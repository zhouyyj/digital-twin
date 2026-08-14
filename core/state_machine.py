"""Persistent physical state + deduction JSON parsing for Digital Twin."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from core.config import get_project_root

STATE_FILENAME = "state.json"

_DEDUCTION_JSON_BLOCK = re.compile(
    r"```(?:json)?\s*(\{[\s\S]*?\})\s*```",
    re.IGNORECASE,
)

Outcome = Literal["accepted", "intercepted", "no_json"]


@dataclass
class UserState:
    """Hard physical meters (reserve, energy, chaos)."""

    capital: float = 100.0
    energy: float = 100.0
    entropy_rate: float = 0.2

    @classmethod
    def default(cls) -> UserState:
        return cls(capital=100.0, energy=100.0, entropy_rate=0.2)

    @classmethod
    def load(cls, path: Path | None = None) -> UserState:
        root = path or get_project_root() / STATE_FILENAME
        if not root.is_file():
            state = cls.default()
            state.save(root)
            return state
        data = json.loads(root.read_text(encoding="utf-8"))
        return cls(
            capital=float(data.get("capital", 100.0)),
            energy=float(data.get("energy", 100.0)),
            entropy_rate=float(data.get("entropy_rate", 0.2)),
        )

    def save(self, path: Path | None = None) -> None:
        root = path or get_project_root() / STATE_FILENAME
        root.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def preview_energy_after(self, energy_delta: float) -> float:
        return self.energy + energy_delta

    def apply_deltas(
        self,
        capital_delta: float,
        energy_delta: float,
        entropy_rate_delta: float,
    ) -> bool:
        """Reject the whole change if energy would go below 0. Persist on success."""
        new_energy = self.energy + energy_delta
        if new_energy < 0:
            return False
        self.capital += capital_delta
        self.energy = new_energy
        self.entropy_rate = max(0.0, min(1.0, self.entropy_rate + entropy_rate_delta))
        self.save()
        return True


def is_deduction_request(user_text: str) -> bool:
    lower = user_text.lower()
    return (
        "deduce" in lower
        or "make a choice" in lower
        or "choose" in lower
        or "推演" in user_text
        or "做选择" in user_text
    )


def deduction_instruction_block(state: UserState) -> str:
    return (
        "[Physical constraint] This turn is a deduction / choice. After the analysis, "
        "append a Markdown JSON code block at the very end with only three numeric fields:\n"
        '  "capital_delta" — change to capital (use negatives to spend);\n'
        '  "energy_delta" — change to energy (use negatives to spend);\n'
        '  "entropy_rate_delta" — change to entropy_rate (more chaos is positive).\n'
        "Example:\n```json\n"
        '{"capital_delta": -5.0, "energy_delta": -12.0, "entropy_rate_delta": 0.03}\n'
        "```\n"
        f"Current physical state: capital={state.capital:.2f}, energy={state.energy:.2f}, "
        f"entropy_rate={state.entropy_rate:.2f}."
    )


def extract_last_state_delta_block(full: str) -> tuple[dict[str, float] | None, re.Match[str] | None]:
    """Pull the last valid state-delta JSON block from a model reply."""
    for m in reversed(list(_DEDUCTION_JSON_BLOCK.finditer(full))):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if not any(
            k in obj for k in ("capital_delta", "energy_delta", "entropy_rate_delta")
        ):
            continue
        deltas = {
            "capital_delta": float(obj.get("capital_delta", 0) or 0),
            "energy_delta": float(obj.get("energy_delta", 0) or 0),
            "entropy_rate_delta": float(obj.get("entropy_rate_delta", 0) or 0),
        }
        return deltas, m
    return None, None


def strip_json_block(full: str, match: re.Match[str]) -> str:
    return (full[: match.start()] + full[match.end() :]).rstrip()


def evaluate_deduction_reply(state: UserState, reply_full: str) -> tuple[str, Outcome]:
    """
    Parse cost JSON from a deduction reply. If energy would go below 0, intercept
    (do not apply, do not show the body). Returns (display text, outcome).
    """
    deltas, m = extract_last_state_delta_block(reply_full)
    if deltas is None:
        return reply_full.strip(), "no_json"

    new_energy = state.preview_energy_after(deltas["energy_delta"])
    if new_energy < 0:
        return "", "intercepted"

    if not state.apply_deltas(
        deltas["capital_delta"],
        deltas["energy_delta"],
        deltas["entropy_rate_delta"],
    ):
        return "", "intercepted"

    display = strip_json_block(reply_full, m).strip() if m else reply_full.strip()
    return display, "accepted"


PHYSICAL_ALERT = "[Physical alert: energy exhausted. This path breaks here.]"
