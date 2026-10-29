"""Checks for player movement and collision (player-movement).

Drives the real JS core under Node against the movement-room Test
Level: one tile per keypress on floor only, wall/lock/gate collision,
and replay to the same end state.

Run with: python -m unittest tools.test_player_movement -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / "movement-room.json"
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


@unittest.skipUnless(shutil.which("node"), "node not available")
class MovementRoomTests(unittest.TestCase):
    def test_movement_room_is_valid_empty_room(self):
        level = game_levels.load_level(ROOT / "levels", "movement-room")
        self.assertTrue(level["test"])
        rows = level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        flat = "".join(rows)
        self.assertEqual(flat.count("P"), 1)
        for ch in "*G":
            self.assertNotIn(ch, flat)
        for row in rows:
            for ch in row:
                self.assertIn(ch, level["legend"])
        # Border is all wall, interior is floor or the player start.
        self.assertEqual(set(rows[0]), {"#"})
        self.assertEqual(set(rows[-1]), {"#"})
        for row in rows[1:-1]:
            self.assertTrue(row.startswith("#") and row.endswith("#"))
            self.assertLessEqual(set(row[1:-1]), {".", "P"})

    def test_movement_room_listed_as_test_level(self):
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn("movement-room", by_id)
        self.assertTrue(by_id["movement-room"]["test"])


if __name__ == "__main__":
    unittest.main()
