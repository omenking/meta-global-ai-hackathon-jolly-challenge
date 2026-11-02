"""Checks for the map tile (mech-55-map-tile).

The mechanic lives in the pure GameCore step (packs/maptile):
stepping on the map tile consumes it (spent tile left behind) and
shows the whole level as an overlay for three seconds of recorded
t_ms while play continues, then it fades and never returns in the
attempt. Restart (fresh state) restores the unconsumed tile.

Covers every test_cases entry in vision-and-information.yml #55:
solution, adversarial, three-second boundary, consumed, restart
and replay. None is blocked-by another mechanic.

Run with: python -m unittest tools.test_mech_55_map_tile -v
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

LEVEL_ID = "mech-55-map-tile-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class MapRoomLevelTests(unittest.TestCase):
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
        self.assertIn("M", grid)
        # Short north branch ends at a blue lock; no blue key exists.
        self.assertIn("B", grid)
        self.assertNotIn('"key_color": "blue"', json.dumps(self.level))
        # Long south branch holds the red key for the red lock.
        self.assertIn("r", grid)
        self.assertIn("R", grid)
        self.assertGreaterEqual(grid.count("*"), 1)
        # Map tile sits at the entrance, before the branch point.
        spawn = next((x, y) for y, r in enumerate(rows)
                     for x, ch in enumerate(r) if ch == "P")
        map_pos = next((x, y) for y, r in enumerate(rows)
                       for x, ch in enumerate(r) if ch == "M")
        self.assertEqual(map_pos[1], spawn[1])
        self.assertGreater(map_pos[0], spawn[0])


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function snap(s) {
  return { pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    active: !!(s.flags && s.flags['map_overlay_active']),
    until: (s.flags && s.flags['map_overlay_until_ms']) || null,
    row1: s.grid[1] };
}
function run(pairs) {
  let s = core.initialState(level, 'mech-55-map-tile-room');
  const snaps = [snap(s)];
  for (const [input, t] of pairs) {
    s = core.step(s, { t_ms: t, input });
    snaps.push(snap(s));
  }
  return { snaps, final: s };
}
const at100 = (inputs) => inputs.map((input, i) => [input, (i + 1) * 100]);
// Solution: step on map, take the long south branch (red key ->
// red lock -> orb -> gate -> warp).
const solutionInputs = [...at100(['right', 'right']),
  ...['down','down','down','down','down','down',
      'right','right','right','right','right','right','right','right',
      'right','right',
      'up','up','up','up','up','up','right',
      'down','down','down','down','down','down','right']
    .map((input, i) => [input, 300 + i * 100])];
const solution = run(solutionInputs);
// Adversarial: glance and run down the short north branch into
// the blue lock, then backtrack and finish the long way.
const naiveInputs = [...at100(['right','right','right','right','right',
    'right','right','right','right']),
  ...['down','down','down','down','down','down',
      'left','left','left','left',
      'right','right','right','right','right','right','right','right',
      'up','up','up','up','up','up','right',
      'down','down','down','down','down','down','right']
    .map((input, i) => [input, 1000 + i * 100])];
const naive = run(naiveInputs);
// Boundary: explicit recorded clock around the 3000ms window.
const boundary = run([['right', 1000], ['right', 2000], ['right', 3000],
  ['right', 4000], ['down', 4999], ['down', 5000], ['down', 5100]]);
// Consumed: trigger, leave, wait past the window, step back on.
const consumed = run([['right', 100], ['right', 200], ['left', 300],
  ['left', 4000], ['right', 4100], ['right', 4200]]);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-55-map-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution: solution.snaps, naive: naive.snaps,
  boundary: boundary.snaps, consumed: consumed.snaps,
  freshRow1: core.initialState(level, 'mech-55-map-tile-room').grid[1],
  freshFlags: core.initialState(level, 'mech-55-map-tile-room').flags,
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MapMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_read_the_glimpse_then_choose(self):
        snaps = self.r["solution"]
        # Stepping on the map tile (snap 2) fires the overlay.
        self.assertEqual(snaps[2]["pos"], {"x": 3, "y": 1})
        self.assertTrue(snaps[2]["active"])
        self.assertEqual(snaps[2]["until"], 3200)
        # The corrected long branch finishes the room.
        self.assertEqual(snaps[-1]["status"], "won")
        self.assertEqual(snaps[-1]["orbs"], 0)
        self.assertEqual(snaps[-1]["pos"], {"x": 15, "y": 7})

    def test_adversarial_glance_and_run(self):
        snaps = self.r["naive"]
        # The short branch is blocked at the blue lock (no key):
        # the player stays west of it, still playing, never lost.
        self.assertEqual(snaps[9]["pos"], {"x": 9, "y": 1})
        self.assertEqual(snaps[9]["status"], "playing")
        self.assertEqual(snaps[9]["orbs"], 1)
        # Backtracking out and taking the long branch still wins:
        # the wrong branch can be walked back out of, never stranded.
        self.assertEqual(snaps[-1]["status"], "won")
        self.assertEqual(snaps[-1]["orbs"], 0)

    def test_three_second_boundary_while_play_continues(self):
        b = self.r["boundary"]
        self.assertFalse(b[1]["active"])
        # Triggered at t_ms 2000, so the window ends at 5000.
        self.assertTrue(b[2]["active"])
        self.assertEqual(b[2]["until"], 5000)
        # Play continues under the overlay: positions keep moving.
        self.assertEqual(b[3]["pos"], {"x": 4, "y": 1})
        self.assertTrue(b[3]["active"])
        self.assertEqual(b[5]["pos"], {"x": 5, "y": 2})
        self.assertTrue(b[5]["active"])
        # At exactly 3000ms the view has faded and does not return.
        self.assertEqual(b[6]["pos"], {"x": 5, "y": 3})
        self.assertFalse(b[6]["active"])
        self.assertFalse(b[7]["active"])
        self.assertEqual(b[7]["status"], "playing")

    def test_consumed_after_one_step(self):
        c = self.r["consumed"]
        self.assertTrue(c[2]["active"])
        self.assertIn("m", c[2]["row1"])
        # Back on the spent tile after the window: no second overlay.
        self.assertEqual(c[6]["pos"], {"x": 3, "y": 1})
        self.assertFalse(c[6]["active"])
        self.assertEqual(c[6]["until"], 3200)

    def test_restart_restores_the_map_tile(self):
        self.assertIn("M", self.r["freshRow1"])
        self.assertNotIn("map_overlay_active", self.r["freshFlags"])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_assets_and_rendering_wired(self):
        pack = ROOT / "tools" / "static" / "packs" / "maptile"
        manifest = json.loads((pack / "manifest.json").read_text())
        self.assertEqual(manifest["pack"], "maptile")
        bundled = [a["file"] for a in manifest["assets"] if a["bundled"]]
        self.assertEqual(bundled,
                         ["map.png", "map-spent.png", "map-overlay.png"])
        for name in bundled:
            self.assertTrue((pack / "assets" / name).is_file(), name)
        js = (ROOT / "tools" / "static" / "game.js").read_text()
        self.assertIn("map_overlay_active", js)
        self.assertIn("map-spent.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/maptile/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right','right',
  'down','down','down','down','down','down',
  'right','right','right','right','right','right','right','right',
  'right','right',
  'up','up','up','up','up','up','right',
  'down','down','down','down','down','down','right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-55-map-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-55-map-tile-room', log);
const replayed2 = core.replay(level, 'mech-55-map-tile-room',
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
                         {"pos": {"x": 15, "y": 7}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 32)


if __name__ == "__main__":
    unittest.main()
