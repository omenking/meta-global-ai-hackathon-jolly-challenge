"""Checks for the fire tile (mech-43-fire-tile).

The mechanic lives in the pure GameCore step (packs/fire-tile);
driven here under Node against the teaching room. Rules: fire on
grass/wood is lethal while burning; every 10 moves each fire
spreads to one adjacent flammable tile (never stone); each fire
burns out after 30 moves leaving safe scorched floor; restart
(fresh state) restores placed fires. The ice-cancels-fire case is
blocked-by mechanic 82 (ice block, not yet built) and is an
explicit skipped-with-reason check, never a fake pass.

Run with: python -m unittest tools.test_mech_43_fire_tile -v
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

LEVEL_ID = "mech-43-fire-tile-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class FireRoomLevelTests(unittest.TestCase):
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
        self.assertGreaterEqual(grid.count("*"), 2)
        self.assertGreaterEqual(grid.count("F"), 2)
        self.assertIn("ggggg", rows[2])  # grass return path
        self.assertIn("www", rows[5])  # wood is flammable too
        # Fire beside the return path, orb beyond it.
        self.assertEqual(rows[3][5], "F")
        self.assertEqual(rows[2][10], "*")


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-43-fire-tile-room');
  const snap = () => ({ pos: { ...s.player }, grid: s.grid.slice(),
    status: s.status, steps: s.steps,
    orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const wait = (n) => Array(n).fill('up');
const solution = ['down', ...Array(9).fill('right'),
  ...Array(4).fill('left'), 'down', 'down',
  ...Array(4).fill('left'), 'up', 'up', 'left', 'up'];
const naive = ['down', ...Array(9).fill('right'),
  ...Array(5).fill('left')];
const crossScorched = [...wait(30), 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'up'];
const s0 = core.initialState(level, 'mech-43-fire-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  init: run([])[0], w9: run(wait(9)).at(-1), w10: run(wait(10)).at(-1),
  w20: run(wait(20)).at(-1), w30: run(wait(30)).at(-1),
  solution: run(solution), naive: run(naive).at(-1),
  scorched: run(crossScorched).at(-1),
  fresh: core.initialState(level, 'mech-43-fire-tile-room').grid,
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class FireMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_spread_follows_the_move_clock(self):
        # No spread before move 10; at move 10 fire spreads onto
        # the grass return path (5,2) and onto wood (6,5).
        self.assertNotIn("F", self.r["w9"]["grid"][2][5])
        self.assertEqual(self.r["w10"]["grid"][2][5], "F")
        self.assertEqual(self.r["w10"]["grid"][5][6], "F")
        # Never onto stone: neighbours on stone stay floor.
        self.assertEqual(self.r["w20"]["grid"][3][6], ".")
        self.assertEqual(self.r["w20"]["grid"][4][5], ".")
        # One new tile per fire per spread tick (4 fires at move 10
        # from 2 placed, 6 at move 20).
        fires10 = sum(r.count("F") for r in self.r["w10"]["grid"])
        fires20 = sum(r.count("F") for r in self.r["w20"]["grid"])
        self.assertEqual((fires10, fires20), (4, 6))

    def test_burn_out_boundary(self):
        # Placed fires burn out at move 30 leaving scorched floor.
        self.assertEqual(self.r["w30"]["grid"][3][5], "H")
        self.assertEqual(self.r["w30"]["grid"][6][6], "H")
        # Scorched floor is safe to cross from that move on.
        s = self.r["scorched"]
        self.assertEqual(s["pos"], {"x": 5, "y": 3})
        self.assertEqual(s["status"], "playing")

    def test_fire_is_lethal_and_naive_return_fails(self):
        n = self.r["naive"]
        self.assertEqual(n["pos"], {"x": 5, "y": 2})
        self.assertEqual(n["status"], "lost")

    def test_corrected_action_succeeds_via_stone_detour(self):
        final = self.r["solution"][-1]
        self.assertEqual(final["pos"], {"x": 1, "y": 1})
        self.assertEqual(final["orbs"], 0)
        self.assertEqual(final["status"], "playing")

    def test_adversarial_waiting_game_still_resolves(self):
        # Waiting lets fire spread across the return path (move 10
        # grid above), yet burn-out + the stone detour mean the
        # room always resolves; no stranded state.
        self.assertEqual(self.r["w30"]["status"], "playing")
        self.assertEqual(self.r["solution"][-1]["orbs"], 0)

    def test_restart_restores_every_fire(self):
        self.assertEqual(self.r["fresh"], self.r["init"]["grid"])
        self.assertEqual(self.r["fresh"][3][5], "F")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_wiring(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("gc2 === 'F' ? 'fire.png'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/fire-tile/main.js", html)
        manifest = json.loads((ROOT / "tools" / "static" / "packs"
                               / "fire-tile" / "manifest.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "fire-tile")
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"])
            path = (ROOT / "tools" / "static" / "packs" / "fire-tile"
                    / "assets" / entry["file"])
            self.assertTrue(path.is_file(), entry["file"])

    @unittest.skip("blocked-by: 82 (ice block) — no ice block pack "
                   "exists yet; sliding an ice block into fire "
                   "cannot be exercised until mechanic 82 lands")
    def test_ice_cancels_fire(self):
        self.fail("unreachable while blocked-by 82")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', ...Array(9).fill('right'),
  ...Array(4).fill('left'), 'down', 'down',
  ...Array(4).fill('left'), 'up', 'up', 'left', 'up'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-43-fire-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-43-fire-tile-room', log);
const replayed2 = core.replay(level, 'mech-43-fire-tile-room',
  JSON.parse(JSON.stringify(log)));
const waitLog = Array.from({length: 30}, (_, i) =>
  ({ t_ms: (i + 1) * 100, input: 'up' }));
let live30 = core.initialState(level, 'mech-43-fire-tile-room');
for (const stepIn of waitLog) live30 = core.step(live30, stepIn);
const replay30 = core.replay(level, 'mech-43-fire-tile-room', waitLog);
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  live30Digest: core.stateDigest(live30),
  replay30Digest: core.stateDigest(
    replay30[replay30.length - 1]),
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
                         {"pos": {"x": 1, "y": 1}, "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 24)

    def test_recorded_30_move_session_replays_to_same_end_state(self):
        self.assertEqual(self.r["replay30Digest"],
                         self.r["live30Digest"])


if __name__ == "__main__":
    unittest.main()
