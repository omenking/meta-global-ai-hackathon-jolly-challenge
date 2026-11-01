"""Checks for the ice cleats (mech-62-ice-cleats).

The mechanic lives in the pure GameCore step (packs/ice-cleats);
driven here under Node against the teaching room. Rules: picking
the cleats up fills one inventory slot for the rest of the level;
while held, ice tiles behave as normal floor (no slide, stop and
turn, one move per tile); all other movement is unchanged. The
YAML cases marked blocked-by (1 ice tile, 82 ice block) get
explicit skipped-with-reason checks, never a fake pass: the ice
tile pack is not built on main, so the room's slide baseline is
the pack-local terrain documented in packs/ice-cleats/main.js.

Run with: python -m unittest tools.test_mech_62_ice_cleats -v
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

LEVEL_ID = "mech-62-ice-cleats-room"


class CleatsRoomLevelTests(unittest.TestCase):
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
        self.assertIn("K", grid)
        strip = next(r for r in rows if "I" in r)
        # Orb sits in the middle of the ice strip, wall brakes it.
        self.assertEqual(strip.count("I"), 5)
        self.assertIn("o", strip)
        self.assertLess(strip.index("K"), strip.index("I"))
        self.assertLess(strip.index("I"), strip.index("o"))
        self.assertEqual(strip[strip.rindex("I") + 1], "#")
        # Floor rows around the strip: the room never strands.
        self.assertIn(".", rows[1])
        self.assertIn(".", rows[3])


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
  let s = core.initialState(level, 'mech-62-ice-cleats-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    inv: core.readout(s).inventory, row: s.grid[2] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// Pickup: spawn (1,1) -> down, right onto the cleats at (2,2).
const pickup = run(['down', 'right']);
// Boundary: with cleats, one tile per input on ice, stop, turn.
const boundary = run(['down', 'right', 'right', 'right',
  'right', 'right', 'right', 'right', 'left',
  'right', 'right', 'right', 'right', 'right']);
// Naive: no cleats, slide in from the west and back again.
const naive = run(['right', 'right', 'right', 'down', 'right', 'left']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-62-ice-cleats-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  pickup: pickup, boundary: boundary, naive: naive,
  freshRow: core.initialState(level,
    'mech-62-ice-cleats-room').grid[2],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class CleatsMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_pickup_fills_one_slot_for_the_level(self):
        p = self.r["pickup"]
        self.assertEqual(p[2]["pos"], {"x": 2, "y": 2})
        self.assertEqual(p[2]["inv"], ["cleats"])
        # The pickup tile is empty behind the player.
        self.assertNotIn("K", p[2]["row"])

    def test_boundary_stop_and_turn_on_ice(self):
        b = self.r["boundary"]
        # From the floor edge (4,2) each input moves exactly one
        # ice tile: no slide while wearing the cleats.
        self.assertEqual(b[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(b[5]["pos"], {"x": 5, "y": 2})
        self.assertEqual(b[6]["pos"], {"x": 6, "y": 2})
        self.assertEqual(b[7]["pos"], {"x": 7, "y": 2})
        self.assertEqual(b[8]["pos"], {"x": 8, "y": 2})
        self.assertEqual(b[8]["orbs"], 0)
        # Turning on the ice walks one tile back, never a slide.
        self.assertEqual(b[9]["pos"], {"x": 7, "y": 2})
        # Standing at the last ice tile, pressing into the braking
        # wall stays put: no slide is ever started by waiting/turning.
        self.assertEqual(b[12]["pos"], {"x": 10, "y": 2})
        self.assertEqual(b[13]["pos"], {"x": 10, "y": 2})
        self.assertEqual(b[14]["pos"], {"x": 10, "y": 2})
        self.assertEqual(b[14]["inv"], ["cleats"])
        self.assertEqual(b[14]["status"], "playing")

    def test_naive_slide_passes_orb_and_never_strands(self):
        n = self.r["naive"]
        # Without cleats the entry step slides to the braking wall,
        # passing the mid-ice orb without collecting it.
        self.assertEqual(n[5]["pos"], {"x": 10, "y": 2})
        self.assertEqual(n[5]["orbs"], 1)
        self.assertEqual(n[5]["inv"], [])
        # Sliding back west stops on the floor beyond the strip:
        # the room resolves by walking back, never stranded on ice.
        self.assertEqual(n[6]["pos"], {"x": 4, "y": 2})
        self.assertEqual(n[6]["status"], "playing")

    def test_restart_restores_pickup_and_empty_slot(self):
        self.assertIn("K", self.r["freshRow"])
        self.assertEqual(self.r["pickup"][0]["inv"], [])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_the_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/ice-cleats/main.js", html)


class BlockedYamlCaseTests(unittest.TestCase):
    """YAML test_cases entries blocked by unbuilt mechanics."""

    @unittest.skip("blocked-by: 1 (ice tile) is not built on main; "
                   "the mid-ice orb collection contract settles with "
                   "that pack, so no fake pass is recorded here")
    def test_solution_mid_ice_orb_with_cleats(self):
        pass

    @unittest.skip("blocked-by: 1 (ice tile) is not built on main; "
                   "the slide-past-the-orb contract settles with "
                   "that pack, so no fake pass is recorded here")
    def test_adversarial_slide_without_cleats(self):
        pass

    @unittest.skip("blocked-by: 82 (ice block) is not built on main; "
                   "pushing from ice settles with that pack, so no "
                   "fake pass is recorded here")
    def test_pushing_from_ice_with_cleats(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'right', 'right', 'right',
  'right', 'right', 'right', 'right', 'left', 'left', 'left', 'left',
  'down', 'right', 'right', 'right', 'right', 'down', 'down',
  'left', 'left', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-62-ice-cleats-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-62-ice-cleats-room', log);
const replayed2 = core.replay(level, 'mech-62-ice-cleats-room',
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
                         {"pos": {"x": 6, "y": 6}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 22)


if __name__ == "__main__":
    unittest.main()
