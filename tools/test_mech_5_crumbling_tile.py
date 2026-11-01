"""Checks for the crumbling tile (mech-5-crumbling-tile).

Level-structure checks live here from the test-level task; the
mechanic behaviour checks (pure GameCore step under Node) join in
the implement-mechanic task.

Run with: python -m unittest tools.test_mech_5_crumbling_tile -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

LEVEL_ID = "mech-5-crumbling-tile-room"


class CrumblingRoomLevelTests(unittest.TestCase):
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
        self.assertIn("P", grid)
        # The crossing is a 3-tile crumbling bridge in the divider.
        bridge_row = next(r for r in rows if "CCC" in r)
        self.assertEqual(bridge_row.count("C"), 3)
        # An orb on the far side and one worth returning for.
        self.assertGreaterEqual(grid.count("*"), 2)
        bridge_y = rows.index(bridge_row)
        far_orb = [(x, y) for y, r in enumerate(rows)
                   for x, ch in enumerate(r) if ch == "*"]
        bridge_xs = [x for x, ch in enumerate(bridge_row) if ch == "C"]
        self.assertTrue(any(x > max(bridge_xs) for x, _ in far_orb),
                        "no orb beyond the bridge")
        # The long way back: the bottom row crosses the divider line
        # on plain floor, so a burned bridge never soft-locks the room.
        bottom = rows[-2]
        self.assertEqual(bottom[min(bridge_xs):max(bridge_xs) + 1],
                         "." * len(bridge_xs))


if __name__ == "__main__":
    unittest.main()
