"""Life-path simulation — branching lives, not a mind map."""

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
from core.twin_model import TwinModel

LIFE_PATH_FILENAME = "life_path.json"
MIN_HORIZON = 2
MAX_HORIZON = 6
DEFAULT_HORIZON = 3

_JSON_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp_horizon(value: Any, fallback: int = DEFAULT_HORIZON) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = fallback
    return max(MIN_HORIZON, min(MAX_HORIZON, n))


def _n(
    nid: str,
    label: str,
    detail: str,
    *,
    parent: str | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": nid,
        "label": label,
        "detail": detail,
    }
    if parent:
        node["parent"] = parent
    return node


def _default_seed(state: UserState, months: int = DEFAULT_HORIZON) -> dict[str, Any]:
    """Offline-safe default graph: 3 forks, then 3 from each, then those 9 lives continue."""
    today = datetime.now().strftime("%Y-%m-%d")
    months = clamp_horizon(months)

    m1 = [
        _n("m1_a", "Gather attention", "Fold the noise into one short list you can actually hold."),
        _n("m1_b", "Keep drifting", "Stay as you are. The days blur, and nothing asks you back."),
        _n("m1_c", "Make a small bet", "Spend a little so the week has a direction, even a foolish one."),
    ]
    m2 = [
        _n("m2_a1", "Protect the hours", "Guard three mornings. The list either lives there or it doesn't.", parent="m1_a"),
        _n("m2_a2", "Say it out loud", "Tell someone who will remember. A witness changes the temperature.", parent="m1_a"),
        _n("m2_a3", "Polish forever", "The list gets prettier. Nothing leaves the notebook.", parent="m1_a"),
        _n("m2_b1", "A knock anyway", "Something outside you forces a turn. Not cruel — just sooner.", parent="m1_b"),
        _n("m2_b2", "Soft numbness", "Comfortable, expensive in ways you won't notice yet.", parent="m1_b"),
        _n("m2_b3", "Name the stall", "You feel the pause and give it one honest sentence.", parent="m1_b"),
        _n("m2_c1", "Double down", "Put a month of life behind the bet so it can bruise you.", parent="m1_c"),
        _n("m2_c2", "Keep a back door", "Progress halves; so does the fear. Both futures get thinner.", parent="m1_c"),
        _n("m2_c3", "Walk it back", "The bet becomes a story you tell. You are free, and a little poorer in nerve.", parent="m1_c"),
    ]
    m3 = [
        _n("m3_a1", "First proof", "One thing exists that did not exist when this started.", parent="m2_a1"),
        _n("m3_a2", "A witness stays", "Someone else can see you're different, and says so.", parent="m2_a2"),
        _n("m3_a3", "Beautiful stall", "The plan is perfect and untouched. Dust on a bright page.", parent="m2_a3"),
        _n("m3_b1", "New weather", "You're living someone else's plot, not unkindly.", parent="m2_b1"),
        _n("m3_b2", "Same room", "The furniture hasn't moved. You have, a little.", parent="m2_b2"),
        _n("m3_b3", "A usable sentence", "The ache became a line you can act on tomorrow morning.", parent="m2_b3"),
        _n("m3_c1", "It has a name", "Other people use the name of the bet without asking what it is.", parent="m2_c1"),
        _n("m3_c2", "Split self", "Two futures, both thinner. You keep both keys.", parent="m2_c2"),
        _n("m3_c3", "Clean slate", "Nothing owed. The quiet is real, and slightly hollow.", parent="m2_c3"),
    ]

    sequels = [
        ("Weather sets in", "The choice has seasons now. You dress for it without thinking."),
        ("A smaller room", "Life rearranged around the fork. Some friends stopped asking."),
        ("Still a draft", "You are living in pencil. Easy to change; hard to inhabit."),
        ("Someone else's map", "The path is clear because it isn't yours."),
        ("Quiet inventory", "You can name what the months cost. That is already a kind of wealth."),
        ("A door you use", "The sentence became a habit. Morning knows what to do."),
        ("Public enough", "The work has an address. People knock."),
        ("Two calendars", "You keep both lives in the same week. Neither gets a full meal."),
        ("Light luggage", "You left it. The absence is cleaner than you feared, and lonelier."),
    ]

    future_months: list[dict[str, Any]] = [
        {"month": 1, "label": "Month 1", "nodes": m1},
        {"month": 2, "label": "Month 2", "nodes": m2},
    ]
    prev = m3
    if months >= 3:
        future_months.append({"month": 3, "label": "Month 3", "nodes": m3})
    for mi in range(4, months + 1):
        nodes = []
        for i, parent in enumerate(prev):
            label, detail = sequels[i]
            nodes.append(
                _n(
                    f"m{mi}_{parent['id'].split('_', 1)[-1]}",
                    label,
                    detail,
                    parent=parent["id"],
                )
            )
        future_months.append({"month": mi, "label": f"Month {mi}", "nodes": nodes})
        prev = nodes

    return {
        "version": 2,
        "generated_at": _now_iso(),
        "trigger": "seed",
        "summary": "Three doors from today. Each door splits three ways. After that, those nine lives simply continue.",
        "today_label": "You, here",
        "past": {
            "trunk": [
                {"id": "born", "label": "Beginning", "detail": "A blank page, before the twin woke."},
                {
                    "id": "awaken",
                    "label": "Twin online",
                    "detail": "Memory is empty. The path ahead is still a sketch.",
                },
            ],
            "closed": [
                {
                    "id": "closed_ignore",
                    "from": "awaken",
                    "label": "Never feed it",
                    "detail": "Leave the twin hollow — a door already shut.",
                },
                {
                    "id": "closed_outsource",
                    "from": "awaken",
                    "label": "Let the week decide",
                    "detail": "Busyness standing in for a choice.",
                },
            ],
        },
        "future": {"months": future_months},
        "history": [],
        "meta": {"today": today, "horizon_months": months},
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
        twin_model: TwinModel | None = None,
        *,
        model: str | None = None,
        path: Path | None = None,
    ) -> None:
        self._client = client
        self._memory = memory
        self._state = state
        self._twin_model = twin_model
        self._model = model or get_openai_model()
        self._path = path or (get_project_root() / LIFE_PATH_FILENAME)

    def load_or_seed(self) -> dict[str, Any]:
        if self._path.is_file():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("future"):
                data.setdefault("history", [])
                data.setdefault("meta", {})
                data["meta"].setdefault("horizon_months", DEFAULT_HORIZON)
                if self._is_legacy_shape(data):
                    return self._upgrade_legacy(data)
                horizon = clamp_horizon(data["meta"].get("horizon_months"))
                self._normalize(data, horizon=horizon)
                self.save(data)
                return data
        seed = _default_seed(self._state)
        self.save(seed)
        return seed

    def _is_legacy_shape(self, data: dict[str, Any]) -> bool:
        if int(data.get("version") or 1) < 2:
            return True
        months = (data.get("future") or {}).get("months") or []
        if not months:
            return True
        month1 = len(months[0].get("nodes") or [])
        month2 = len(months[1].get("nodes") or []) if len(months) > 1 else 0
        return month1 < 3 or month2 < 9

    def _upgrade_legacy(self, data: dict[str, Any]) -> dict[str, Any]:
        horizon = clamp_horizon((data.get("meta") or {}).get("horizon_months"))
        seed = _default_seed(self._state, horizon)
        history = list(data.get("history") or [])
        if data.get("trigger") != "seed":
            history.append(
                {
                    "id": uuid.uuid4().hex[:10],
                    "archived_at": _now_iso(),
                    "reason": data.get("trigger") or "manual",
                    "summary": data.get("summary", ""),
                    "today_label": data.get("today_label", ""),
                    "past": data.get("past", {}),
                    "future": data.get("future", {}),
                    "generated_at": data.get("generated_at"),
                    "trigger": data.get("trigger"),
                    "horizon_months": (data.get("meta") or {}).get("horizon_months"),
                }
            )
        seed["history"] = history[-12:]
        seed["trigger"] = "upgrade"
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

    def regenerate(
        self,
        *,
        reason: str,
        archive: bool = True,
        lang: str = "en",
        months: int | None = None,
    ) -> dict[str, Any]:
        current = self.load_or_seed()
        horizon = clamp_horizon(
            months
            if months is not None
            else (current.get("meta") or {}).get("horizon_months")
        )
        history = list(current.get("history") or [])
        if archive and current.get("trigger") != "seed":
            history.append(
                {
                    "id": uuid.uuid4().hex[:10],
                    "archived_at": _now_iso(),
                    "reason": reason,
                    "summary": current.get("summary", ""),
                    "today_label": current.get("today_label", "today"),
                    "past": current.get("past", {}),
                    "future": current.get("future", {}),
                    "generated_at": current.get("generated_at"),
                    "trigger": current.get("trigger"),
                    "horizon_months": (current.get("meta") or {}).get("horizon_months"),
                }
            )
            history = history[-12:]

        memory_hits = self._memory.search_relevant_events(
            "future months important decisions life path work love health money",
            limit=8,
        )
        mem_block = "(no watered material yet)"
        if memory_hits:
            parts = []
            for i, h in enumerate(memory_hits, start=1):
                parts.append(
                    f"[{i}] {h.get('event_type','')} | {h.get('timestamp','')}\n"
                    f"{h.get('text','')[:500]}"
                )
            mem_block = "\n\n".join(parts)
        profile_block = (
            self._twin_model.compact_context()
            if self._twin_model is not None
            else "(no durable twin model)"
        )

        past = current.get("past") or {"trunk": [], "closed": []}
        later_rule = ""
        if horizon >= 3:
            later_rule = (
                f"- Months 3–{horizon}: exactly 9 nodes each. Each node continues "
                "ONE of the month-2 lives (parent = that month-2 id, then 1:1 down the chain). "
                "Do not explode into 27 forks.\n"
            )

        lang_line = (
            "Write every summary, label, and detail in English. "
            "Labels should sound speakable, not like category titles."
        )
        json_sys = (
            "Output valid JSON only. No markdown commentary. All strings in English."
        )
        prompt = (
            "You are Digital Twin's cartographer of lives — not a mind-map generator.\n"
            "From the user's evidence and revisable twin model, draw branching lives they could actually walk.\n"
            f"{lang_line}\n"
            f"Horizon: the next {horizon} month(s).\n"
            "Shape (strict):\n"
            "- Month 1: exactly 3 nodes. These are three real choices from TODAY. No parent field.\n"
            "- Month 2: exactly 9 nodes. Each month-1 node has exactly 3 children (parent = that month-1 id).\n"
            f"{later_rule}"
            "This is a river delta, not an org chart: uneven, specific, a little tender.\n"
            "JSON shape:\n"
            "{\n"
            '  "summary": "one warm sentence",\n'
            '  "today_label": "short name for today",\n'
            '  "past": {\n'
            '    "trunk": [{"id":"...","label":"...","detail":"..."}],\n'
            '    "closed": [{"id":"...","from":"trunk-id or today","label":"...","detail":"..."}]\n'
            "  },\n"
            '  "future": { "months": [ { "month": 1, "label": "Month 1", "nodes": ['
            '{"id":"m1_a","label":"...","detail":"...","plausibility":"plausible|strained|breaks|unknown",'
            '"plausibility_confidence":0.0,"constraint_basis":["..."],'
            '"pressure":{"money":"low|medium|high|unknown","energy":"low|medium|high|unknown",'
            '"coordination":"low|medium|high|unknown"}}'
            "] } ] }\n"
            "}\n"
            "Rules:\n"
            "- past.trunk: 2–4 nodes that led here.\n"
            "- past.closed: 2–5 doors already shut.\n"
            "- ids unique. month 2+ nodes MUST set parent.\n"
            "- label: 2–6 words. Concrete. Not 'Career' / 'Health' / 'Plan A'.\n"
            "- detail: one sensory sentence — a room, a cost, a morning. Not a strategy bullet.\n"
            "- Never invent exact resource numbers. Express pressure qualitatively and keep unknowns unknown.\n"
            "- plausibility is not desirability: plausible / strained / breaks / unknown.\n"
            "- constraint_basis must point to a concrete twin-model claim or memory; if none exists, use [].\n"
            "- Every branch must be causally different because of this person's documented "
            "patterns or constraints. Avoid advice that could describe anyone.\n"
            "- A branch may break under a documented constraint. Do not quietly make it easy, "
            "but never declare impossibility from weak evidence.\n"
            f"Why this map: {reason}\n"
            f"Active commitment (a choice, not proof it happened):\n"
            f"{json.dumps(current.get('commitment'), ensure_ascii=False)[:1200]}\n"
            f"Durable twin model (claims remain uncertain):\n{profile_block}\n"
            f"Memory:\n{mem_block}\n"
            f"Existing past (keep continuity):\n{json.dumps(past, ensure_ascii=False)[:2500]}"
        )

        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": json_sys},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=min(8000, 2800 + horizon * 700),
        )
        raw = (resp.choices[0].message.content or "").strip()
        parsed = _extract_json(raw)
        if not parsed:
            parsed = _default_seed(self._state, horizon)
            parsed["summary"] = "The model didn't return valid JSON; keeping the sketched path."
            parsed["trigger"] = reason

        data = {
            "version": 2,
            "generated_at": _now_iso(),
            "trigger": reason,
            "summary": parsed.get("summary") or current.get("summary") or "",
            "today_label": parsed.get("today_label") or "You, here",
            "past": parsed.get("past") or past,
            "future": parsed.get("future") or current.get("future"),
            "history": history,
            "commitment": current.get("commitment"),
            "meta": {
                "today": datetime.now().strftime("%Y-%m-%d"),
                "horizon_months": horizon,
                "memory_hits": len(memory_hits),
            },
        }
        self._normalize(data, horizon=horizon)
        self.save(data)
        return data

    def _fold_future_into_past(
        self,
        past: dict[str, Any],
        future: dict[str, Any],
        *,
        commitment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trunk = list(past.get("trunk") or [])
        closed = list(past.get("closed") or [])
        months = future.get("months") or []
        first = (months[0].get("nodes") or []) if months else []
        committed_id = str((commitment or {}).get("node_id") or "")
        committed_path = set((commitment or {}).get("path_ids") or [])
        head = next(
            (node for node in first if node.get("id") in committed_path or node.get("id") == committed_id),
            None,
        )
        if head:
            trunk.append(
                {
                    "id": f"hist_{head.get('id', uuid.uuid4().hex[:6])}",
                    "label": head.get("label", ""),
                    "detail": head.get("detail", ""),
                }
            )
            origin = trunk[-1]["id"] if trunk else "today"
            for n in first:
                if n.get("id") == head.get("id"):
                    continue
                closed.append(
                    {
                        "id": f"closed_{n.get('id', uuid.uuid4().hex[:6])}",
                        "from": origin,
                        "label": n.get("label", ""),
                        "detail": n.get("detail", ""),
                    }
                )
        return {"trunk": trunk[-5:], "closed": closed[-8:]}

    def commit(self, node_id: str) -> dict[str, Any]:
        """Record an explicit choice without pretending the predicted future already happened."""
        data = self.load_or_seed()
        months = (data.get("future") or {}).get("months") or []
        by_id: dict[str, dict[str, Any]] = {}
        for month in months:
            for node in month.get("nodes") or []:
                by_id[str(node.get("id", ""))] = node
        node = by_id.get(node_id)
        if node is None:
            raise ValueError("Path node not found.")
        path_ids: list[str] = []
        cursor: dict[str, Any] | None = node
        seen: set[str] = set()
        while cursor is not None:
            cursor_id = str(cursor.get("id", ""))
            if not cursor_id or cursor_id in seen:
                break
            seen.add(cursor_id)
            path_ids.append(cursor_id)
            cursor = by_id.get(str(cursor.get("parent") or ""))
        path_ids.reverse()
        commitment = {
            "node_id": node_id,
            "path_ids": path_ids,
            "label": node.get("label", ""),
            "detail": node.get("detail", ""),
            "committed_at": _now_iso(),
            "predicted_pressure": node.get("pressure", {}),
            "plausibility": node.get("plausibility", "unknown"),
            "status": "active",
        }
        data["commitment"] = commitment
        self.save(data)
        self._memory.add_event(
            "[Committed path]\n"
            f"Choice: {commitment['label']}\n"
            f"Expected life: {commitment['detail']}\n"
            f"Path ids: {', '.join(path_ids)}",
            "Choice_Commitment",
            source="life-path",
            media_kind="decision",
        )
        return data

    def apply_edits(
        self,
        *,
        positions: dict[str, dict[str, float]] | None = None,
        edits: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        data = self.load_or_seed()
        positions = positions or {}
        edits = edits or {}

        def visit(node: dict[str, Any]) -> None:
            nid = str(node.get("id", ""))
            if not nid:
                return
            if nid in positions:
                pos = positions[nid]
                if "x" in pos and "y" in pos:
                    node["x"] = float(pos["x"])
                    node["y"] = float(pos["y"])
            if nid in edits:
                if "label" in edits[nid] and edits[nid]["label"] is not None:
                    node["label"] = str(edits[nid]["label"]).strip()[:40]
                if "detail" in edits[nid] and edits[nid]["detail"] is not None:
                    node["detail"] = str(edits[nid]["detail"]).strip()[:800]

        if "today" in positions:
            pos = positions["today"]
            if "x" in pos and "y" in pos:
                data["today_x"] = float(pos["x"])
                data["today_y"] = float(pos["y"])
        if "today" in edits:
            if edits["today"].get("label"):
                data["today_label"] = str(edits["today"]["label"]).strip()[:40]
            if "detail" in edits["today"] and edits["today"]["detail"] is not None:
                data["summary"] = str(edits["today"]["detail"]).strip()[:800]

        past = data.setdefault("past", {})
        for node in past.get("trunk") or []:
            visit(node)
        for node in past.get("closed") or []:
            visit(node)
        for month in (data.get("future") or {}).get("months") or []:
            for node in month.get("nodes") or []:
                visit(node)

        self.save(data)
        return data

    def _normalize(self, data: dict[str, Any], *, horizon: int) -> None:
        past = data.setdefault("past", {})
        past.setdefault("trunk", [])
        past.setdefault("closed", [])
        future = data.setdefault("future", {})
        months = list(future.get("months") or [])
        by_num: dict[int, dict[str, Any]] = {}
        for m in months:
            try:
                num = int(m.get("month") or 0)
            except (TypeError, ValueError):
                continue
            if num:
                by_num[num] = m
        ordered = []
        for i in range(1, horizon + 1):
            m = by_num.get(i) or {"month": i, "nodes": []}
            m["month"] = i
            m.setdefault("label", f"Month {i}")
            m.setdefault("nodes", [])
            ordered.append(m)
        future["months"] = ordered
        self._normalize_constraints(ordered)
        data.setdefault("history", [])
        data.pop("state_snapshot", None)
        meta = data.setdefault("meta", {})
        meta["horizon_months"] = horizon

    def _normalize_constraints(self, months: list[dict[str, Any]]) -> None:
        """Expose uncertainty instead of laundering weak evidence into exact meters."""
        valid_plausibility = {"plausible", "strained", "breaks", "unknown"}
        valid_pressure = {"low", "medium", "high", "unknown"}
        for month in months:
            for node in month.get("nodes") or []:
                plausibility = str(node.get("plausibility") or "unknown").lower()
                node["plausibility"] = (
                    plausibility if plausibility in valid_plausibility else "unknown"
                )
                try:
                    confidence = float(node.get("plausibility_confidence", 0) or 0)
                except (TypeError, ValueError):
                    confidence = 0.0
                node["plausibility_confidence"] = max(0.0, min(1.0, confidence))
                basis = node.get("constraint_basis")
                node["constraint_basis"] = basis[:4] if isinstance(basis, list) else []
                pressure = node.get("pressure") if isinstance(node.get("pressure"), dict) else {}
                normalized_pressure: dict[str, str] = {}
                for key in ("money", "energy", "coordination"):
                    value = str(pressure.get(key) or "unknown").lower()
                    normalized_pressure[key] = value if value in valid_pressure else "unknown"
                node["pressure"] = normalized_pressure
