"""Checks for the ghost (mech-78-ghost).

The mechanic lives in the pure GameCore step (packs/ghost/main.js);
driven here under Node against the teaching room. Rules: stepping
into the ghost pit ends the attempt and records its route; on the
next attempt a ghost replays that route one step behind; touching
or head-on crossing a ghost ends the attempt and adds another
ghost; ghosts pass through each other; a ghost fades when its
replay ends; a fresh initialState (restart) clears every ghost.

Run with: python -m unittest tools.test_mech_78_ghost -v
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

LEVEL_ID = "mech-78-ghost-room"


class GhostRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(self.level["legend"]["H"]["def"], "ghost:pit")
        # The failed-attempt corridor: spawn west, pit at the east end.
        corridor = rows[1]
        self.assertTrue(corridor.startswith("#P"))
        self.assertTrue(corridor.endswith("H#"))
        # A corrected line exists: the lower rows cross the whole
        # room on plain floor to the warp, never touching the pit row.
        self.assertIn("X", grid)
        warp = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "X"]
        self.assertEqual(warp, [(13, 6)])
        self.assertGreaterEqual(grid.count("*"), 2)


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function snap(s) {
  return { pos: { ...s.player }, status: s.status,
    deaths: (s.counters || {})['ghost:deaths'] || 0,
    orbs: core.readout(s).orbs_left,
    trails: (s.flags.ghost_trails || []).map((t) => t.length),
    ghosts: (s.flags.ghost_positions || []).map((g) =>
      ({ x: g.x, y: g.y, kind: g.kind, fading: g.fading })) };
}
function runSeq(s, seq, t0) {
  const snaps = [];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: t0 + (i + 1) * 100, input });
    snaps.push(snap(s));
  });
  return { s, snaps };
}
let s = core.initialState(level, 'mech-78-ghost-room');
const initial = snap(s);
// Attempt 1 (naive): east along the corridor into the pit.
const a1 = runSeq(s, Array(12).fill('right'), 0); s = a1.s;
// Attempt 2 (adversarial): repeat the route, then backtrack west
// into the ghost trailing one step behind.
const a2 = runSeq(s, ['right', 'right', 'left'], 1200); s = a2.s;
// Attempt 3 (corrected): lower bypass to the warp while the ghosts
// retrace the old corridor route.
const a3 = runSeq(s, ['down', 'down', ...Array(12).fill('right'),
  'down', 'down', 'down'], 1500); s = a3.s;
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-78-ghost-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  initial, a1: a1.snaps, a2: a2.snaps, a3: a3.snaps,
  pure: JSON.stringify(s0) === before,
  fresh: snap(core.initialState(level, 'mech-78-ghost-room')),
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GhostMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_no_ghosts_on_first_attempt(self):
        self.assertEqual(self.r["initial"]["ghosts"], [])
        self.assertEqual(self.r["initial"]["trails"], [])
        self.assertEqual(self.r["initial"]["deaths"], 0)

    def test_pit_ends_attempt_and_records_route(self):
        # Step 11 collects the corridor orb; step 12 steps into the
        # pit: the attempt ends, the player is back at the spawn,
        # orbs are restored, and the route became a ghost trail.
        self.assertEqual(self.r["a1"][10]["orbs"], 2)
        last = self.r["a1"][11]
        self.assertEqual(last["pos"], {"x": 1, "y": 1})
        self.assertEqual(last["deaths"], 1)
        self.assertEqual(last["orbs"], 3)
        self.assertEqual(last["trails"], [13])
        self.assertEqual(last["status"], "playing")

    def test_one_step_behind_exact(self):
        # YAML: 'one step behind and fades at the end' (offset part).
        # Attempt 2, step 1: the ghost is at the failed attempt's
        # start; step 2: at its first move — always one step behind.
        self.assertEqual(self.r["a2"][0]["ghosts"],
                         [{"x": 1, "y": 1, "kind": "start",
                           "fading": False}])
        self.assertEqual(self.r["a2"][1]["ghosts"],
                         [{"x": 2, "y": 1, "kind": "ghost",
                           "fading": False}])
        self.assertEqual(self.r["a2"][1]["pos"], {"x": 3, "y": 1})

    def test_adversarial_backtrack_meets_ghost_and_loses(self):
        # YAML: 'adversarial repeat the same route' — backtracking
        # west crosses the eastbound ghost head-on; the attempt ends
        # (never stranded: playing at the spawn, a second trail laid).
        last = self.r["a2"][2]
        self.assertEqual(last["deaths"], 2)
        self.assertEqual(last["pos"], {"x": 1, "y": 1})
        self.assertEqual(last["status"], "playing")
        self.assertEqual(last["trails"], [13, 4])

    def test_dodge_your_own_last_route(self):
        # YAML: 'dodge your own last route' (solution) — the lower
        # bypass reaches the warp while ghosts retrace the corridor.
        self.assertEqual(self.r["a3"][-1]["status"], "won")
        self.assertEqual(self.r["a3"][-1]["pos"], {"x": 13, "y": 6})
        # Mid-run the first ghost is on the old corridor route.
        self.assertIn({"x": 6, "y": 1, "kind": "ghost", "fading": False},
                      self.r["a3"][5]["ghosts"])

    def test_ghosts_share_a_tile_and_fade_in_turn(self):
        # Several ghosts can occupy the same tile (they pass through
        # each other): at attempt-3 step 2 both sit at (2,1).
        self.assertEqual(self.r["a3"][1]["ghosts"], [
            {"x": 2, "y": 1, "kind": "ghost", "fading": False},
            {"x": 2, "y": 1, "kind": "ghost", "fading": False}])
        # YAML: 'one step behind and fades at the end' (fade part) —
        # the short trail fades at step 5, the long one at step 14,
        # and both are gone before the win.
        self.assertTrue(any(g["fading"] for g in self.r["a3"][4]["ghosts"]))
        self.assertTrue(any(g["fading"] for g in self.r["a3"][13]["ghosts"]))
        self.assertEqual(self.r["a3"][16]["ghosts"], [])

    @unittest.skip("blocked-by: 48 (checkpoint) — ghosts restarting "
                   "from an active checkpoint is unbuilt; pass-through "
                   "itself is covered by "
                   "test_ghosts_share_a_tile_and_fade_in_turn")
    def test_ghosts_pass_through_each_other_checkpoint_case(self):
        # YAML: 'ghosts pass through each other' — blocked-by: 48.
        raise AssertionError("unreachable")

    def test_restart_clears_every_ghost(self):
        # YAML: 'restart and replay' (restart part) — a fresh state
        # has no trails, no ghosts and no deaths.
        self.assertEqual(self.r["fresh"]["trails"], [])
        self.assertEqual(self.r["fresh"]["ghosts"], [])
        self.assertEqual(self.r["fresh"]["deaths"], 0)

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_ghosts(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("ghost_positions", js)
        self.assertIn("ghost-jolly.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/ghost/main.js", html)


REPLAY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = [...Array(12).fill('right'), 'right', 'right', 'left',
  'down', 'down', ...Array(12).fill('right'), 'down', 'down', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-78-ghost-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-78-ghost-room', log);
const replayed2 = core.replay(level, 'mech-78-ghost-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  status: live.status, deaths: live.counters['ghost:deaths'],
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GhostReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(REPLAY_SCRIPT)

    def test_session_replays_to_same_end_state(self):
        # YAML: 'restart and replay' (replay part).
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["status"], "won")
        self.assertEqual(self.r["deaths"], 2)


if __name__ == "__main__":
    unittest.main()
