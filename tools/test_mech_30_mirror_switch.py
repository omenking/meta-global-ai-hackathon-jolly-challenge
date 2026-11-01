"""Checks for the mirror switch (mech-30-mirror-switch).

Mirror inverts every toggle A<->B exactly once and doors follow
(open only when every toggle is A); broken one-time switches are
unaffected; restart restores placed state. YAML test_cases blocked
by unbuilt mechanics 22/27 get explicit skips, never fake passes.

Run with: python -m unittest tools.test_mech_30_mirror_switch -v
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

LEVEL_ID = "mech-30-mirror-switch-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class RoomLevelTests(unittest.TestCase):
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
        self.assertIn("M", grid)
        # Mirror by the entrance on the spawn row, toggles A/B/A.
        self.assertEqual(rows[1].index("M"), 3)
        self.assertEqual(rows[2], "#..A.B.A....#")
        self.assertIn("D", rows[4])
        self.assertGreaterEqual(grid.count("*"), 1)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-30-mirror-switch-room');
  const snap = () => ({ pos: {...s.player}, row1: s.grid[1],
    row2: s.grid[2], row3: s.grid[3], row4: s.grid[4],
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, {t_ms: (i+1)*100, input}); snaps.push(snap());
  });
  return { snaps, final: s };
}
const naive = run(['right','right']);
const naiveFix = run(['right','right','left','right']);
const solution = run(['down','down','right','right','right','right',
  'up','down','right','down','down','down']);
const broken = run(['down','down','right','right','right','right',
  'right','right','right','right','left','left','left','left',
  'left','left','left','up','up','right', 'left']);
const s0 = core.initialState(level, 'mech-30-mirror-switch-room');
const before = JSON.stringify(s0);
core.step(s0, {t_ms: 100, input: 'right'});
console.log(JSON.stringify({ naive: naive.snaps, naiveFix: naiveFix.snaps,
  solution: solution.snaps, broken: broken.snaps,
  solFinal: {pos: {...solution.final.player},
    orbs: core.readout(solution.final).orbs_left,
    status: solution.final.status},
  freshRow2: core.initialState(level,'mech-30-mirror-switch-room').grid[2],
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MirrorMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SCRIPT)

    def test_mirror_inverts_every_toggle_once(self):
        n = self.r["naive"]
        self.assertEqual(n[2]["pos"], {"x": 3, "y": 1})
        self.assertEqual(n[2]["row2"], "#..B.A.B....#")
        # Door stays shut: mirror is not itself a door opener.
        self.assertEqual(n[2]["row4"], "######D######")

    def test_second_press_restores_room(self):
        f = self.r["naiveFix"]
        self.assertEqual(f[4]["row2"], "#..A.B.A....#")

    def test_corrected_action_succeeds(self):
        self.assertEqual(self.r["solFinal"],
                         {"pos": {"x": 6, "y": 6}, "orbs": 0,
                          "status": "won"})
        # After fixing the single B toggle the door opened.
        self.assertEqual(self.r["solution"][7]["row4"], "######d######")

    def test_broken_onetime_unaffected_by_mirror(self):
        b = self.r["broken"]
        # Final snap: on mirror, one-time already broken ('n').
        self.assertIn("n", b[-1]["row3"])
        self.assertEqual(b[-1]["row2"], "#..B.A.B....#")

    def test_restart_restores(self):
        self.assertEqual(self.r["freshRow2"], "#..A.B.A....#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_wiring(self):
        js = (ROOT / "tools" / "static" / "game-core.js").read_text()
        self.assertIn("mirror-switch/main.js", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/mirror-switch/main.js", html)


class YamlBlockedCases(unittest.TestCase):
    @unittest.skip("blocked-by: 22 (toggle switch) - not yet built as "
                   "its own mechanic; mirror pack toggles are local")
    def test_yaml_solution_mirror_a_wrong_room_right(self):
        pass

    @unittest.skip("blocked-by: 22 (toggle switch)")
    def test_yaml_adversarial_mirror_by_the_entrance(self):
        pass

    @unittest.skip("blocked-by: 27 (one-time switch)")
    def test_yaml_boundary_broken_onetime_unaffected(self):
        pass

    @unittest.skip("blocked-by: 22 (toggle switch)")
    def test_yaml_boundary_one_press_inverts_each_once(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down','down','right','right','right','right',
  'up','down','right','down','down','down'];
const log = inputs.map((input, i) => ({t_ms: (i+1)*100, input}));
let live = core.initialState(level, 'mech-30-mirror-switch-room');
for (const e of log) live = core.step(live, e);
const replayed = core.replay(level, 'mech-30-mirror-switch-room', log);
const replayed2 = core.replay(level, 'mech-30-mirror-switch-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length-1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length-1]),
  liveFinal: {pos: {...live.player}, orbs: core.readout(live).orbs_left,
    status: live.status}, replaySteps: replayed.length - 1 }));
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
                         {"pos": {"x": 6, "y": 6}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 12)


if __name__ == "__main__":
    unittest.main()
