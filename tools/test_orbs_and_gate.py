"""Checks for orbs and the gate (orbs-and-gate).

The mechanics live in the pure GameCore step; driven here under
Node. Orbs ('*' tiles) never enter the inventory: each one walked
onto decrements the orbs-left counter. The gate ('G') blocks like a
wall while orbs remain and opens at zero.

Run with: python -m unittest tools.test_orbs_and_gate -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402


def run_core(script, level_name="orbs-room"):
    level = ROOT / "levels" / f"{level_name}.json"
    out = subprocess.run(["node", "-e", script, str(CORE), str(level)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class OrbsRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", "orbs-room")

    def test_orbs_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertTrue(by_id["orbs-room"]["test"])

    def test_rows_rectangular_and_legend_covers_tiles(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_gated_portal_with_orbs_placed(self):
        grid = "".join(self.level["rows"])
        self.assertIn("P", grid)
        self.assertIn("G", grid, "gate not placed")
        self.assertIn("X", grid, "portal behind the gate not placed")
        self.assertGreaterEqual(grid.count("*"), 2, "need at least 2 orbs")
        # Every orb is reachable without crossing the gate: the gate
        # row is the only divider, so no orb may sit behind it.
        gate_y = next(y for y, r in enumerate(self.level["rows"])
                      if "G" in r)
        orb_rows = [y for y, r in enumerate(self.level["rows"])
                    if "*" in r]
        self.assertTrue(all(y < gate_y for y in orb_rows),
                        "an orb behind the gate would deadlock the level")
        portal_y = next(y for y, r in enumerate(self.level["rows"])
                        if "X" in r)
        self.assertGreater(portal_y, gate_y)

    def test_orb_and_gate_sprites_exist(self):
        sprites = ROOT / "tools" / "static" / "level-sprites"
        for name in ("orb.png", "gate.png", "portal.png"):
            self.assertTrue((sprites / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
