"""Life-path simulation — Wait-But-Why style past / today / 3-month future tree."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from core.config import get_openai_model, get_project_root
from core.memory_manager import MemoryManager
from core.state_machine import UserState

LIFE_PATH_FILENAME = "life_path.json"

_JSON_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_seed(state: UserState) -> dict[str, Any]:
    """Offline-safe default graph so the section is never empty before first LLM call."""
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "version": 1,
        "generated_at": _now_iso(),
        "trigger": "seed",
        "summary": "默认三月路径：在浇灌私料之前，镜子先给出可分叉的重要节点骨架。",
        "today_label": "你的人生 · 今天",
        "state_snapshot": {
            "capital": state.capital,
            "energy": state.energy,
            "entropy_rate": state.entropy_rate,
        },
        "past": {
            "trunk": [
                {"id": "born", "label": "起点", "detail": "镜子苏醒之前的空白页。"},
                {
                    "id": "awaken",
                    "label": "接通孪生",
                    "detail": "本地记忆与状态机上线；尚未浇灌私料。",
                },
            ],
            "closed": [
                {
                    "id": "closed_ignore",
                    "from": "awaken",
                    "label": "从不喂养",
                    "detail": "让孪生停在空壳——已关闭。",
                },
                {
                    "id": "closed_outsource",
                    "from": "awaken",
                    "label": "把决定外包给热闹",
                    "detail": "用忙碌替代选择——已关闭。",
                },
            ],
        },
        "future": {
            "months": [
                {
                    "month": 1,
                    "label": "第 1 月",
                    "nodes": [
                        {
                            "id": "m1_focus",
                            "label": "收束注意力",
                            "detail": "把散落的念头收成一张可执行的短清单。",
                            "capital_delta": -2,
                            "energy_delta": -8,
                            "entropy_delta": -0.02,
                        },
                        {
                            "id": "m1_drift",
                            "label": "继续漂",
                            "detail": "维持现状，熵慢慢爬升。",
                            "capital_delta": 0,
                            "energy_delta": -3,
                            "entropy_delta": 0.04,
                        },
                    ],
                },
                {
                    "month": 2,
                    "label": "第 2 月",
                    "nodes": [
                        {
                            "id": "m2_commit",
                            "label": "押一个方向",
                            "detail": "对清单里的一项做不可逆的小承诺。",
                            "parent": "m1_focus",
                            "capital_delta": -10,
                            "energy_delta": -12,
                            "entropy_delta": 0.01,
                        },
                        {
                            "id": "m2_hedge",
                            "label": "两边都留",
                            "detail": "保留退路，进度变慢。",
                            "parent": "m1_focus",
                            "capital_delta": -4,
                            "energy_delta": -6,
                            "entropy_delta": 0.03,
                        },
                        {
                            "id": "m2_stall",
                            "label": "卡在等待",
                            "detail": "等一个不会自己到来的信号。",
                            "parent": "m1_drift",
                            "capital_delta": -1,
                            "energy_delta": -5,
                            "entropy_delta": 0.05,
                        },
                    ],
                },
                {
                    "month": 3,
                    "label": "第 3 月",
                    "nodes": [
                        {
                            "id": "m3_proof",
                            "label": "交出证据",
                            "detail": "用一件可展示的结果证明方向成立。",
                            "parent": "m2_commit",
                            "capital_delta": 5,
                            "energy_delta": -10,
                            "entropy_delta": -0.03,
                        },
                        {
                            "id": "m3_rethink",
                            "label": "回头改写",
                            "detail": "承认对冲失败，重开第 1 月的分叉。",
                            "parent": "m2_hedge",
                            "capital_delta": -6,
                            "energy_delta": -9,
                            "entropy_delta": 0.02,
                        },
                        {
                            "id": "m3_fade",
                            "label": "静音退出",
                            "detail": "话题从生活里消失，但消耗已经发生。",
                            "parent": "m2_stall",
                            "capital_delta": -2,
                            "energy_delta": -4,
                            "entropy_delta": 0.06,
                        },
                    ],
                },
            ]
        },
        "history": [],
        "meta": {"today": today, "horizon_months": 3},
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    candidates: list[str] = []
    for m in _JSON_BLOCK.finditer(text):
        candidates.append(m.group(1).strip())
    candidates.append(text)
    for raw in candidates:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                continue
            try:
                obj = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                continue
        if isinstance(obj, dict) and "future" in obj:
            return obj
    return None


class LifePathEngine:
    """Generate and version the branching life-path graph."""

    def __init__(
        self,
        client: OpenAI,
        memory: MemoryManager,
        state: UserState,
        *,
        model: str | None = None,
        path: Path | None = None,
    ) -> None:
        self._client = client
        self._memory = memory
        self._state = state
        self._model = model or get_openai_model()
        self._path = path or (get_project_root() / LIFE_PATH_FILENAME)

    def load_or_seed(self) -> dict[str, Any]:
        if self._path.is_file():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("future"):
                data.setdefault("history", [])
                return data
        seed = _default_seed(self._state)
        self.save(seed)
        return seed

    def save(self, data: dict[str, Any]) -> None:
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def ensure_ready(self, *, generate_if_seed: bool = True) -> dict[str, Any]:
        data = self.load_or_seed()
        if generate_if_seed and data.get("trigger") == "seed":
            try:
                return self.regenerate(reason="boot", archive=False)
            except Exception:
                return data
        return data

    def regenerate(self, *, reason: str, archive: bool = True) -> dict[str, Any]:
        current = self.load_or_seed()
        history = list(current.get("history") or [])
        if archive and current.get("trigger") != "seed":
            history.append(
                {
                    "id": uuid.uuid4().hex[:10],
                    "archived_at": _now_iso(),
                    "reason": reason,
                    "summary": current.get("summary", ""),
                    "today_label": current.get("today_label", "今天"),
                    "past": current.get("past", {}),
                    "future": current.get("future", {}),
                    "generated_at": current.get("generated_at"),
                    "trigger": current.get("trigger"),
                }
            )
            # Keep last 12 archives
            history = history[-12:]

        memory_hits = self._memory.search_relevant_events(
            "未来三个月 重要决定 人生路径 工作 关系 健康 金钱",
            limit=8,
        )
        mem_block = "（暂无浇灌材料）"
        if memory_hits:
            parts = []
            for i, h in enumerate(memory_hits, start=1):
                parts.append(
                    f"[{i}] {h.get('event_type','')} | {h.get('timestamp','')}\n"
                    f"{h.get('text','')[:500]}"
                )
            mem_block = "\n\n".join(parts)

        # Fold previous future into closed past branches when archiving
        past = current.get("past") or {"trunk": [], "closed": []}
        if archive and current.get("trigger") != "seed":
            past = self._fold_future_into_past(past, current.get("future") or {})

        prompt = (
            "你是 Mirror Image 的人生路径绘图引擎。根据用户记忆与物理状态，"
            "输出接下来 3 个月的重要节点分叉图（JSON only）。\n"
            "结构必须严格为：\n"
            "{\n"
            '  "summary": "一句话总览",\n'
            '  "today_label": "今天节点短标签",\n'
            '  "past": {\n'
            '    "trunk": [{"id":"...", "label":"...", "detail":"..."}],\n'
            '    "closed": [{"id":"...", "from":"trunk-id或today", "label":"...", "detail":"..."}]\n'
            "  },\n"
            '  "future": {\n'
            '    "months": [\n'
            "      {\n"
            '        "month": 1, "label": "第 1 月",\n'
            '        "nodes": [{"id":"m1_a","label":"...","detail":"...","capital_delta":0,'
            '"energy_delta":0,"entropy_delta":0}]\n'
            "      },\n"
            "      { \"month\": 2, \"label\": \"第 2 月\", \"nodes\": ["
            "{\"id\":\"m2_a\",\"label\":\"...\",\"detail\":\"...\",\"parent\":\"m1_a\","
            '"capital_delta":0,"energy_delta":0,"entropy_delta":0}] },\n'
            "      { \"month\": 3, \"label\": \"第 3 月\", \"nodes\": ["
            "{\"id\":\"m3_a\",\"label\":\"...\",\"detail\":\"...\",\"parent\":\"m2_a\","
            '"capital_delta":0,"energy_delta":0,"entropy_delta":0}] }\n'
            "    ]\n"
            "  }\n"
            "}\n"
            "规则：\n"
            "- past.trunk：到达今天的主路径，2～5 个节点（可吸收历史）。\n"
            "- past.closed：已关闭的岔路，2～6 条。\n"
            "- future：每月 2～3 个开放节点；month 2/3 必须用 parent 指向上月节点 id。\n"
            "- 标签短（≤14字），detail 一句刺骨说明。\n"
            "- 结合物理状态，delta 要合理。\n"
            f"当前物理：capital={self._state.capital:.1f}, energy={self._state.energy:.1f}, "
            f"entropy_rate={self._state.entropy_rate:.2f}\n"
            f"触发原因：{reason}\n"
            f"相关记忆：\n{mem_block}\n"
            f"既有 past（可改写但保留连续感）：\n{json.dumps(past, ensure_ascii=False)[:2500]}"
        )

        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "只输出合法 JSON。不要 Markdown 说明。语言用中文。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.55,
            max_tokens=2200,
        )
        raw = (resp.choices[0].message.content or "").strip()
        parsed = _extract_json(raw)
        if not parsed:
            # Fall back to seed-shaped future but keep archived history
            parsed = _default_seed(self._state)
            parsed["summary"] = "模型未返回合法 JSON，沿用骨架路径。"
            parsed["trigger"] = reason

        data = {
            "version": 1,
            "generated_at": _now_iso(),
            "trigger": reason,
            "summary": parsed.get("summary") or current.get("summary") or "",
            "today_label": parsed.get("today_label") or "你的人生 · 今天",
            "state_snapshot": {
                "capital": self._state.capital,
                "energy": self._state.energy,
                "entropy_rate": self._state.entropy_rate,
            },
            "past": parsed.get("past") or past,
            "future": parsed.get("future") or current.get("future"),
            "history": history,
            "meta": {
                "today": datetime.now().strftime("%Y-%m-%d"),
                "horizon_months": 3,
                "memory_hits": len(memory_hits),
            },
        }
        self._normalize(data)
        self.save(data)
        return data

    def _fold_future_into_past(
        self, past: dict[str, Any], future: dict[str, Any]
    ) -> dict[str, Any]:
        trunk = list(past.get("trunk") or [])
        closed = list(past.get("closed") or [])
        # Promote first node of each month as a faint trunk echo, rest as closed
        for month in future.get("months") or []:
            nodes = month.get("nodes") or []
            if not nodes:
                continue
            head = nodes[0]
            trunk.append(
                {
                    "id": f"hist_{head.get('id', uuid.uuid4().hex[:6])}",
                    "label": f"曾推演·{head.get('label', '节点')}",
                    "detail": head.get("detail", ""),
                }
            )
            for n in nodes[1:]:
                closed.append(
                    {
                        "id": f"closed_{n.get('id', uuid.uuid4().hex[:6])}",
                        "from": trunk[-1]["id"] if trunk else "today",
                        "label": n.get("label", "岔路"),
                        "detail": n.get("detail", "浇灌后关闭的旧未来。"),
                    }
                )
        # Cap sizes
        return {"trunk": trunk[-6:], "closed": closed[-10:]}

    def _normalize(self, data: dict[str, Any]) -> None:
        past = data.setdefault("past", {})
        past.setdefault("trunk", [])
        past.setdefault("closed", [])
        future = data.setdefault("future", {})
        months = future.get("months") or []
        # Ensure month numbers
        for i, m in enumerate(months, start=1):
            m.setdefault("month", i)
            m.setdefault("label", f"第 {i} 月")
            m.setdefault("nodes", [])
        data.setdefault("history", [])
