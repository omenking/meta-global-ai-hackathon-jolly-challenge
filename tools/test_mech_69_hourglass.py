"""Checks for the hourglass (mech-69-hourglass).

The mechanic lives in the pure GameCore step (packs/hourglass);
driven here under Node against the teaching room. Rules: stepping
on the hourglass collects it at once (no inventory) and freezes
the level timer for exactly 10 real seconds (recorded t_ms),
however many moves are made inside it; the timer then resumes
from the held value. Restart (fresh state) restores it.

YAML test_cases coverage (time-gates-and-exits.yml #69):
- solution placement before the hard room
- adversarial early collection
- freeze lasts exactly 10 real seconds
- door countdown is not frozen (blocked-by: 25, skipped)
- restart and replay

Run with: python -m unittest tools.test_mech_69_hourglass -v
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

LEVEL_ID = "mech-69-hourglass-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class HourglassRoomLevelTests(unittest.TestCase):
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

        def pos(ch):
            return [(x, y) for y, r in enumerate(rows)
                    for x, c in enumerate(r) if c == ch]

        self.assertEqual(pos("P"), [(1, 1)])
        # Early hourglass on the main path near the start, late
        # hourglass just before the gate into the hard room.
        self.assertEqual(sorted(pos("H")), [(3, 1), (7, 3)])
        self.assertEqual(pos("G"), [(8, 3)])
        self.assertEqual(pos("X"), [(11, 3)])
        self.assertGreaterEqual(len(pos("*")), 2)
        # Hard room (right of the gate) holds the warp, no orbs.
        self.assertTrue(all(x > 8 for x, _ in pos("X")))


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(pairs) {
  let s = core.initialState(level, 'mech-69-hourglass-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    left: s.time_left_s, eff: s.effective_elapsed_s,
    frozen: core.readout(s).timer_frozen,
    collected: (s.counters || {})['hourglass:collected'] || 0,
    collectMs: (s.counters || {})['hourglass:collect_ms'],
    inv: core.readout(s).inventory, orbs: core.readout(s).orbs_left,
    row1: s.grid[1], row3: s.grid[3] });
  const snaps = [snap()];
  for (const [t_ms, input] of pairs) {
    s = core.step(s, { t_ms, input });
    snaps.push(snap());
  }
  return { snaps, final: s };
}
const mv = (list, start, stepMs) =>
  list.map((input, i) => [start + i * stepMs, input]);
// Solution: avoid the early hourglass, take both easy orbs,
// collect the late hourglass just before the gate, cross frozen.
const solutionPairs = [
  ...mv(['down','down','down','down'], 100, 100),
  ...mv(['right','right','right','right'], 500, 100),
  ...mv(['up','up','up','up'], 900, 100),
  ...mv(['down','down'], 1300, 100),
  [1500, 'right'], [1600, 'right'],
  [5000, 'right'],
  [6000, 'right'], [7000, 'right'], [8000, 'right'],
];
const solution = run(solutionPairs);
// Resume after the late freeze: collect, then step past 10s.
const resume = run([...solutionPairs.slice(0, 16),
  [11600, 'left'], [12600, 'right']]);
// Adversarial: collect early, spend the freeze on the opening.
const adv = run([[1000,'right'],[2000,'right'],[3000,'right'],
  [13000,'right'],[23000,'right'],[34900,'left'],[35000,'timeout']]);
// Boundary: many moves inside the freeze vs one jump.
const many = run([[1000,'right'],[2000,'right'],
  [3000,'left'],[4000,'right'],[5000,'left'],[6000,'right'],
  [7000,'left'],[8000,'right'],[9000,'left'],[10000,'right'],
  [11000,'left'],[12000,'right'],[13000,'left']]);
const jump = run([[1000,'right'],[2000,'right'],[11000,'left'],
  [12000,'right'],[13000,'left']]);
// Second collection starts a fresh freeze.
const second = run([[1000,'right'],[2000,'right'],[13000,'left'],
  [14000,'down'],[15000,'down'],[16000,'right'],[17000,'right'],
  [17500,'right'],[18000,'right'],[18500,'right'],[23000,'left']]);
const s0 = core.initialState(level, 'mech-69-hourglass-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution: solution.snaps, resume: resume.snaps,
  adv: adv.snaps, many: many.snaps, jump: jump.snaps,
  second: second.snaps,
  fresh: { row1: s0.grid[1], row3: s0.grid[3], left: s0.time_left_s,
    collected: (s0.counters || {})['hourglass:collected'] || 0 },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class HourglassMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_placement_before_hard_room(self):
        s = self.r["solution"]
        # Late collection at t=1600: timer held at 23.4s left.
        self.assertEqual(s[16]["pos"], {"x": 7, "y": 3})
        self.assertEqual(s[16]["collected"], 1)
        self.assertEqual(s[16]["left"], 23.4)
        self.assertTrue(s[16]["frozen"])
        # Crossing the gate and reaching the warp stays frozen.
        self.assertEqual(s[17]["pos"], {"x": 8, "y": 3})
        self.assertEqual(s[17]["left"], 23.4)
        self.assertEqual(s[20]["pos"], {"x": 11, "y": 3})
        self.assertEqual(s[20]["status"], "won")
        self.assertEqual(s[20]["left"], 23.4)

    def test_timer_resumes_from_held_value_after_freeze(self):
        r = self.r["resume"]
        self.assertEqual(r[17]["left"], 23.4)
        self.assertFalse(r[17]["frozen"])
        self.assertEqual(r[18]["left"], 22.4)

    def test_adversarial_early_collection(self):
        a = self.r["adv"]
        # Collected on the main path at t=2000, held at 23s.
        self.assertEqual(a[2]["pos"], {"x": 3, "y": 1})
        self.assertEqual(a[2]["left"], 23)
        # Freeze spent on the easy opening: hard room is reached
        # with the timer running normally again (never stranded).
        self.assertEqual(a[4]["left"], 22)
        self.assertFalse(a[4]["frozen"])
        self.assertEqual(a[4]["status"], "playing")
        self.assertEqual(a[5]["left"], 12)
        self.assertEqual(a[6]["status"], "playing")
        # Expiry at the effective limit loses the run.
        self.assertEqual(a[7]["status"], "lost")
        self.assertEqual(a[7]["left"], 0)

    def test_freeze_lasts_exactly_10_real_seconds(self):
        many, jump = self.r["many"], self.r["jump"]
        # 9s after collection (t=11000): still held, moves or not.
        self.assertEqual(many[11]["left"], 23)
        self.assertTrue(many[11]["frozen"])
        self.assertEqual(jump[3]["left"], 23)
        self.assertEqual(many[11]["left"], jump[3]["left"])
        # At 10s the held value is the resume point; then it falls.
        self.assertEqual(many[12]["left"], 23)
        self.assertEqual(jump[4]["left"], 23)
        self.assertEqual(many[13]["left"], 22)
        self.assertFalse(many[13]["frozen"])
        self.assertEqual(jump[5]["left"], 22)

    def test_collection_fires_on_step_and_never_enters_inventory(self):
        a = self.r["adv"]
        self.assertEqual(a[2]["inv"], [])
        self.assertEqual(a[2]["row1"][3], "h")
        self.assertEqual(a[2]["collectMs"], 2000)

    def test_second_collection_starts_a_fresh_freeze(self):
        s = self.r["second"]
        self.assertEqual(s[10]["pos"], {"x": 7, "y": 3})
        self.assertEqual(s[10]["left"], 16.5)
        self.assertEqual(s[11]["left"], 16.5)
        self.assertTrue(s[11]["frozen"])

    def test_restart_restores_hourglass_and_timer(self):
        self.assertEqual(self.r["fresh"]["row1"], "#P.H.*..#.....#")
        self.assertEqual(self.r["fresh"]["row3"], "#......HG..X..#")
        self.assertEqual(self.r["fresh"]["left"], 25)
        self.assertEqual(self.r["fresh"]["collected"], 0)

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_door_countdown_is_not_frozen(self):
        # YAML case: blocked-by 25 (timer switch). The timer-switch
        # pack is not built on this branch, so this is an explicit
        # skip with reason, never a fake pass.
        self.assertFalse(
            (ROOT / "tools" / "static" / "packs" / "timer-switch").exists(),
            "timer-switch pack now exists: un-skip and implement this case")
        self.skipTest("blocked-by: 25 (timer switch): timer-switch "
                      "pack/door not built in this engine, so the "
                      "door-countdown-vs-freeze case cannot run yet")

    def test_game_renders_spent_tile_and_frozen_timer(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("hourglass-spent.png", js)
        self.assertIn("timer-frozen", js)
        self.assertIn("dt.ch === 'H'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/hourglass/main.js", html)

    def test_no_unrecorded_wall_clock_reads(self):
        pack = (ROOT / "tools" / "static" / "packs" / "hourglass"
                / "main.js").read_text(encoding="utf-8")
        self.assertNotIn("Date.now", pack)
        self.assertNotIn("performance.now", pack)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const pairs = [
  [100,'down'],[200,'down'],[300,'down'],[400,'down'],
  [500,'right'],[600,'right'],[700,'right'],[800,'right'],
  [900,'up'],[1000,'up'],[1100,'up'],[1200,'up'],
  [1300,'down'],[1400,'down'],[1500,'right'],[1600,'right'],
  [5000,'right'],[6000,'right'],[7000,'right'],[8000,'right'],
];
const log = pairs.map(([t_ms, input]) => ({ t_ms, input }));
let live = core.initialState(level, 'mech-69-hourglass-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-69-hourglass-room', log);
const replayed2 = core.replay(level, 'mech-69-hourglass-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    left: live.time_left_s },
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
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 11, "y": 3}, "status": "won",
                          "left": 23.4})
        self.assertEqual(self.r["replaySteps"], 20)


if __name__ == "__main__":
    unittest.main()
