"""Checks for the ice tile (mech-1-ice-tile).

The mechanic lives in the ice pack (packs/ice/main.js) as a pure
terrain hook in the GameCore step; driven here under Node against
the teaching room. Rules: stepping onto ice slides the player in
the entry direction within the same input until the next tile is
a wall, lock or block; no steering or stopping midway; orbs on
the line are collected; restart (fresh state) restores the room.

Covers every test_cases entry for mechanic #1 in
plans/level-design/candidate-mechanics/movement-tiles.yml:
solution, adversarial, no-steering, cleats (blocked-by 62,
skipped with reason), restart+replay.

Run with: python -m unittest tools.test_mech_1_ice_tile -v
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

LEVEL_ID = "mech-1-ice-tile-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class IceRoomLevelTests(unittest.TestCase):
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
        strip = next(r for r in rows if "I" in r)
        # Ice strip with orbs on the ice and a braking wall east.
        self.assertIn("*", strip)
        self.assertGreaterEqual(strip.count("*"), 1)
        east_end = strip.index("#", strip.index("I"))
        self.assertTrue(all(c in "I*" for c in strip[strip.index("I"):east_end]),
                        "strip must be ice/orbs up to the braking wall")
        # A floor return corridor below the strip: never stranded.
        corridor = rows[rows.index(strip) + 1]
        self.assertIn(".", corridor)
        grid = "".join(rows)
        self.assertIn("P", grid)
        self.assertIn("G", grid)
        self.assertIn("X", grid)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-1-ice-tile-room');
  const snap = () => ({ pos: { ...s.player },
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toStrip = ['down', 'right'];
// A: solution east slide + win through the gate to the warp.
const a = run([...toStrip, 'right', 'down', 'left', 'down', 'down',
  'left', 'left', 'down']);
// B: south slide over the orb column (no stop on the orb).
const b = run(['right', 'right', 'right', 'right', 'right', 'down']);
// C: east slide then west slide back across the strip.
const c = run([...toStrip, 'right', 'left']);
const s0 = core.initialState(level, 'mech-1-ice-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps,
  aFinal: { pos: { ...a.final.player }, status: a.final.status,
    orbs: core.readout(a.final).orbs_left },
  fresh: (() => { const f = core.initialState(level,
    'mech-1-ice-tile-room');
    return { pos: { ...f.player }, orbs: core.readout(f).orbs_left,
      row: f.grid[2] }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class IceMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_slide_collects_orbs_and_stops_at_braking_wall(self):
        a = self.r["a"]
        # Standing on floor west of the strip before the slide.
        self.assertEqual(a[2]["pos"], {"x": 2, "y": 2})
        # One east input slides the whole strip, collects both
        # orbs on the line, and stops only at the braking wall.
        self.assertEqual(a[3]["pos"], {"x": 9, "y": 2})
        self.assertEqual(a[3]["orbs"], 0)
        self.assertEqual(a[3]["status"], "playing")

    def test_adversarial_straight_slide_passes_orb_then_return_route_wins(self):
        a = self.r["a"]
        # The naive straight slide does not stop on either orb
        # tile (x=6 / x=8, y=2); it ends at the wall.
        self.assertNotIn(a[3]["pos"], [{"x": 6, "y": 2}, {"x": 8, "y": 2}])
        # The return route (corridor, gate, warp) resolves the
        # room: never a stranded slide.
        self.assertEqual(self.r["aFinal"],
                         {"pos": {"x": 6, "y": 6}, "status": "won", "orbs": 0})
        for snap in a:
            self.assertNotEqual(snap["status"], "lost")

    def test_no_steering_or_stopping_midway(self):
        b = self.r["b"]
        # Entering the orb's ice tile heading south in one input
        # passes over it (collected) and stops on floor beyond.
        self.assertEqual(b[5]["pos"], {"x": 6, "y": 1})
        self.assertEqual(b[6]["pos"], {"x": 6, "y": 3})
        self.assertEqual(b[6]["orbs"], 1)

    def test_slide_is_atomic_in_entry_direction_and_releases_after(self):
        c = self.r["c"]
        # West slide back crosses the whole strip in one input
        # and stops on the floor west of the strip.
        self.assertEqual(c[3]["pos"], {"x": 9, "y": 2})
        self.assertEqual(c[4]["pos"], {"x": 2, "y": 2})
        self.assertEqual(c[4]["status"], "playing")

    def test_cleats_stop_and_turn(self):
        self.skipTest("blocked-by: 62 (ice cleats): ice cleats are "
                      "mechanic 62 in gear-and-items.yml, not built "
                      "yet; with cleats held the player can stop "
                      "and turn on ice where the bare slide could not")

    def test_restart_restores_ice_and_orbs(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1}, "orbs": 2,
                          "row": "#..III*I*I#...#"})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_assets_and_wiring(self):
        pack = ROOT / "tools" / "static" / "packs" / "ice"
        manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "ice")
        for entry in manifest["assets"]:
            if not entry["bundled"]:
                continue
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", entry["file"])
            self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512),
                             entry["file"])
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/ice/main.js", html)
        main = (pack / "main.js").read_text(encoding="utf-8")
        self.assertIn("ice:ice", main)
        self.assertIn("defineAsset", main)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'right', 'right', 'down', 'left', 'down',
  'down', 'left', 'left', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-1-ice-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-1-ice-tile-room', log);
const replayed2 = core.replay(level, 'mech-1-ice-tile-room',
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
                         {"pos": {"x": 6, "y": 6}, "status": "won", "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 10)


if __name__ == "__main__":
    unittest.main()
