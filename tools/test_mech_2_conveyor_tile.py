"""Checks for the conveyor tile (mech-2-conveyor-tile).

The mechanic lives in the pure GameCore step (packs/conveyor);
driven here under Node against the teaching room. Rules: stepping
onto a belt does not carry on that move; at the start of each later
move the belt carries the player exactly one tile in its arrow
direction, sideways inputs included; the player gets off only
where the belt ends on a normal tile. No YAML test_case for this
mechanic is blocked-by another mechanic, so none are skipped.

Run with: python -m unittest tools.test_mech_2_conveyor_tile -v
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

LEVEL_ID = "mech-2-conveyor-tile-room"


class ConveyorRoomLevelTests(unittest.TestCase):
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
        # Two belts meet on the normal tile at (6, 5): east to the
        # exit chamber, south to the void hazard at (6, 8).
        self.assertEqual(rows[5][6], ".")
        self.assertEqual(rows[5][7:10], ">>>")
        self.assertEqual(rows[6][6], "v")
        self.assertEqual(rows[7][6], "v")
        self.assertEqual(rows[8][6], "!")
        self.assertEqual(rows[5][12], "X")


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
  let s = core.initialState(level, 'mech-2-conveyor-tile-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toCenter = ['right', 'right', 'down', 'right'];
// A: solution — read the arrows, ride the east belt to the exit.
const a = run([...toCenter, 'right', 'right', 'right', 'right',
  'right', 'right']);
// B: adversarial — first belt south, sideways tries, hazard ends it.
const b = run([...toCenter, 'down', 'left', 'left']);
// C: sideways input on the east belt still carries east one tile.
const c = run([...toCenter, 'right', 'right', 'up']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-2-conveyor-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps,
  freshRow: core.initialState(level,
    'mech-2-conveyor-tile-room').grid[5],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class ConveyorMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_read_the_arrows_and_ride_to_exit(self):
        a = self.r["a"]
        self.assertEqual(a[4]["pos"], {"x": 6, "y": 5})
        # Entering the belt does not carry on the entry move.
        self.assertEqual(a[5]["pos"], {"x": 7, "y": 5})
        self.assertEqual(a[6]["pos"], {"x": 8, "y": 5})
        self.assertEqual(a[7]["pos"], {"x": 9, "y": 5})
        # Off only where the belt ends on a normal tile.
        self.assertEqual(a[8]["pos"], {"x": 10, "y": 5})
        self.assertEqual(a[10]["pos"], {"x": 12, "y": 5})
        self.assertEqual(a[10]["status"], "won")

    def test_adversarial_first_belt_carries_to_hazard(self):
        b = self.r["b"]
        self.assertEqual(b[5]["pos"], {"x": 6, "y": 6})
        # Sideways input cannot leave the belt: carried south.
        self.assertEqual(b[6]["pos"], {"x": 6, "y": 7})
        # Carried into the void hazard: attempt lost, never stranded.
        self.assertEqual(b[7]["pos"], {"x": 6, "y": 8})
        self.assertEqual(b[7]["status"], "lost")

    def test_one_tile_per_move_and_no_sideways_exit(self):
        c = self.r["c"]
        self.assertEqual(c[5]["pos"], {"x": 7, "y": 5})
        self.assertEqual(c[6]["pos"], {"x": 8, "y": 5})
        # 'up' from the belt resolves to exactly one tile east.
        self.assertEqual(c[7]["pos"], {"x": 9, "y": 5})
        self.assertEqual(c[7]["status"], "playing")

    def test_restart_restores_the_placed_belts(self):
        self.assertEqual(self.r["freshRow"], "#......>>>..X.#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_loads_the_conveyor_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/conveyor/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'down', 'right',
  'right', 'right', 'right', 'right',
  'right', 'up', 'up', 'up', 'right',
  'down', 'down', 'down', 'left'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-2-conveyor-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-2-conveyor-tile-room', log);
const replayed2 = core.replay(level, 'mech-2-conveyor-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
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
                         {"pos": {"x": 12, "y": 5}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 17)


if __name__ == "__main__":
    unittest.main()
