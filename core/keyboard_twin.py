"""Phase 4 — keyboard twin: cognitive tempo via pynput (rhythm, not keylogging)."""

from __future__ import annotations

import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from pynput import keyboard

from core.state_machine import UserState

PrintFn = Callable[..., None]


@dataclass
class TwinSnapshot:
    """Aggregate of a listening window — never includes key characters."""

    keystrokes: int = 0
    bursts: int = 0
    active_seconds: float = 0.0
    idle_seconds: float = 0.0
    mean_ipi_ms: float | None = None
    ipi_stdev_ms: float | None = None
    entropy_nudge: float = 0.0

    def as_memory_text(self) -> str:
        mean = f"{self.mean_ipi_ms:.0f}ms" if self.mean_ipi_ms is not None else "n/a"
        stdev = f"{self.ipi_stdev_ms:.0f}ms" if self.ipi_stdev_ms is not None else "n/a"
        return (
            "[KeyboardTwin 节奏摘要] "
            f"keystrokes={self.keystrokes}, bursts={self.bursts}, "
            f"active={self.active_seconds:.1f}s, idle={self.idle_seconds:.1f}s, "
            f"mean_IPI={mean}, IPI_stdev={stdev}, "
            f"entropy_nudge={self.entropy_nudge:+.3f}"
        )


@dataclass
class _Session:
    started_at: float = field(default_factory=time.monotonic)
    last_key_at: float | None = None
    last_burst_at: float | None = None
    keystrokes: int = 0
    bursts: int = 0
    intervals_ms: list[float] = field(default_factory=list)
    active_seconds: float = 0.0


class KeyboardTwin:
    """
    Passive tempo sensor.

    Records inter-key intervals and burst structure only — never the key
    identity or character. On stop (or explicit pulse), writes a summary event
    and optionally nudges UserState.entropy_rate from interval variance.
    """

    # Gaps longer than this start a new burst (seconds).
    _BURST_GAP = 1.25
    # Treat as idle beyond this (seconds).
    _IDLE_AFTER = 3.0
    # Cap how much one pulse can move entropy_rate.
    _MAX_ENTROPY_NUDGE = 0.08

    def __init__(
        self,
        state: UserState,
        *,
        print: PrintFn = print,
    ) -> None:
        self._state = state
        self._print = print
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None
        self._session: _Session | None = None

    @property
    def running(self) -> bool:
        return self._listener is not None

    def start(self) -> None:
        if self._listener is not None:
            self._print("键盘孪生已在运行。用 /twin stop 结束，或 /twin pulse 结算当前窗口。")
            return
        with self._lock:
            self._session = _Session()
        self._listener = keyboard.Listener(on_press=self._on_press)
        try:
            self._listener.start()
        except Exception:
            self._listener = None
            with self._lock:
                self._session = None
            raise
        self._print(
            "键盘孪生已启动：只统计击键节奏与爆发间隔，不记录按键内容。"
            "（macOS 需在「辅助功能」中授权本终端。）"
        )

    def stop(self) -> TwinSnapshot | None:
        if self._listener is None:
            self._print("键盘孪生未在运行。")
            return None
        listener = self._listener
        self._listener = None
        try:
            listener.stop()
        except Exception:
            pass
        snap = self._finalize_snapshot(apply_entropy=True)
        self._print("键盘孪生已停止。")
        return snap

    def pulse(self, *, apply_entropy: bool = True) -> TwinSnapshot | None:
        """Close the current window into a snapshot and start a fresh window if still running."""
        if self._session is None:
            self._print("键盘孪生未在运行。")
            return None
        snap = self._finalize_snapshot(apply_entropy=apply_entropy)
        if self._listener is not None:
            with self._lock:
                self._session = _Session()
        return snap

    def status_line(self) -> str:
        with self._lock:
            if self._session is None:
                return "twin=off"
            s = self._session
            elapsed = time.monotonic() - s.started_at
            return (
                f"twin=on keystrokes={s.keystrokes} bursts={s.bursts} "
                f"window={elapsed:.0f}s"
            )

    def _on_press(self, _key: keyboard.Key | keyboard.KeyCode | None) -> None:
        now = time.monotonic()
        with self._lock:
            s = self._session
            if s is None:
                return
            if s.last_key_at is not None:
                gap = now - s.last_key_at
                if gap < self._IDLE_AFTER:
                    s.active_seconds += gap
                    s.intervals_ms.append(gap * 1000.0)
                if gap >= self._BURST_GAP:
                    s.bursts += 1
                    s.last_burst_at = now
            else:
                s.bursts = 1
                s.last_burst_at = now
            s.last_key_at = now
            s.keystrokes += 1

    def _finalize_snapshot(self, *, apply_entropy: bool) -> TwinSnapshot | None:
        with self._lock:
            s = self._session
            self._session = None
        if s is None:
            return None

        now = time.monotonic()
        window = max(0.0, now - s.started_at)
        idle = max(0.0, window - s.active_seconds)
        mean = statistics.fmean(s.intervals_ms) if s.intervals_ms else None
        stdev = (
            statistics.pstdev(s.intervals_ms) if len(s.intervals_ms) >= 2 else None
        )

        nudge = 0.0
        if stdev is not None and mean is not None and mean > 0 and s.keystrokes >= 8:
            # High relative variance → more chaotic tempo → small entropy bump.
            cv = stdev / mean
            # Steady typing (low cv) slightly reduces chaos; erratic raises it.
            nudge = max(-self._MAX_ENTROPY_NUDGE, min(self._MAX_ENTROPY_NUDGE, (cv - 0.55) * 0.06))

        snap = TwinSnapshot(
            keystrokes=s.keystrokes,
            bursts=s.bursts,
            active_seconds=s.active_seconds,
            idle_seconds=idle,
            mean_ipi_ms=mean,
            ipi_stdev_ms=stdev,
            entropy_nudge=nudge,
        )

        if apply_entropy and nudge != 0.0:
            self._state.apply_deltas(0.0, 0.0, nudge)

        return snap
