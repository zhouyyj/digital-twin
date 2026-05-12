"""Persistent physical state + deduction JSON parsing for Mirror Image."""

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
    """硬性物理指标（精力 / 资金储备、身心带宽、混乱度）。"""

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
        """若精力将低于 0 则拒绝整次变更（不修改任何字段）。成功则落盘。"""
        new_energy = self.energy + energy_delta
        if new_energy < 0:
            return False
        self.capital += capital_delta
        self.energy = new_energy
        self.entropy_rate = max(0.0, min(1.0, self.entropy_rate + entropy_rate_delta))
        self.save()
        return True


def is_deduction_request(user_text: str) -> bool:
    return "推演" in user_text or "做选择" in user_text


def deduction_instruction_block(state: UserState) -> str:
    return (
        "【物理状态机约束】本轮涉及「推演」或「做选择」。你必须在推演/选项分析之后，"
        "在整段回复的最后单独附加一个 Markdown JSON 代码块，且仅包含三个数字字段：\n"
        '  "capital_delta" — 对 capital 的增量（消耗用负数）；\n'
        '  "energy_delta" — 对 energy 的增量（消耗用负数）；\n'
        '  "entropy_rate_delta" — 对 entropy_rate 的增量（更混乱为正）。\n'
        "示例：\n```json\n"
        '{"capital_delta": -5.0, "energy_delta": -12.0, "entropy_rate_delta": 0.03}\n'
        "```\n"
        f"当前物理状态：capital={state.capital:.2f}, energy={state.energy:.2f}, "
        f"entropy_rate={state.entropy_rate:.2f}。"
    )


def extract_last_state_delta_block(full: str) -> tuple[dict[str, float] | None, re.Match[str] | None]:
    """从模型回复中取出最后一个合法的状态增量 JSON 代码块。"""
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
    解析推演回复中的 JSON 消耗；若精力将 < 0 则拦截（不应用、不展示正文）。
    返回 (展示用文本, 结果标记)。
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


PHYSICAL_ALERT_CN = "【系统物理警报：精力耗尽，推演路径在此断裂】"
