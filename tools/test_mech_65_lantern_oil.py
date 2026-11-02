"""Checks for lantern oil (mech-65-lantern-oil).

The mechanic lives in the pure GameCore step (packs/lantern-oil);
driven here under Node against the teaching room. Rules: oil is
spent on collection and refills the lantern to full; in a dark
room the lantern burns down from recorded t_ms only and the lit
radius shrinks to the base radius and stops (never out); the
conditional HUD gauge is the lantern:fuel counter; restart
restores the oil and starting fuel.

YAML test_cases for mechanic #65: four cases are marked
blocked-by 51 (dark room) / 52 (lantern), which are not built;
those get explicit skipped-with-reason checks below, never a
fake pass. The restart-and-replay case is unblocked and runs.

Run with: python -m unittest tools.test_mech_65_lantern_oil -v
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

LEVEL_ID = "mech-65-lantern-oil-room"


class LanternRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("o"), 1)
        self.assertGreaterEqual(grid.count("*"), 2)
        oil = [(x, y) for y, r in enumerate(rows)
               for x, ch in enumerate(r) if ch == "o"]
        spawn = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "P"]
        far = max(x for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "*")
        self.assertLess(abs(oil[0][0] - spawn[0][0]), 4,
                        "oil is not near the entrance")
        self.assertGreater(far, oil[0][0] + 6,
                           "no search area beyond the oil")


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
  let s = core.initialState(level, 'mech-65-lantern-oil-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    fuel: s.counters['lantern:fuel'], radius: s.counters['lantern:radius'],
    dark: !!s.flags['lantern:dark'], orbs: core.readout(s).orbs_left,
    row1: s.grid[1] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
// Corrected: collect the oil, search east, both orbs, gate, warp.
const solutionInputs = ['right', 'right'];
for (let i = 0; i < 10; i++) solutionInputs.push('right');
solutionInputs.push('down', 'down');
for (let i = 0; i < 11; i++) solutionInputs.push('left');
for (let i = 0; i < 12; i++) solutionInputs.push('right');
solutionInputs.push('up', 'up', 'right');
const solution = run(solutionInputs);
// Naive: walk straight past the oil to the far side and back.
const naiveInputs = ['down'];
for (let i = 0; i < 12; i++) naiveInputs.push('right');
naiveInputs.push('up', 'down');
for (let i = 0; i < 11; i++) naiveInputs.push('left');
naiveInputs.push('up', 'right');
const naive = run(naiveInputs);
// Boundary: burn to empty, keep walking at base radius.
const burnInputs = [];
for (let i = 0; i < 30; i++) burnInputs.push(i % 2 ? 'left' : 'right');
const burn = run(burnInputs);
const s0 = core.initialState(level, 'mech-65-lantern-oil-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution: solution.snaps, naive: naive.snaps, burn: burn.snaps,
  solFinal: { pos: { ...solution.final.player },
    status: solution.final.status,
    orbs: core.readout(solution.final).orbs_left },
  fresh: { fuel: s0.counters['lantern:fuel'],
    radius: s0.counters['lantern:radius'], row1: s0.grid[1] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class LanternMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_starts_partly_spent_in_a_dark_room(self):
        self.assertEqual(self.r["fresh"]["fuel"], 60)
        self.assertTrue(self.r["solution"][0]["dark"])

    def test_oil_refills_to_full_in_one_collection(self):
        s = self.r["solution"]
        self.assertEqual(s[2]["pos"], {"x": 3, "y": 1})
        self.assertGreaterEqual(s[2]["fuel"], 90)
        self.assertEqual(s[2]["radius"], 4)
        self.assertNotIn("o", s[2]["row1"].replace("P", "", 1)
                         if False else s[3]["row1"])

    def test_solution_route_collects_far_orbs_with_light_remaining(self):
        s = self.r["solution"]
        # Step 12 stands on the far orb tile with fuel to spare.
        self.assertGreater(s[12]["fuel"], 0)
        self.assertEqual(self.r["solFinal"]["status"], "won")
        self.assertEqual(self.r["solFinal"]["orbs"], 0)

    def test_naive_walk_past_oil_shrinks_to_base_before_far_orbs(self):
        n = self.r["naive"]
        # Step 14 stands on the far orb tile, already at base.
        self.assertEqual(n[14]["radius"], 1)
        self.assertLessEqual(n[14]["fuel"], 16)
        # Never stranded: the walk back reaches and collects the oil.
        self.assertEqual(n[-1]["pos"], {"x": 3, "y": 1})
        self.assertGreaterEqual(n[-1]["fuel"], 90)
        self.assertEqual(n[-1]["status"], "playing")

    def test_shrink_stops_at_base_radius_and_never_goes_out(self):
        b = self.r["burn"]
        self.assertEqual(b[-1]["fuel"], 0)
        self.assertEqual(b[-1]["radius"], 1)
        self.assertEqual(b[-1]["status"], "playing")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_the_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/lantern-oil/main.js", html)


class BlockedYamlCaseTests(unittest.TestCase):
    """YAML cases blocked-by unbuilt mechanics 51/52: explicit skips."""

    def test_solution_oil_route_through_the_dark_room(self):
        self.skipTest("blocked-by: 51 (dark room) — dark-room "
                      "visibility is not built; the fuel/radius "
                      "rules are covered locally in LanternMechanicTests")

    def test_adversarial_walking_past_the_oil(self):
        self.skipTest("blocked-by: 52 (lantern) — the carried "
                      "lantern tile is not built; the shrink-to-base "
                      "and walk-back rules are covered locally")

    def test_boundary_oil_restores_to_full(self):
        self.skipTest("blocked-by: 52 (lantern) — the carried "
                      "lantern tile is not built; refill-to-full "
                      "is covered locally")

    def test_boundary_shrink_stops_at_base_radius(self):
        self.skipTest("blocked-by: 51 (dark room) — dark-room "
                      "visibility is not built; the base-radius "
                      "floor is covered locally")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right'];
for (let i = 0; i < 10; i++) inputs.push('right');
inputs.push('down', 'down');
for (let i = 0; i < 11; i++) inputs.push('left');
for (let i = 0; i < 12; i++) inputs.push('right');
inputs.push('up', 'up', 'right');
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-65-lantern-oil-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-65-lantern-oil-room', log);
const replayed2 = core.replay(level, 'mech-65-lantern-oil-room',
  JSON.parse(JSON.stringify(log)));
const fresh = core.initialState(level, 'mech-65-lantern-oil-room');
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  freshFuel: fresh.counters['lantern:fuel'], freshRow1: fresh.grid[1],
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
        self.assertEqual(self.r["liveFinal"]["status"], "won")
        self.assertEqual(self.r["liveFinal"]["orbs"], 0)

    def test_restart_restores_oil_and_starting_fuel(self):
        self.assertEqual(self.r["freshFuel"], 60)
        self.assertIn("o", self.r["freshRow1"])


if __name__ == "__main__":
    unittest.main()
