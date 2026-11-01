"""Checks for the blocker (mech-34-blocker).

The mechanic lives in the pure GameCore step (packs/blocker);
driven here under Node against the teaching room. Rules: the
blocker lives in its three-wide doorway strip, shuffles exactly
one tile per player move sideways tracking the player, never
leaves the strip and never changes row; beside/in the doorway it
is committed (guard window), so a feint crosses at the far side;
touch loses the attempt. Pin (mech 81) and decoy (mech 39) cases
are explicitly skipped: those mechanics are not built yet.

Run with: python -m unittest tools.test_mech_34_blocker -v
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

LEVEL_ID = "mech-34-blocker-room"


class BlockerRoomLevelTests(unittest.TestCase):
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
        doorway = next(r for r in rows if "B" in r)
        self.assertEqual(doorway, "#####DBD#####")
        self.assertEqual(doorway.count("D"), 2)
        self.assertEqual(doorway.count("B"), 1)
        self.assertGreaterEqual(grid.count("*"), 1)
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
function blockerX(s) { return s.grid[4].indexOf('B'); }
function run(seq) {
  let s = core.initialState(level, 'mech-34-blocker-room');
  const snap = () => ({ pos: { ...s.player }, row: s.grid[4],
    bx: blockerX(s), status: s.status,
    orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
// A: walk right along the top row; blocker tracks one tile/move.
const a = run(['right', 'right', 'right', 'right', 'right', 'right']);
// B: naive slip at the guarded column (x=6).
const b = run(['right', 'right', 'right', 'right', 'right',
  'down', 'down', 'down']);
// C: feint east from afar, walk up west, cross at x=5, orb, portal.
const c = run(['right', 'right', 'right', 'right', 'right', 'right',
  'down', 'down', 'left', 'left', 'down', 'down',
  'right', 'down', 'right', 'right', 'right', 'right', 'right',
  'down']);
// D: long walk to prove the blocker never leaves its strip/row.
const d = run(['right', 'right', 'right', 'right', 'right', 'right',
  'left', 'left', 'left', 'left', 'left', 'left',
  'right', 'right', 'right']);
const s0 = core.initialState(level, 'mech-34-blocker-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, d: d.snaps,
  cFinal: { pos: { ...c.final.player }, status: c.final.status,
    orbs: core.readout(c.final).orbs_left },
  freshRow: core.initialState(level,
    'mech-34-blocker-room').grid[4],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class BlockerMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_one_sideways_tile_per_move_inside_the_strip(self):
        # YAML: 'one sideways tile per move inside the strip'.
        a = self.r["a"]
        self.assertEqual(a[0]["bx"], 6)
        # First move west-of-strip: exactly one shuffle toward the
        # player's column (clamped at the strip's west edge).
        self.assertEqual(a[1]["bx"], 5)
        self.assertEqual(a[1]["row"], "#####BDD#####")
        for prev, cur in zip(a, a[1:]):
            self.assertLessEqual(abs(cur["bx"] - prev["bx"]), 1)
            self.assertIn(cur["bx"], (5, 6, 7))
            self.assertIn("B", cur["row"])

    def test_never_leaves_strip_and_never_changes_row(self):
        for snap in self.r["d"]:
            self.assertIn(snap["bx"], (5, 6, 7))
            self.assertEqual(snap["row"].count("B"), 1)
            self.assertTrue(snap["row"].startswith("#####"))
            self.assertTrue(snap["row"].endswith("#####"))

    def test_adversarial_slip_past_the_guarded_side(self):
        # YAML: 'adversarial slip past the guarded side' — mirrored
        # and touched; lost, and a fresh restart is never stranded.
        b = self.r["b"]
        self.assertEqual(b[7]["pos"], {"x": 6, "y": 3})
        self.assertEqual(b[7]["bx"], 6)
        self.assertEqual(b[8]["pos"], {"x": 6, "y": 4})
        self.assertEqual(b[8]["status"], "lost")
        self.assertEqual(self.r["freshRow"], "#####DBD#####")
        # The corrected (feint) action succeeds after that lesson.
        self.assertEqual(self.r["cFinal"]["status"], "won")

    def test_feint_crosses_behind_the_guard_window(self):
        c = self.r["c"]
        # Lured east from afar, committed while the player walks up.
        self.assertEqual(c[8]["bx"], 7)
        self.assertEqual(c[10]["pos"], {"x": 5, "y": 3})
        self.assertEqual(c[10]["bx"], 7)
        # Cross at the vacated west side, collect orb, take portal.
        self.assertEqual(c[11]["pos"], {"x": 5, "y": 4})
        self.assertEqual(c[11]["status"], "playing")
        self.assertEqual(self.r["cFinal"],
                         {"pos": {"x": 11, "y": 7},
                          "status": "won", "orbs": 0})

    def test_restart_restores_the_blocker(self):
        # YAML: 'restart and replay' (restart half; replay below).
        self.assertEqual(self.r["freshRow"], "#####DBD#####")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    @unittest.skip("blocked-by: 81 (push block) not built yet — "
                   "pin the blocker with a pushed block")
    def test_pin_and_walk_the_other_side(self):
        pass

    @unittest.skip("blocked-by: 39 (decoy Jolly) not built yet — "
                   "decoy draws the blocker tracking")
    def test_decoy_draws_the_tracking(self):
        pass

    def test_game_page_loads_the_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/blocker/main.js", html)
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'B'", js)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'right', 'right', 'right',
  'down', 'down', 'left', 'left', 'down', 'down',
  'right', 'down', 'right', 'right', 'right', 'right', 'right',
  'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-34-blocker-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-34-blocker-room', log);
const replayed2 = core.replay(level, 'mech-34-blocker-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row: replayed[replayed.length - 1].grid[4],
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        # YAML: 'restart and replay' — recorded session replays to
        # the same end state (digest match, twice).
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 11, "y": 7},
                          "status": "won", "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 20)


if __name__ == "__main__":
    unittest.main()
