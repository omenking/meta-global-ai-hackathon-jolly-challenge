"""Checks for the crumbling tile (mech-5-crumbling-tile).

The mechanic lives in the pure GameCore step (packs/crumbling.js);
driven here under Node against the teaching room. Rules: safe while
stood on, falls one move after leaving, void blocks, stepping back
in time disarms, restart (fresh state) restores.

Run with: python -m unittest tools.test_mech_5_crumbling_tile -v
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


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-5-crumbling-tile-room');
  const snaps = [{ pos: { ...s.player }, row: s.grid[2] }];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push({ pos: { ...s.player }, row: s.grid[2],
      orbs: core.readout(s).orbs_left });
  });
  return { snaps, final: s };
}
const toBridge = ['right', 'right', 'right', 'down'];
// A: cross the bridge one tile at a time.
const a = run([...toBridge, 'right', 'right', 'right', 'right', 'up']);
// B: stand on the middle bridge tile and push into the wall twice.
const b = run([...toBridge, 'right', 'right', 'up', 'up', 'right']);
// C: step off the first bridge tile and straight back on.
const c = run([...toBridge, 'right', 'left', 'right', 'up', 'right']);
// D: cross, take the far orb, fail back over the void, long way home.
const d = run([...toBridge, 'right', 'right', 'right', 'right',
  'up', 'right', 'right', 'left', 'left', 'down', 'left',
  'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left',
  'up', 'up', 'up', 'up', 'up', 'left']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-5-crumbling-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, d: d.snaps,
  dFinal: { pos: { ...d.final.player },
    orbs: core.readout(d.final).orbs_left },
  freshRow: core.initialState(level,
    'mech-5-crumbling-tile-room').grid[2],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class CrumblingMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_bridge_intact_until_crossed(self):
        # snaps[4] stands before the bridge at (4,2).
        self.assertEqual(self.r["a"][4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(self.r["a"][4]["row"], "#....CCC....#")

    def test_falls_one_move_after_leaving_not_on_leaving(self):
        a = self.r["a"]
        # On C2 (6,2): the tile just left (5,2) is still standing.
        self.assertEqual(a[6]["pos"], {"x": 6, "y": 2})
        self.assertEqual(a[6]["row"], "#....CCC....#")
        # On C3 (7,2), one move later: (5,2) has fallen to void.
        self.assertEqual(a[7]["row"], "#....VCC....#")
        # Off the bridge at (8,2): (6,2) has fallen, (7,2) has not yet.
        self.assertEqual(a[8]["row"], "#....VVC....#")
        # One more move: the whole bridge is void.
        self.assertEqual(a[9]["row"], "#....VVV....#")

    def test_safe_while_standing_on_it(self):
        b = self.r["b"]
        # Two blocked pushes into the wall: still on C2, and C2 itself
        # is intact (the tile behind, already left, has fallen).
        self.assertEqual(b[8]["pos"], {"x": 6, "y": 2})
        self.assertEqual(b[8]["row"], "#....VCC....#")
        self.assertEqual(b[8]["row"][6], "C")
        # And it still carries the player onward.
        self.assertEqual(b[9]["pos"], {"x": 7, "y": 2})

    def test_stepping_back_on_disarms_the_fall(self):
        c = self.r["c"]
        # Off C1 and back on, then a blocked push: C1 never fell.
        self.assertEqual(c[8]["pos"], {"x": 5, "y": 2})
        self.assertEqual(c[8]["row"], "#....CCC....#")
        self.assertEqual(c[9]["pos"], {"x": 6, "y": 2})

    def test_void_blocks_return_and_long_way_home_works(self):
        d = self.r["d"]
        # snaps[15] pressed left from (8,2) into the void: no move.
        self.assertEqual(d[14]["pos"], {"x": 8, "y": 2})
        self.assertEqual(d[15]["pos"], {"x": 8, "y": 2})
        self.assertEqual(d[15]["row"], "#....VVV....#")
        # Long way home collects the return orb and reaches the start.
        self.assertEqual(self.r["dFinal"],
                         {"pos": {"x": 1, "y": 1}, "orbs": 0})

    def test_restart_restores_the_bridge(self):
        self.assertEqual(self.r["freshRow"], "#....CCC....#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_void_instead_of_floor(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("gc === 'C' || gc === 'V'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/crumbling.js", html)


if __name__ == "__main__":
    unittest.main()
