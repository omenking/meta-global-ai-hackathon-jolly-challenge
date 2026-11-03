"""Checks for the ice block (mech-82-ice-block).

The mechanic lives in the pure GameCore step (packs/ice-block);
driven here under Node against the teaching room. Rules: one push
slides the block over floor and ice until a wall, lock, gate or
other block stops it; fire (local ice:fire stand-in for mech 43)
melts and consumes it and leaves scorched floor; lava, deep
water and void destroy it with the tile unchanged; shallow water
(local ice:shallow stand-in for mech 50) stops it as an ice
bridge; restart (fresh state) restores every tile.

YAML test_cases coverage: adversarial nearest-wall overshoot,
slide stops only at a blocker, and restart+replay are covered
directly. The two cases the YAML marks blocked-by (43 fire tile,
50 ice bridge) get explicit skipped-with-reason checks for the
cross-mechanic integration; the same behaviours are exercised
here against the pack's local stand-in tiles, never faked as the
real 43/50 tiles.

Run with: python -m unittest tools.test_mech_82_ice_block -v
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

LEVEL_ID = "mech-82-ice-block-room"


class IceBlockRoomLevelTests(unittest.TestCase):
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
        # Ice block on the ice lane, orb lane beside its slide line.
        self.assertIn("I", rows[1])
        self.assertIn("i", rows[1])
        orb = [(x, y) for y, r in enumerate(rows)
               for x, ch in enumerate(r) if ch == "*"]
        self.assertTrue(any(y == 2 for _, y in orb),
                        "no orb in the lane beside the slide line")
        # One lane per hazard the slide can meet, plus a blocker lane.
        for ch in ("F", "~", "D", "A", "V"):
            self.assertIn(ch, grid)
        self.assertEqual(rows[13].count("I"), 2)


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
  let s = core.initialState(level, 'mech-82-ice-block-room');
  const snap = () => ({ pos: { ...s.player }, grid: [...s.grid],
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const downs = (n) => Array(n).fill('down');
// A: naive nearest-wall push on the ice lane (teaching failure).
const a = run(['right', 'right']);
// B: corrected slide into the fire, then cross scorched to warp.
const b = run(['down', 'down', 'right', 'right',
  ...Array(11).fill('right')]);
// C: stop-at-blocker lane, then push again against the blocker.
const c = run([...downs(12), 'right', 'right',
  ...Array(6).fill('right'), 'right']);
// D: shallow lane (local stand-in): bridge, cross and return.
const d = run([...downs(4), 'right', 'right',
  ...Array(10).fill('right'), ...Array(10).fill('left')]);
// E/F/G: deep, lava and void lanes destroy the block.
const e = run([...downs(6), 'right', 'right']);
const f = run([...downs(8), 'right', 'right']);
const g = run([...downs(10), 'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-82-ice-block-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ a, b, c, d, e, f, g,
  fresh: core.initialState(level, 'mech-82-ice-block-room').grid,
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class IceBlockMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_adversarial_nearest_wall_overshoot(self):
        a = self.r["a"]
        # It slides the whole way past the orb lane to the far wall.
        self.assertEqual(a[2]["grid"][1], "#P.iiiiiiii....I#")
        self.assertEqual(a[2]["pos"], {"x": 2, "y": 1})
        self.assertEqual(a[2]["status"], "playing")

    def test_slide_stops_only_at_a_blocker(self):
        c = self.r["c"]
        # Across floor and ice, stopping only beside the blocker.
        self.assertEqual(c[14]["grid"][13], "#..i...i.II.....#")
        self.assertEqual(c[14]["pos"], {"x": 2, "y": 13})
        # Pushing again against the blocker: nothing moves.
        self.assertEqual(c[-1]["grid"][13], "#..i...i.II.....#")
        self.assertEqual(c[-1]["pos"], {"x": 8, "y": 13})
        self.assertEqual(c[-1]["status"], "playing")

    def test_local_fire_standin_cancels_to_scorched(self):
        b = self.r["b"]
        self.assertEqual(b[4]["grid"][3], "#..i....S...*X..#")
        self.assertEqual(b[4]["pos"], {"x": 2, "y": 3})
        # The corrected play crosses the scorched tile and wins.
        self.assertEqual(b[-1]["pos"], {"x": 13, "y": 3})
        self.assertEqual(b[-1]["status"], "won")

    def test_local_shallow_standin_becomes_a_bridge(self):
        d = self.r["d"]
        self.assertEqual(d[6]["grid"][5], "#..i....B.......#")
        # Crossing the bridge and coming back stays safe.
        self.assertEqual(d[-1]["pos"], {"x": 2, "y": 5})
        self.assertEqual(d[-1]["status"], "playing")

    def test_deep_lava_and_void_destroy_the_block(self):
        self.assertEqual(self.r["e"][-1]["grid"][7], "#..i....D.......#")
        self.assertEqual(self.r["f"][-1]["grid"][9], "#..i....A.......#")
        self.assertEqual(self.r["g"][-1]["grid"][11], "#..i....V.......#")
        for key in ("e", "f", "g"):
            self.assertEqual(self.r[key][-1]["status"], "playing")

    def test_restart_restores_every_tile(self):
        fresh = self.r["fresh"]
        self.assertEqual(fresh[1], "#P.Iiiiiiii.....#")
        self.assertEqual(fresh[3], "#..I....F...*X..#")
        self.assertEqual(fresh[5], "#..I....~.......#")
        self.assertEqual(fresh[13], "#..I...i..I.....#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_moved_blocks_and_transforms(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'I'", js)
        self.assertIn("packs/ice-block/main.js",
                      (ROOT / "tools" / "static" / "game.html")
                      .read_text(encoding="utf-8"))

    def test_block_sprite_is_raised_above_the_destination_floor(self):
        # Regression (qa-verification): board sprites are added in
        # row-major order, so a destination floor drawn after the
        # block's origin covers the block after an east/south slide;
        # the block looked picked up. The 'I' render branch must
        # bring its sprite to the front of its parent.
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        branch = js.split("dt.ch === 'I'", 1)[1].split("dt.ch === 'F'", 1)[0]
        self.assertIn("setChildIndex", branch)

    @unittest.skip("blocked-by: 43 (fire tile) is not built on main; "
                   "the pack's local ice:fire stand-in is covered by "
                   "test_local_fire_standin_cancels_to_scorched")
    def test_solution_slide_to_cancel_fire(self):
        pass

    @unittest.skip("blocked-by: 50 (ice bridge) is not built on main; "
                   "the pack's local ice:shallow stand-in is covered "
                   "by test_local_shallow_standin_becomes_a_bridge, and "
                   "deep/void destruction by "
                   "test_deep_lava_and_void_destroy_the_block")
    def test_water_and_void_boundaries(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'down', 'right', 'right',
  ...Array(11).fill('right')];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-82-ice-block-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-82-ice-block-room', log);
const replayed2 = core.replay(level, 'mech-82-ice-block-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row: replayed[replayed.length - 1].grid[3],
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 13, "y": 3}, "orbs": 1,
                          "status": "won"})
        self.assertEqual(self.r["row"], "#..i....S....X..#")
        self.assertEqual(self.r["replaySteps"], 15)


if __name__ == "__main__":
    unittest.main()
