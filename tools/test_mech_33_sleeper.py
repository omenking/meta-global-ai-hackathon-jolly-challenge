"""Checks for the sleeper (mech-33-sleeper).

The mechanic lives in the sleeper pack (packs/sleeper/main.js);
driven here under Node against the teaching room. Rules: asleep
and solid on its tile until any orb anywhere is collected (not
tied to one specific orb); then it patrols its fixed marked loop
at one tile per player move, lethal on touch like a patroller
(touch returns the player to the level spawn, room retryable);
restart (fresh state) restores it asleep with no orb collected.

Run with: python -m unittest tools.test_mech_33_sleeper -v
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

LEVEL_ID = "mech-33-sleeper-room"


class SleeperRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("S"), 1)
        self.assertEqual(grid.count("*"), 2)
        s_pos = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "S"][0]
        orbs = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "*"]
        # Nearest orb sits in front (west) of the sleeping sleeper;
        # the safer orb is further away, beyond the loop.
        near = min(orbs, key=lambda p: abs(p[0] - s_pos[0]))
        far = max(orbs, key=lambda p: abs(p[0] - s_pos[0]))
        self.assertLess(near[0], s_pos[0])
        self.assertGreater(far[0], s_pos[0])
        # The marked loop is a closed cycle through the sleeper tile.
        loop = [tuple(p) for p in self.level["sleeper_loop"]]
        self.assertIn(s_pos, loop)
        self.assertGreaterEqual(len(loop), 8)
        for i, cell in enumerate(loop):
            nxt = loop[(i + 1) % len(loop)]
            self.assertEqual(abs(nxt[0] - cell[0]) + abs(nxt[1] - cell[1]), 1)
            self.assertIn(rows[cell[1]][cell[0]], "SL")
        # Gate and warp behind it: leaving needs both orbs.
        self.assertIn("G", grid)
        self.assertIn("X", grid)


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
  let s = core.initialState(level, 'mech-33-sleeper-room');
  const snap = () => {
    const a = s.actors.find((ac) => ac.def === 'sleeper:sleeper');
    return { pos: { ...s.player }, sl: { x: a.x, y: a.y },
      awake: !!s.flags['sleeper:awake'],
      orbs: core.readout(s).orbs_left, status: s.status };
  };
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// A: solution - collect the near orb, cross the loop interior in
// the gap, collect the far orb and leave through the gate.
const a = run(['down', 'right', 'right', 'right', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'right', 'right']);
// B: asleep tile is solid (no orb collected on this path), then
// the near orb wakes it and wall-waiting advances it 1/move.
const b = run(['right', 'right', 'right', 'right', 'down', 'right',
  'right']);
const b2 = run(['down', 'right', 'right', 'right', 'up', 'up', 'up']);
// C: adversarial - nearest orb first, then a careless crossing of
// the loop's bottom row head-on into the patrol.
const c = run(['down', 'right', 'right', 'right', 'down', 'down',
  'down', 'right', 'right', 'right', 'right']);
// D: any orb wakes it - the safer far orb first, near orb untouched.
const d = run(['down', 'down', 'down', 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'right', 'right', 'up', 'up', 'right', 'up', 'down']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-33-sleeper-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
const fresh = core.initialState(level, 'mech-33-sleeper-room');
const fa = fresh.actors.find((ac) => ac.def === 'sleeper:sleeper');
console.log(JSON.stringify({ a, b, b2, c, d,
  fresh: { sl: { x: fa.x, y: fa.y }, awake: !!fresh.flags['sleeper:awake'],
    orbs: core.readout(fresh).orbs_left },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SleeperMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_asleep_sleeper_is_solid_and_still(self):
        b = self.r["b"]
        # Along the top and down in front of it, then two pushes
        # east into its tile: no entry, no wake, no orb collected.
        self.assertEqual(b[5]["pos"], {"x": 5, "y": 2})
        self.assertEqual(b[6]["pos"], {"x": 5, "y": 2})
        self.assertEqual(b[7]["pos"], {"x": 5, "y": 2})
        self.assertEqual(b[7]["sl"], {"x": 6, "y": 2})
        self.assertFalse(b[7]["awake"])
        self.assertEqual(b[7]["orbs"], 2)

    def test_collect_then_cross_in_the_gap(self):
        a = self.r["a"]
        self.assertEqual(a[4]["orbs"], 1)
        self.assertTrue(a[4]["awake"])
        # Crossed the loop and left through the gate to the warp.
        self.assertEqual(a[-1]["pos"], {"x": 13, "y": 4})
        self.assertEqual(a[-1]["orbs"], 0)
        self.assertEqual(a[-1]["status"], "won")

    def test_patrols_one_tile_per_player_move(self):
        b2 = self.r["b2"]
        # Wake step: still on its tile. Three wall-waits after:
        # exactly three loop tiles advanced, no more and no fewer.
        self.assertEqual(b2[4]["sl"], {"x": 6, "y": 2})
        self.assertEqual(b2[5]["sl"], {"x": 7, "y": 2})
        self.assertEqual(b2[6]["sl"], {"x": 8, "y": 2})
        self.assertEqual(b2[7]["sl"], {"x": 9, "y": 2})
        self.assertEqual(b2[7]["pos"], {"x": 4, "y": 1})

    def test_adversarial_nearest_orb_first(self):
        c = self.r["c"]
        self.assertEqual(c[10]["pos"], {"x": 7, "y": 5})
        self.assertEqual(c[10]["sl"], {"x": 9, "y": 5})
        # Touched head-on: returned to the level start, still
        # playing (the collected orb stays collected), never stranded.
        self.assertEqual(c[11]["pos"], {"x": 1, "y": 1})
        self.assertEqual(c[11]["sl"], {"x": 8, "y": 5})
        self.assertEqual(c[11]["status"], "playing")
        self.assertEqual(c[11]["orbs"], 1)

    def test_any_orb_wakes_it(self):
        d = self.r["d"]
        # Far orb collected first: sleeper wakes on its tile even
        # though the near orb was never touched, then patrols.
        self.assertEqual(d[19]["orbs"], 1)
        self.assertTrue(d[19]["awake"])
        self.assertEqual(d[19]["sl"], {"x": 6, "y": 2})
        self.assertEqual(d[20]["sl"], {"x": 7, "y": 2})

    @unittest.skip("blocked-by: 38 (alarm tile): stepping on the "
                   "alarm wakes the sleeper without any orb; the "
                   "alarm tile mechanic is not built in this pack")
    def test_alarm_wakes_by_stepping(self):
        pass

    def test_restart_restores_asleep_sleeper(self):
        self.assertEqual(self.r["fresh"],
                         {"sl": {"x": 6, "y": 2}, "awake": False, "orbs": 2})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_awake_sleeper(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("sleeper-awake.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/sleeper/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'right', 'right', 'right', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-33-sleeper-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-33-sleeper-room', log);
const replayed2 = core.replay(level, 'mech-33-sleeper-room',
  JSON.parse(JSON.stringify(log)));
const last = replayed[replayed.length - 1];
const la = last.actors.find((ac) => ac.def === 'sleeper:sleeper');
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(last),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  sleeper: { x: la.x, y: la.y }, awake: !!last.flags['sleeper:awake'],
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
                         {"pos": {"x": 13, "y": 4}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 15)
        self.assertTrue(self.r["awake"])


if __name__ == "__main__":
    unittest.main()
