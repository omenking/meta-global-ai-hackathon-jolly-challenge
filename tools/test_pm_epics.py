"""Focused checks for PM epics (Epic -> Feature -> Task).

Run with: python -m unittest tools.test_pm_epics -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pm_store import (StoreError, archive_epic, create_epic, create_feature,
                      epic_progress, get_epic, load_pm, save_pm,
                      update_epic, update_feature)

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "tools" / "web" / "src" / "App.jsx"


def _data():
    data = {"features": [], "epics": []}
    create_epic(data, "base-game", "Base game")
    create_epic(data, "mechanic-sanity-checks", "Mechanic sanity checks")
    return data


class EpicStoreTests(unittest.TestCase):
    def test_create_assign_and_progress(self):
        data = _data()
        create_feature(data, "game-shell", "Shell", epic="base-game")
        create_feature(data, "mech-1-ice-tile", "Ice", epic="mechanic-sanity-checks")
        create_feature(data, "loose", "Loose")
        self.assertEqual(
            epic_progress(data, "base-game"),
            {"features": 1, "completed": 0, "tasks_done": 0, "tasks_total": 0})
        update_feature(data, "loose", {"epic": "mechanic-sanity-checks"})
        self.assertEqual(epic_progress(data, "mechanic-sanity-checks")["features"], 2)
        update_feature(data, "loose", {"epic": None})
        self.assertEqual(epic_progress(data, "mechanic-sanity-checks")["features"], 1)
        self.assertIsNone(
            [f for f in data["features"] if f["id"] == "loose"][0]["epic"])

    def test_unknown_epic_rejected(self):
        data = _data()
        with self.assertRaises(StoreError):
            create_feature(data, "x", "X", epic="nope")
        create_feature(data, "y", "Y")
        with self.assertRaises(StoreError):
            update_feature(data, "y", {"epic": "nope"})
        with self.assertRaises(StoreError):
            create_epic(data, "base-game", "Dup")
        with self.assertRaises(StoreError):
            create_epic(data, "ok-id", "   ")

    def test_update_and_archive_epic(self):
        data = _data()
        e = update_epic(data, "base-game", {"title": "Base game engine"})
        self.assertEqual(e["title"], "Base game engine")
        archive_epic(data, "base-game")
        self.assertTrue(get_epic(data, "base-game")["archived"])

    def test_roundtrip_preserves_epics(self):
        data = _data()
        create_feature(data, "game-shell", "Shell", epic="base-game")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pm.yml"
            save_pm(data, "", path)
            loaded, _ = load_pm(path)
        self.assertEqual([e["id"] for e in loaded["epics"]],
                         ["base-game", "mechanic-sanity-checks"])
        self.assertEqual(loaded["features"][0]["epic"], "base-game")


class EpicUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = APP.read_text(encoding="utf-8")

    def test_epics_page_and_epic_column_exist(self):
        self.assertIn("/pm/epics", self.src)
        self.assertIn("function EpicsPage", self.src)
        self.assertIn("function EpicShow", self.src)
        row = self.src[self.src.index("function FeatureRow"):self.src.index("function Board")]
        self.assertIn("feature.epic", row)


if __name__ == "__main__":
    unittest.main()
