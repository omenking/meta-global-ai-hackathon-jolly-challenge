"""Checks for deep water (mech-41-deep-water).

The mechanic lives in the deep-water pack (packs/deep-water/main.js)
as pure terrain/object hooks in the GameCore step; driven here under
Node against the teaching room. Rules: without the life preserver,
entering deep water returns the player to the active checkpoint
with the timer running; with it, each deep tile takes two inputs,
the first wading in place; restart (fresh state) restores the room.

Covers every test_cases entry for mechanic #41 in
plans/level-design/candidate-mechanics/terrain-and-hazards.yml.
The preserver (61) and checkpoint (48) surfaces are defined
in-pack in minimal form so the room is playable standalone;
their standalone features refine them later.

Run with: python -m unittest tools.test_mech_41_deep_water -v
"""
import json
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

LEVEL_ID = "mech-41-deep-water-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class DeepWaterRoomLevelTests(unittest.TestCase):
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
        self.assertIn("L", grid)
        cross_row = next(r for r in rows if "WWW" in r)
        self.assertEqual(cross_row.count("W"), 3)
        # Checkpoint and preserver sit on the near bank, west of
        # the water, and the preserver can be bypassed on the
        # crossing row so the naive entry really has no preserver.
        self.assertLess(grid.index("K"), grid.index("W"))
        self.assertLess(rows[1].index("L"), rows[1].index("#", 4))
        self.assertEqual(rows[2][4], ".")
        self.assertGreaterEqual(grid.count("*"), 2)
        # The long way back: the bottom row crosses the divider
        # line on plain floor, so the room never soft-locks.
        bottom = rows[-2]
        self.assertEqual(bottom[5:8], "...")


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-41-deep-water-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    inv: core.readout(s).inventory, orbs: core.readout(s).orbs_left,
    steps: s.steps,
    wade: (s.meta['5,2'] || {}).deep_wade || 0 });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
// Naive: touch the checkpoint, drop to the crossing row, wade in
// without ever picking up the preserver.
const naive = run(['right', 'right', 'down', 'right', 'right']);
// Naive without touching the checkpoint first.
const naiveNoCp = run(['down', 'right', 'right', 'right', 'right']);
// Corrected: pick up the preserver, then cross WWW to the bank.
const cross = run(['right', 'right', 'right', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right']);
// Hesitation: enter one deep tile, step back out, wade again.
const hes = run(['right', 'right', 'right', 'down',
  'right', 'right', 'left', 'right', 'right']);
const s0 = core.initialState(level, 'mech-41-deep-water-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  naive: naive.snaps, naiveNoCp: naiveNoCp.snaps,
  cross: cross.snaps, hes: hes.snaps,
  fresh: (() => { const f = core.initialState(level,
    'mech-41-deep-water-room');
    return { pos: { ...f.player }, inv: core.readout(f).inventory,
      orbs: core.readout(f).orbs_left, row: f.grid[2] }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class DeepWaterMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_without_preserver_returns_to_checkpoint_timer_running(self):
        n = self.r["naive"]
        self.assertEqual(n[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(n[4]["inv"], [])
        # Entering deep water sends the player back to the touched
        # checkpoint (3,1); the run is still playing, not lost.
        self.assertEqual(n[5]["pos"], {"x": 3, "y": 1})
        self.assertEqual(n[5]["status"], "playing")
        self.assertEqual(n[5]["steps"], 5)

    def test_without_checkpoint_touch_returns_to_spawn(self):
        n = self.r["naiveNoCp"]
        self.assertEqual(n[5]["pos"], {"x": 1, "y": 1})
        self.assertEqual(n[5]["status"], "playing")

    def test_with_preserver_crossing_costs_two_moves_per_tile(self):
        c = self.r["cross"]
        self.assertEqual(c[3]["inv"], ["life-preserver"])
        self.assertEqual(c[4]["pos"], {"x": 4, "y": 2})
        # First input on each deep tile wades in place.
        self.assertEqual(c[5]["pos"], {"x": 4, "y": 2})
        self.assertEqual(c[5]["wade"], 1)
        self.assertEqual(c[6]["pos"], {"x": 5, "y": 2})
        self.assertEqual(c[7]["pos"], {"x": 5, "y": 2})
        self.assertEqual(c[8]["pos"], {"x": 6, "y": 2})
        self.assertEqual(c[9]["pos"], {"x": 6, "y": 2})
        self.assertEqual(c[10]["pos"], {"x": 7, "y": 2})
        # Leaving the last deep tile onto the bank is one move.
        self.assertEqual(c[11]["pos"], {"x": 8, "y": 2})
        self.assertEqual(c[11]["status"], "playing")

    def test_adversarial_hesitation_never_strands_the_player(self):
        h = self.r["hes"]
        self.assertEqual(h[6]["pos"], {"x": 5, "y": 2})
        # Stepping back out to the bank takes one move, and
        # re-entering wades then crosses: never stranded.
        self.assertEqual(h[7]["pos"], {"x": 4, "y": 2})
        self.assertEqual(h[8]["pos"], {"x": 4, "y": 2})
        self.assertEqual(h[9]["pos"], {"x": 5, "y": 2})
        for snap in h:
            self.assertEqual(snap["status"], "playing")

    def test_restart_restores_the_room(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1}, "inv": [],
                          "orbs": 2, "row": "#....WWW....#"})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_assets_and_wiring(self):
        pack = ROOT / "tools" / "static" / "packs" / "deep-water"
        manifest = json.loads(
            (pack / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "deep-water")
        for entry in manifest["assets"]:
            if not entry["bundled"]:
                continue
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", entry["file"])
            self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512),
                             entry["file"])
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/deep-water/main.js", html)
        main = (pack / "main.js").read_text(encoding="utf-8")
        self.assertIn("deep:water", main)
        self.assertIn("defineAsset", main)
        game_js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("jolly-wading.png", game_js)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'up', 'right', 'left',
  'down', 'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left',
  'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-41-deep-water-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-41-deep-water-room', log);
const replayed2 = core.replay(level, 'mech-41-deep-water-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    orbs: core.readout(live).orbs_left },
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
                         {"pos": {"x": 10, "y": 6}, "status": "won",
                          "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 33)


if __name__ == "__main__":
    unittest.main()
