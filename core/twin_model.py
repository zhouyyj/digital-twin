"""Durable, evidence-bound model of the person behind the simulation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from core.config import get_openai_model, get_project_root
from core.memory_manager import MemoryManager

PROFILE_FILENAME = "twin_profile.json"
_JSON_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_profile() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now(),
        "observations": 0,
        "confidence": 0.0,
        "summary": "Not enough evidence yet. Add a concrete note, diary, or document.",
        "values": [],
        "patterns": [],
        "constraints": [],
        "assets": [],
        "tensions": [],
        "unknowns": [
            "What repeatedly gives or drains energy?",
            "Which obligations cannot be traded away?",
            "What does this person choose when words and behavior disagree?",
        ],
        "revisions": [],
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    candidates = [m.group(1).strip() for m in _JSON_BLOCK.finditer(text)]
    candidates.append(text.strip())
    for raw in candidates:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                continue
            try:
                value = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                continue
        if isinstance(value, dict):
            return value
    return None


class TwinModel:
    """Turns episodic memories into a revisable simulation prior, not a diagnosis."""

    _LIST_FIELDS = ("values", "patterns", "constraints", "assets", "tensions", "unknowns")

    def __init__(
        self,
        client: OpenAI,
        memory: MemoryManager,
        *,
        model: str | None = None,
        path: Path | None = None,
    ) -> None:
        self._client = client
        self._memory = memory
        self._model = model or get_openai_model()
        self._path = path or get_project_root() / PROFILE_FILENAME

    def load(self) -> dict[str, Any]:
        if self._path.is_file():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return self._normalize(data)
            except (OSError, json.JSONDecodeError):
                pass
        data = _default_profile()
        self.save(data)
        return data

    def save(self, data: dict[str, Any]) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def compact_context(self) -> str:
        profile = self.load()
        return json.dumps(
            {
                "summary": profile.get("summary", ""),
                "confidence": profile.get("confidence", 0),
                **{field: profile.get(field, []) for field in self._LIST_FIELDS},
            },
            ensure_ascii=False,
        )

    def refresh(self, *, reason: str) -> dict[str, Any]:
        current = self.load()
        events = [
            event
            for event in self._memory.recent_events(limit=64)
            if event.get("event_type") != "AI_Intervention"
        ][:48]
        if not events:
            return current

        evidence = []
        for event in events:
            evidence_id = str(event.get("id") or "unknown")
            evidence.append(
                f"[{evidence_id}] {event.get('timestamp','')} | {event.get('event_type','')} | "
                f"{event.get('source','')}\n{str(event.get('text',''))[:900]}"
            )
        evidence_block = "\n\n".join(evidence)

        prompt = (
            "Update a digital-twin model from the evidence below. This model will constrain "
            "future simulations, so generic personality language is harmful.\n"
            "Return JSON only with: summary, confidence (0..1), values, patterns, constraints, "
            "assets, tensions, unknowns, revisions.\n"
            "Each list item is an object with keys: claim, evidence (array of persistent evidence ids), confidence. "
            "unknowns may instead be short strings. revisions are short descriptions of what changed.\n"
            "Rules:\n"
            "- Preserve a prior claim only while evidence still supports it.\n"
            "- Separate what the person says from what repeated behavior shows.\n"
            "- Prefer concrete constraints and repeated patterns over adjectives.\n"
            "- If evidence conflicts, record the tension; do not average it away.\n"
            "- Do not infer sensitive identity, health diagnoses, or hidden facts.\n"
            "- Use at most 6 items per list and leave uncertainty visible.\n"
            f"Update reason: {reason}\n"
            f"Previous model:\n{json.dumps(current, ensure_ascii=False)[:6000]}\n"
            f"Evidence:\n{evidence_block}"
        )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "You maintain an evidence-bound human model. Output valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2600,
        )
        parsed = _extract_json((response.choices[0].message.content or "").strip())
        if not parsed:
            current["last_refresh_error"] = "Model returned invalid profile JSON."
            self.save(current)
            return current

        parsed["version"] = 1
        parsed["updated_at"] = _now()
        parsed["observations"] = len(events)
        parsed["refresh_reason"] = reason
        result = self._normalize(parsed)
        self.save(result)
        return result

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        base = _default_profile()
        base.update(data)
        try:
            base["confidence"] = max(0.0, min(1.0, float(base.get("confidence", 0))))
        except (TypeError, ValueError):
            base["confidence"] = 0.0
        for field in self._LIST_FIELDS:
            value = base.get(field)
            base[field] = value[:6] if isinstance(value, list) else []
        if not isinstance(base.get("revisions"), list):
            base["revisions"] = []
        base["revisions"] = base["revisions"][-8:]
        base["summary"] = str(base.get("summary") or _default_profile()["summary"])[:1200]
        return base
