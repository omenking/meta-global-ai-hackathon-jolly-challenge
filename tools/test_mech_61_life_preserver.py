"""Checks for the life preserver (mech-61-life-preserver).

Run with: python -m unittest tools.test_mech_61_life_preserver -v
Cases marked blocked-by an unbuilt mechanic in the YAML get an
explicit skipped-with-reason check, never a fake pass.
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

LEVEL_ID = "mech-61-life-preserver-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class RoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])

    def test_rows_rectangular_and_legend_covers_tiles(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_teaching_layout(self):
        grid = "".join(self.level["rows"])
        self.assertIn("L", grid)
        self.assertIn("D", grid)
        self.assertIn("*", grid)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-61-life-preserver-room');
  const snaps = [{ pos: { ...s.player }, inv: core.readout(s).inventory }];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push({ pos: { ...s.player }, inv: core.readout(s).inventory,
      status: s.status });
  });
  return snaps;
}
const solution = run(Array(13).fill('right'));
const s0 = core.initialState(level, 'mech-61-life-preserver-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ solution,
  freshInv: core.readout(core.initialState(level,
    'mech-61-life-preserver-room')).inventory,
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SCRIPT)

    def test_solution_crossing_with_preserver(self):
        # YAML: solution crossing with preserver (not blocked).
        snaps = self.r["solution"]
        self.assertEqual(snaps[2]["inv"], ["life-preserver"])
        self.assertEqual(snaps[-1]["pos"], {"x": 11, "y": 1})
        self.assertEqual(snaps[-1]["status"], "won")
        self.assertEqual(snaps[-1]["inv"], ["life-preserver"])

    def test_adversarial_wading_in_without_it(self):
        self.skipTest("blocked-by: 48 (checkpoint) — checkpoint mechanic "
                      "not built as its own pack; pack implements a local "
                      "spawn-return but the YAML case is deferred")

    def test_boundary_two_moves_per_deep_tile(self):
        self.skipTest("blocked-by: 41 (deep water) — deep-water mechanic "
                      "not built as its own pack; pack implements a local "
                      "two-move cost but the YAML case is deferred")

    def test_boundary_slot_held_for_the_level(self):
        # YAML: boundary slot held for the level (not blocked).
        snaps = self.r["solution"]
        for snap in snaps[2:]:
            self.assertEqual(snap["inv"], ["life-preserver"])

    def test_restart_restores_preserver(self):
        self.assertEqual(self.r["freshInv"], [])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/life-preserver/main.js", html)


SANITY = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = Array(13).fill('right');
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-61-life-preserver-room');
for (const e of log) live = core.step(live, e);
const replayed = core.replay(level, 'mech-61-life-preserver-room', log);
console.log(JSON.stringify({ liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  final: { pos: { ...live.player }, status: live.status } }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    def test_restart_and_replay_same_end_state(self):
        # YAML: restart and replay (not blocked).
        r = run_core(SANITY)
        self.assertEqual(r["replayDigest"], r["liveDigest"])
        self.assertEqual(r["final"]["status"], "won")


if __name__ == "__main__":
    unittest.main()
