"""Checks for the chaser (mech-32-chaser).

The mechanic lives in the chaser pack (packs/chaser/main.js) as an
actor controller plus a tick touch rule, driven here under Node
against the teaching room. Rules: after each player move the chaser
takes one step in the same direction if that tile is free, otherwise
it stays (blocked pose); touch either way loses the attempt; restart
(fresh state) restores the chaser to its placed tile.

YAML test_cases (enemies-and-bots.yml #32) coverage:
- "lead it into a wall" -> test_solution_leads_it_into_a_wall_and_wins
- "adversarial straight run" -> test_straight_run_for_the_orb_is_caught
- "one copied step per move" -> test_one_copied_step_per_move,
  test_copy_into_a_wall_stays_and_shows_blocked
- "mud print following" -> blocked-by 47, skipped with reason
- "restart and replay" -> test_restart_restores_the_chaser,
  SanityReplayTests

Run with: python -m unittest tools.test_mech_32_chaser -v
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

LEVEL_ID = "mech-32-chaser-room"
SOLUTION = (["down", "down", "down", "right", "right", "down", "down",
  "left", "up", "up", "left", "up", "up", "up"] + ["right"] * 12)
NAIVE = ["right"] * 12


class ChaserRoomLevelTests(unittest.TestCase):
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
        self.assertIn("H", grid)
        self.assertEqual(grid.count("*"), 1)
        self.assertIn("X", grid)
        # Chaser starts between the player and the orb on its lane.
        top = rows[1]
        self.assertLess(top.index("P"), top.index("H"))
        self.assertLess(top.index("H"), top.index("*"))


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
  let s = core.initialState(level, 'mech-32-chaser-room');
  const snap = () => {
    const c = s.actors.find((a) => a.def === 'chaser:chaser');
    return { pos: { ...s.player },
      chaser: c ? { x: c.x, y: c.y, blocked: !!c.flags.blocked } : null,
      status: s.status, orbs: core.readout(s).orbs_left };
  };
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const solution = ['down', 'down', 'down', 'right', 'right', 'down',
  'down', 'left', 'up', 'up', 'left', 'up', 'up', 'up',
  ...Array(12).fill('right')];
const naive = Array(12).fill('right');
const s0 = core.initialState(level, 'mech-32-chaser-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution: run(solution), naive: run(naive),
  oneRight: run(['right']), oneDown: run(['down']),
  pushWall: run(['up']),
  fresh: run([])[0],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class ChaserMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_one_copied_step_per_move(self):
        self.assertEqual(self.r["oneRight"][1]["pos"], {"x": 2, "y": 1})
        self.assertEqual(self.r["oneRight"][1]["chaser"],
                         {"x": 6, "y": 1, "blocked": False})
        self.assertEqual(self.r["oneDown"][1]["pos"], {"x": 1, "y": 2})
        self.assertEqual(self.r["oneDown"][1]["chaser"],
                         {"x": 5, "y": 2, "blocked": False})

    def test_blocked_player_push_copies_nothing(self):
        # Pushing into the wall above is not a move: no copy.
        self.assertEqual(self.r["pushWall"][1]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["pushWall"][1]["chaser"],
                         {"x": 5, "y": 1, "blocked": False})

    def test_straight_run_for_the_orb_is_caught(self):
        naive = self.r["naive"]
        # The chaser is driven to the warp corner and held there.
        self.assertEqual(naive[8]["chaser"],
                         {"x": 13, "y": 1, "blocked": False})
        self.assertEqual(naive[9]["chaser"],
                         {"x": 13, "y": 1, "blocked": True})
        # The player still collects the orb, then is caught on it.
        self.assertEqual(naive[12]["orbs"], 0)
        self.assertEqual(naive[12]["pos"], {"x": 13, "y": 1})
        self.assertEqual(naive[12]["status"], "lost")

    def test_solution_leads_it_into_a_wall_and_wins(self):
        sol = self.r["solution"]
        # Parked low against the right wall while the player crosses.
        self.assertEqual(sol[-1]["chaser"],
                         {"x": 13, "y": 4, "blocked": True})
        self.assertEqual(sol[-1]["pos"], {"x": 13, "y": 1})
        self.assertEqual(sol[-1]["orbs"], 0)
        self.assertEqual(sol[-1]["status"], "won")

    def test_copy_into_a_wall_stays_and_shows_blocked(self):
        naive = self.r["naive"]
        self.assertEqual(naive[9]["chaser"]["x"], naive[8]["chaser"]["x"])
        self.assertTrue(naive[9]["chaser"]["blocked"])
        self.assertTrue(naive[10]["chaser"]["blocked"])

    def test_restart_restores_the_chaser(self):
        self.assertEqual(self.r["fresh"]["chaser"],
                         {"x": 5, "y": 1, "blocked": False})
        self.assertEqual(self.r["fresh"]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["fresh"]["status"], "playing")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    @unittest.skip("blocked-by: 47 (mud tile) — mud is not built yet; "
                   "the chaser follows print order in mud instead of "
                   "copying moves, which needs the mud pack first")
    def test_mud_print_following(self):
        pass

    def test_game_wires_the_chaser_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("chaser:chaser", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/chaser/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'down', 'down', 'right', 'right', 'down',
  'down', 'left', 'up', 'up', 'left', 'up', 'up', 'up',
  ...Array(12).fill('right')];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-32-chaser-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-32-chaser-room', log);
const replayed2 = core.replay(level, 'mech-32-chaser-room',
  JSON.parse(JSON.stringify(log)));
const last = replayed[replayed.length - 1];
const c = last.actors.find((a) => a.def === 'chaser:chaser');
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  chaser: { x: c.x, y: c.y },
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
                         {"pos": {"x": 13, "y": 1}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["chaser"], {"x": 13, "y": 4})
        self.assertEqual(self.r["replaySteps"], 26)


if __name__ == "__main__":
    unittest.main()
