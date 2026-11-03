"""Checks for the guarded orb (mech-19-guarded-orb).

The mechanic lives in the pure GameCore step (packs/guarded-orb);
driven here under Node against the teaching room and synthetic
mini-rooms. Rules (orbs.yml #19): within two tiles it steps one
tile away to a free floor tile, once per move; it cannot enter
walls or water; driven against a wall it can be stepped on.

Run with: python -m unittest tools.test_mech_19_guarded_orb -v
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

LEVEL_ID = "mech-19-guarded-orb-room"


class GuardedRoomLevelTests(unittest.TestCase):
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
        self.assertIn("Q", grid)
        self.assertIn("~", grid)
        self.assertEqual(self.level["legend"]["Q"]["def"],
                         "guarded:guarded-orb")


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function orbOf(s) {
  for (let y = 0; y < s.objects.length; y++)
    for (let x = 0; x < s.objects[y].length; x++)
      if (s.objects[y][x] === 'guarded:guarded-orb') return { x, y };
  return null;
}
function run(seq, lvl, name) {
  let s = core.initialState(lvl || level, name || 'mech-19-guarded-orb-room');
  const snap = () => ({ pos: { ...s.player }, orb: orbOf(s),
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const WIN = ['down', ...Array(10).fill('right')];
const win = run(WIN);
const chase = run(['right', 'right', 'right', 'right', 'right', 'right']);
const legend = { '.': { label: 'floor', sprite: 'floor_default.png' },
  '#': { label: 'wall', sprite: 'wall.png' },
  'P': { base: 'floor_default.png', label: 'player', sprite: 'jolly.png' },
  'Q': { base: 'floor_default.png', label: 'guarded orb',
    sprite: 'guarded-orb.png', def: 'guarded:guarded-orb' },
  '~': { base: 'floor_default.png', label: 'water', def: 'water:water' } };
const waterLevel = { name: 'water-mini', time_limit: 120, legend,
  rows: ['#######', '#P.Q~.#', '#######'] };
const water = run(['right', 'right'], waterLevel, 'water-mini');
const s0 = core.initialState(level, 'mech-19-guarded-orb-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ win, chase, water,
  fresh: (() => { const f = core.initialState(level,
    'mech-19-guarded-orb-room');
    return { pos: { ...f.player }, orb: orbOf(f),
      orbs: core.readout(f).orbs_left }; })(),
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GuardedMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_boundary_stays_at_three_steps_at_two(self):
        chase = self.r["chase"]
        # Player (3,1) is three tiles from the orb: it stays still.
        self.assertEqual(chase[2]["orb"], {"x": 6, "y": 2})
        # Player (4,1) is two away: exactly one flee step.
        self.assertEqual(chase[3]["orb"], {"x": 7, "y": 2})
        # Once per move: each later approach move shifts it by one.
        self.assertEqual(chase[4]["orb"], {"x": 8, "y": 2})

    def test_adversarial_direct_chase_never_collects_in_open(self):
        chase = self.r["chase"]
        for snap in chase:
            self.assertEqual(snap["orbs"], 1)
            self.assertEqual(snap["status"], "playing")
        # Not stranded: the player kept moving every turn.
        self.assertEqual(chase[-1]["pos"], {"x": 7, "y": 1})

    def test_solution_herd_against_wall_then_collect(self):
        win = self.r["win"]
        self.assertEqual(win[8]["orb"], {"x": 11, "y": 2})
        # Against the right wall it has no farther tile and stays.
        self.assertEqual(win[9]["orb"], {"x": 11, "y": 2})
        self.assertEqual(win[10]["orb"], {"x": 11, "y": 2})
        self.assertIsNone(win[11]["orb"])
        self.assertEqual(win[11]["orbs"], 0)

    def test_water_closes_the_flee_direction(self):
        water = self.r["water"]
        # The only farther tile is water, so the orb holds its tile.
        self.assertEqual(water[1]["orb"], {"x": 3, "y": 1})
        # Cornered by water, it can then be stepped on.
        self.assertIsNone(water[2]["orb"])
        self.assertEqual(water[2]["orbs"], 0)

    def test_parked_block_closes_the_escape(self):
        self.skipTest("blocked-by: 81 (push block) — push-block pack "
                      "is not built on this branch, so no block can be "
                      "parked on the escape tile yet")

    def test_restart_restores_the_orb(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1},
                          "orb": {"x": 6, "y": 2}, "orbs": 1})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wiring_renders_the_pack(self):
        js = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("packs/guarded-orb/main.js", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/guarded-orb/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', ...Array(10).fill('right')];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-19-guarded-orb-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-19-guarded-orb-room', log);
const replayed2 = core.replay(level, 'mech-19-guarded-orb-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1 }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_herding_session_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 11, "y": 2}, "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 11)


if __name__ == "__main__":
    unittest.main()
