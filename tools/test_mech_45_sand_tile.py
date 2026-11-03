"""Checks for the sand tile (mech-45-sand-tile).

Mechanic lives in packs/sand-tile via terrain onEnterTerrain hook;
driven under Node against the teaching room. Rules: walking on sand
leaves prints persisting for the attempt, no slowing (one move per
tile), enemies ignore prints (blocked-by 31), restart clears prints.

Run with: python -m unittest tools.test_mech_45_sand_tile -v
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

LEVEL_ID = "mech-45-sand-tile-room"


class SandRoomLevelTests(unittest.TestCase):
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
        self.assertGreaterEqual(grid.count("S"), 10)
        self.assertGreaterEqual(grid.count("*"), 1)
        # Junction (5,1): east dead end and south untaken exit both sand.
        self.assertEqual(rows[1][5], "S")
        self.assertEqual(rows[1][9], "S")  # dead-end end
        self.assertEqual(rows[2][5], "S")  # south exit
        self.assertEqual(rows[3][11], "*")


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
  let s = core.initialState(level, 'mech-45-sand-tile-room');
  const prints = () => Object.keys(s.meta || {}).filter(k => s.meta[k].sand_print).sort();
  const snap = () => ({ pos: {...s.player}, steps: s.steps, status: s.status,
    orbs: core.readout(s).orbs_left, prints: prints() });
  const snaps = [snap()];
  seq.forEach((input, i) => { s = core.step(s, {t_ms:(i+1)*100, input}); snaps.push(snap()); });
  return { snaps, final: s };
}
// Solution: junction -> south -> orb -> back to start
const sol = run(['right','right','right','right','down','down',
  'right','right','right','right','right','right',
  'left','left','left','left','left','left','up','up',
  'left','left','left','left']);
// Dead-end: east to end, back to junction
const dead = run(['right','right','right','right','right','right','right','right',
  'left','left','left','left']);
// Boundary: at dead end push into wall
const wall = run(['right','right','right','right','right','right','right','right','right','right']);
const s0 = core.initialState(level, 'mech-45-sand-tile-room');
const before = JSON.stringify(s0);
core.step(s0, {t_ms:100, input:'right'});
console.log(JSON.stringify({ sol: sol.snaps, dead: dead.snaps, wall: wall.snaps,
  solFinal: {pos:{...sol.final.player}, orbs: core.readout(sol.final).orbs_left},
  freshPrints: Object.keys(core.initialState(level,'mech-45-sand-tile-room').meta||{}),
  pure: JSON.stringify(s0)===before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SandMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_prints_persist_and_cost_nothing(self):
        sol = self.r["sol"]
        # One move per tile on sand: after 4 rights, at junction, 4 steps.
        self.assertEqual(sol[4]["pos"], {"x": 5, "y": 1})
        self.assertEqual(sol[4]["steps"], 4)
        # Prints on every sand cell entered so far, persist later.
        self.assertIn("2,1", sol[4]["prints"])
        self.assertIn("5,1", sol[4]["prints"])
        # After full solution prints persist on taken route.
        self.assertIn("5,3", sol[-1]["prints"])
        self.assertIn("10,3", sol[-1]["prints"])

    def test_solution_collects_orb_and_returns(self):
        self.assertEqual(self.r["solFinal"], {"pos": {"x": 1, "y": 1}, "orbs": 0})

    def test_adversarial_dead_end_retrace(self):
        dead = self.r["dead"]
        # Reached dead end (9,1), returned to junction (5,1), still playing (no soft-lock).
        self.assertEqual(dead[8]["pos"], {"x": 9, "y": 1})
        self.assertEqual(dead[-1]["pos"], {"x": 5, "y": 1})
        self.assertEqual(dead[-1]["status"], "playing")
        # Taken east route printed, untaken south exit print-free.
        self.assertIn("9,1", dead[-1]["prints"])
        self.assertNotIn("5,2", dead[-1]["prints"])
        self.assertNotIn("5,3", dead[-1]["prints"])

    def test_boundary_wall_push_no_move_no_new_print(self):
        wall = self.r["wall"]
        self.assertEqual(wall[-1]["pos"], {"x": 9, "y": 1})
        self.assertNotIn("10,1", wall[-1]["prints"])

    def test_enemies_ignore_prints_blocked(self):
        self.skipTest("blocked-by: 31 (patroller): patroller mechanic not built; "
                      "sand prints are player-only meta and no controller reads them")

    def test_restart_clears_prints(self):
        self.assertEqual(self.r["freshPrints"], [])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_sand_prints(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("sand-prints.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/sand-tile/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right','right','right','right','down','down',
  'right','right','right','right','right','right',
  'left','left','left','left','left','left','up','up',
  'left','left','left','left'];
const log = inputs.map((input,i)=>({t_ms:(i+1)*100, input}));
let live = core.initialState(level, 'mech-45-sand-tile-room');
for (const e of log) live = core.step(live, e);
const replayed = core.replay(level, 'mech-45-sand-tile-room', log);
const replayed2 = core.replay(level, 'mech-45-sand-tile-room', JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: {pos:{...live.player}, orbs: core.readout(live).orbs_left},
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length-1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length-1]),
  replaySteps: replayed.length-1 }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"], {"pos": {"x": 1, "y": 1}, "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 24)


if __name__ == "__main__":
    unittest.main()
