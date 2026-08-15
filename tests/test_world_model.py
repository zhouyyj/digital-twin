from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.life_path import LifePathEngine
from core.state_machine import UserState
from core.twin_model import TwinModel


class _Memory:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def add_event(self, text: str, event_type: str, **_kwargs) -> str:
        self.events.append((text, event_type))
        return "event-1"


class WorldModelTests(unittest.TestCase):
    def test_profile_normalization_keeps_uncertainty_bounded(self) -> None:
        model = TwinModel.__new__(TwinModel)
        profile = model._normalize(
            {
                "confidence": 4.2,
                "summary": "specific",
                "constraints": list(range(12)),
                "unknowns": "not-a-list",
            }
        )
        self.assertEqual(profile["confidence"], 1.0)
        self.assertEqual(len(profile["constraints"]), 6)
        self.assertEqual(profile["unknowns"], [])

    def test_constraint_normalization_does_not_invent_precision(self) -> None:
        engine = LifePathEngine.__new__(LifePathEngine)
        months = [
            {
                "month": 1,
                "nodes": [
                    {
                        "id": "a",
                        "plausibility": "maybe",
                        "plausibility_confidence": 8,
                        "pressure": {"money": "HIGH", "energy": 7},
                    }
                ],
            }
        ]
        engine._normalize_constraints(months)
        node = months[0]["nodes"][0]
        self.assertEqual(node["plausibility"], "unknown")
        self.assertEqual(node["plausibility_confidence"], 1.0)
        self.assertEqual(node["pressure"]["money"], "high")
        self.assertEqual(node["pressure"]["energy"], "unknown")
        self.assertEqual(node["pressure"]["coordination"], "unknown")

    def test_commitment_is_recorded_as_choice_not_reality(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "life.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "trigger": "test",
                        "summary": "test",
                        "today_label": "today",
                        "past": {"trunk": [], "closed": []},
                        "future": {
                            "months": [
                                {
                                    "month": 1,
                                    "nodes": [
                                        {
                                            "id": "m1_a",
                                            "label": "Try it",
                                            "detail": "A test world",
                                            "plausibility": "strained",
                                            "plausibility_confidence": 0.8,
                                            "pressure": {"money": "medium"},
                                        }
                                    ],
                                },
                                {"month": 2, "nodes": []},
                            ]
                        },
                        "history": [],
                        "meta": {"horizon_months": 2},
                    }
                ),
                encoding="utf-8",
            )
            memory = _Memory()
            engine = LifePathEngine(
                object(), memory, UserState.default(), path=path, model="unused"
            )
            result = engine.commit("m1_a")
            self.assertEqual(result["commitment"]["status"], "active")
            self.assertNotIn("actual_state", result["commitment"])
            self.assertEqual(memory.events[0][1], "Choice_Commitment")


if __name__ == "__main__":
    unittest.main()
