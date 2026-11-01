"""Checks for the turntable tile (mech-7-turntable-tile).

The mechanic lives in the pure GameCore step (packs/turntable);
driven here under Node against the teaching room. Rules: stepping
onto the turntable on foot turns its arrow 90 degrees clockwise
and nudges the player one tile in the new arrow direction,
automatically on entry; restart (fresh state) restores the placed
arrow. The slides/belts case is blocked-by mechanic 1 (ice tile),
not yet built, so it is an explicit skip, never a fake pass.

Run with: python -m unittest tools.test_mech_7_turntable_tile -v
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

LEVEL_ID = "mech-7-turntable-tile-room"


class TurntableRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("T"), 1)
        t_pos = next((x, y) for y, r in enumerate(rows)
                     for x, ch in enumerate(r) if ch == "T")
        # The east lane beyond the turntable holds orb then warp.
        row = rows[t_pos[1]]
        self.assertIn("*", row[t_pos[0]:])
        self.assertIn("X", row[t_pos[0]:])
        # Every nudge target around the turntable is open floor.
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            self.assertEqual(rows[t_pos[1] + dy][t_pos[0] + dx], ".")


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
  let s = core.initialState(level, 'mech-7-turntable-tile-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    dir: (s.meta['5,2'] || {}).turntable_dir || null });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const toTable = ['right', 'right', 'right', 'down'];
// A: solution - ride the nudge east, collect the orb, warp out.
const a = run([...toTable, 'right', 'right', 'right']);
// B: adversarial - nudged while thinking, then loop back home.
const b = run([...toTable, 'right', 'down', 'down', 'left',
  'left', 'up', 'up', 'left', 'left', 'left', 'up']);
// C: four on-foot entries cycle east, south, west, north.
const c = run([...toTable, 'right',
  'down', 'left', 'left', 'up', 'right',
  'left', 'up', 'right',
  'down', 'right', 'up']);
// D: waiting beside the tile turns nothing.
const d = run([...toTable, 'wait', 'wait']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-7-turntable-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ a, b, c, d,
  freshDir: (core.initialState(level,
    'mech-7-turntable-tile-room').meta['5,2'] || {}).turntable_dir,
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class TurntableMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_on_foot_entry_turns_and_nudges(self):
        a = self.r["a"]
        self.assertEqual(a[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(a[4]["dir"], "north")
        # One step onto T: arrow north->east, nudged east at once.
        self.assertEqual(a[5]["pos"], {"x": 6, "y": 2})
        self.assertEqual(a[5]["dir"], "east")
        self.assertEqual(a[6]["pos"], {"x": 7, "y": 2})
        self.assertEqual(a[6]["orbs"], 1)
        self.assertEqual(a[7]["pos"], {"x": 8, "y": 2})
        self.assertEqual(a[7]["status"], "won")

    def test_adversarial_nudge_while_thinking_loops_back(self):
        b = self.r["b"]
        # The naive step does not leave the player standing on T.
        self.assertEqual(b[5]["pos"], {"x": 6, "y": 2})
        self.assertEqual(b[5]["dir"], "east")
        # The open floor loops back to the start, never stranded.
        self.assertEqual(b[-1]["pos"], {"x": 1, "y": 1})
        self.assertEqual(b[-1]["status"], "playing")

    def test_exactly_90_degrees_per_entry(self):
        c = self.r["c"]
        self.assertEqual(c[5]["dir"], "east")
        self.assertEqual(c[5]["pos"], {"x": 6, "y": 2})
        self.assertEqual(c[10]["dir"], "south")
        self.assertEqual(c[10]["pos"], {"x": 5, "y": 3})
        self.assertEqual(c[13]["dir"], "west")
        self.assertEqual(c[13]["pos"], {"x": 4, "y": 2})
        self.assertEqual(c[16]["dir"], "north")
        self.assertEqual(c[16]["pos"], {"x": 5, "y": 1})

    def test_no_entry_no_turn(self):
        d = self.r["d"]
        self.assertEqual(d[-1]["pos"], {"x": 4, "y": 2})
        self.assertEqual(d[-1]["dir"], "north")

    @unittest.skip("blocked-by: 1 (ice tile) and 2 (conveyor) - "
                   "slides/belts are not built yet, so pass-straight-"
                   "over cannot be exercised; never a fake pass")
    def test_slides_and_belts_pass_straight_over(self):
        pass

    def test_restart_restores_placed_arrow(self):
        self.assertEqual(self.r["freshDir"], "north")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_turntable_direction(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("turntable-' + tdir + '.png'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/turntable/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'down',
  'right', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-7-turntable-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-7-turntable-tile-room', log);
const replayed2 = core.replay(level, 'mech-7-turntable-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
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

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 8, "y": 2}, "status": "won",
                          "orbs": 1})
        self.assertEqual(self.r["replaySteps"], 7)


if __name__ == "__main__":
    unittest.main()
