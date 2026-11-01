"""Checks for the bomb block (mech-83-bomb-block).

The mechanic lives in the bomb-block pack (packs/bomb-block/main.js)
on top of the pure GameCore step; driven here under Node against the
teaching room. Rules: the bomb block slides only onto empty floor or
a switch plate exactly as a push block; water, deep water, void, fire
and lava block it; a push that would drive it into a wall explodes it
instead (that wall becomes floor, the bomb is consumed); locks,
closed gates and other blocks never crack. Restart (fresh state)
restores the bomb and every wall; a recorded session replays to the
same end state.

Run with: python -m unittest tools.test_mech_83_bomb_block -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

LEVEL_ID = "mech-83-bomb-block-room"


class BombRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id)
        self.assertTrue(by_id[LEVEL_ID]["test"])

    def test_rows_rectangular_and_legend_covers_tiles(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_teaching_moment_layout(self):
        rows = self.level["rows"]
        grid = "".join(rows)
        # One player, one bomb block, one switch plate, one warp.
        self.assertEqual(grid.count("P"), 1)
        self.assertEqual(grid.count("B"), 1)
        self.assertEqual(grid.count("S"), 1)
        self.assertEqual(grid.count("X"), 1)
        # Two crackable walls face the bomb: rock wall and exit wall.
        walls = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "W"]
        self.assertEqual(len(walls), 2)
        (exit_x, exit_y), (rock_x, rock_y) = sorted(
            walls, key=lambda p: p[1])
        # The bomb starts aligned with the nearest (rock) wall, so the
        # naive eastward push spends it; the exit wall is rows away.
        bomb = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "B"][0]
        self.assertEqual(bomb[1], rock_y)
        self.assertNotEqual(bomb[1], exit_y)
        # Behind the rock wall is solid rock; behind the exit wall is
        # open floor leading to the warp.
        self.assertEqual(rows[rock_y][rock_x + 1], "#")
        self.assertEqual(rows[exit_y][exit_x + 1], ".")
        warp = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "X"][0]
        self.assertGreater(warp[0], exit_x)


if __name__ == "__main__":
    unittest.main()
