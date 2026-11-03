"""Checks for the patroller (mech-31-patroller).

The mechanic lives in the pure GameCore step (packs/patroller);
driven here under Node against the teaching room. Rules: one
tile per player move along its marked loop forever; touching it
(or it touching you, including swapping tiles) returns you to
the level start; its loop never changes unless a mirror block
redirects it (mech-84, blocked-by); restart (fresh state)
restores the patroller to its placed loop position and a
recorded session replays to the same end state.

Run with: python -m unittest tools.test_mech_31_patroller -v
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

LEVEL_ID = "mech-31-patroller-room"


class PatrollerRoomLevelTests(unittest.TestCase):
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
        self.assertIn("A", grid)  # the patroller spawn
        # Marked loop tiles in the patroller column plus the loop
        # cell inside the corridor row.
        self.assertEqual(grid.count("L"), 6)
        self.assertGreaterEqual(grid.count("*"), 1)
        self.assertIn("X", grid)
        # The corridor row is the only crossing of the divider.
        divider_x = rows[5].index("L")
        blocked = [r[divider_x + 1] for r in rows]
        self.assertEqual(blocked.count("#"), len(rows) - 1)
        self.assertEqual(blocked[5], ".")
        # The loop is a closed ordered cycle of adjacent cells.
        loop = [tuple(p) for p in self.level["patroller_loop"]]
        self.assertEqual(len(loop), 12)
        for a, b in zip(loop, loop[1:] + loop[:1]):
            self.assertEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)


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
  let s = core.initialState(level, 'mech-31-patroller-room');
  const pat = () => { const a = s.actors.find((a) => a.def === 'patroller:patroller');
    return { x: a.x, y: a.y }; };
  const snap = () => ({ pos: { ...s.player }, pat: pat(),
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const R = 'right', L = 'left';
// Naive: walk straight across without timing the loop.
// Timed: bump-wait two beats at the start wall, then cross.
// Three plain moves for the one-tile-per-move check.
// A long straight run for the loop-cycle check.
const naive = run(Array(12).fill(R));
const timed = run([L, L, ...Array(11).fill(R)]);
const three = run([R, R, R]);
const cycle = run(Array(24).fill(L));
const s0 = core.initialState(level, 'mech-31-patroller-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  naive: naive.snaps, timed: timed.snaps, three: three.snaps,
  cycle: cycle.snaps.map((s) => s.pat),
  timedFinal: { pos: { ...timed.final.player },
    orbs: core.readout(timed.final).orbs_left,
    status: timed.final.status },
  freshPat: (() => { const f = core.initialState(level,
    'mech-31-patroller-room');
    const a = f.actors.find((a) => a.def === 'patroller:patroller');
    return { x: a.x, y: a.y }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class PatrollerMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_adversarial_straight_crossing(self):
        # YAML: 'adversarial straight crossing' — walk straight
        # across without timing the loop and be touched; the
        # player returns to the level start and can retry.
        n = self.r["naive"]
        self.assertEqual(n[0]["pos"], {"x": 1, "y": 5})
        self.assertEqual(n[4]["pos"], {"x": 5, "y": 5})
        # Step 5 meets the patroller on the crossing cell (6,5):
        # the player is back at the start, still playing.
        self.assertEqual(n[5]["pat"], {"x": 6, "y": 5})
        self.assertEqual(n[5]["pos"], {"x": 1, "y": 5})
        self.assertEqual(n[5]["status"], "playing")
        # Never stranded: the retry walks again from the start.
        self.assertEqual(n[6]["pos"], {"x": 2, "y": 5})
        self.assertEqual(n[6]["status"], "playing")

    def test_timed_corridor_crossing(self):
        # YAML: 'timed corridor crossing' — wait for the patroller
        # to pass, then cross in the gap and reach the far side.
        t = self.r["timed"]
        self.assertEqual(t[2]["pos"], {"x": 1, "y": 5})  # waited
        self.assertEqual(self.r["timedFinal"],
                         {"pos": {"x": 12, "y": 5}, "orbs": 0,
                          "status": "won"})
        # The player crossed the patroller column alive.
        self.assertTrue(any(s["pos"] == {"x": 7, "y": 5} for s in t))

    def test_one_tile_per_player_move(self):
        # YAML: 'one tile per player move' — three player moves
        # advance the patroller exactly three tiles along its loop.
        pats = [s["pat"] for s in self.r["three"]]
        self.assertEqual(pats, [{"x": 6, "y": 6}, {"x": 6, "y": 7},
                                {"x": 6, "y": 8}, {"x": 6, "y": 7}])

    def test_loop_unchanged_without_mirror(self):
        # YAML: 'loop only changes by mirror' (first half) —
        # without a mirror block the loop is unchanged after any
        # number of moves: the 24-step run is two identical cycles.
        cycle = self.r["cycle"]
        self.assertEqual(len(cycle), 25)
        self.assertEqual(cycle[0], {"x": 6, "y": 6})
        self.assertEqual(cycle[12], cycle[0])
        self.assertEqual(cycle[24], cycle[0])
        self.assertEqual(cycle[1:13], cycle[13:25])

    @unittest.skip("blocked-by: 84 (mirror block) — the loop "
                   "redirect half of 'loop only changes by mirror' "
                   "needs the mirror block mechanic, not built here")
    def test_loop_redirected_by_mirror_block(self):
        pass

    def test_restart_restores_the_patroller(self):
        self.assertEqual(self.r["freshPat"], {"x": 6, "y": 6})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_the_patroller_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("actorSprites", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/patroller/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['left', 'left', ...Array(11).fill('right')];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-31-patroller-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-31-patroller-room', log);
const replayed2 = core.replay(level, 'mech-31-patroller-room',
  JSON.parse(JSON.stringify(log)));
const patOf = (s) => { const a = s.actors.find(
  (a) => a.def === 'patroller:patroller'); return { x: a.x, y: a.y }; };
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
  livePat: patOf(live),
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        # YAML: 'restart and replay' — a recorded crossing session
        # replays to the same end state.
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 12, "y": 5}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 13)


if __name__ == "__main__":
    unittest.main()
