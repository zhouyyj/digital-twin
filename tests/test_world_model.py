from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.life_path import LifePathEngine, _default_seed
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

    def test_profile_detects_old_non_english_content(self) -> None:
        model = TwinModel.__new__(TwinModel)
        self.assertTrue(model.needs_english_migration({"summary": "仍在寻找方向"}))
        self.assertFalse(model.needs_english_migration({"summary": "Still finding a direction"}))

    def test_life_path_language_check_ignores_archived_wording(self) -> None:
        engine = LifePathEngine.__new__(LifePathEngine)
        english_current = {
            "summary": "Three possible lives.",
            "today_label": "You, here",
            "past": {"trunk": [], "closed": []},
            "future": {"months": []},
            "history": [{"summary": "旧预测应保持原样"}],
        }
        self.assertFalse(engine.needs_english_migration(english_current))
        english_current["today_label"] = "寻找工作"
        self.assertTrue(engine.needs_english_migration(english_current))

    def test_legacy_commitment_keeps_choice_without_chinese_display_text(self) -> None:
        migrated = LifePathEngine._english_commitment(
            {
                "node_id": "m1_a",
                "label": "寻找工作",
                "detail": "投递三份简历",
                "status": "active",
            }
        )
        self.assertEqual(migrated["node_id"], "m1_a")
        self.assertEqual(migrated["label"], "Committed path (legacy)")
        self.assertNotIn("投递", migrated["detail"])

    def test_failed_language_regeneration_uses_english_fallback_and_archives_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "life.json"
            original = _default_seed(UserState.default())
            original["trigger"] = "manual"
            original["summary"] = "旧的中文预测"
            path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            engine = LifePathEngine(
                object(), _Memory(), UserState.default(), path=path, model="unused"
            )

            def fail_regeneration(**_kwargs):
                raise RuntimeError("offline")

            engine.regenerate = fail_regeneration
            migrated = engine.migrate_to_english()
            self.assertFalse(engine.needs_english_migration(migrated))
            self.assertEqual(migrated["trigger"], "language-migration-fallback")
            self.assertEqual(migrated["history"][-1]["summary"], "旧的中文预测")
            self.assertEqual(migrated["history"][-1]["reason"], "language-migration")

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
