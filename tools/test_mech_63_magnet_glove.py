"""Checks for the magnet glove (mech-63-magnet-glove).

The mechanic lives in the magnet-glove pack plus a generic
before-move hook in the kernel; driven here under Node against the
teaching room. Rules: the glove is held in a slot; pressing toward
a metal block in a clear line within 3 tiles slides the block one
tile toward the player while the player stays; otherwise the
player moves normally; a wall in the line means no pull. Restart
(fresh state) restores the glove and the block.

YAML test_cases coverage (gear-and-items.yml, mechanic 63):
- solution pull in a clear line: run for real below. The entry is
  marked blocked-by 81 (push block) because the metal block is the
  push block in metal form; this pack defines the block tile and
  the pull, so the pull assertions run, and pushing (81's own
  behaviour) is not asserted anywhere here.
- adversarial pull from the wrong line: run for real.
- boundary three tiles and one-tile pull: run for real.
- boundary wall blocks the pull: run for real.
- adversarial pulling a block off its switch: blocked-by 29
  (weight switch); no weight switch or held door exists on main,
  so this is an explicit skipped-with-reason check, never faked.
- restart and replay: run for real (SanityReplayTests).

Run with: python -m unittest tools.test_mech_63_magnet_glove -v
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

LEVEL_ID = "mech-63-magnet-glove-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "magnet-glove"


class MagnetRoomLevelTests(unittest.TestCase):
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
        self.assertIn("g", grid)
        self.assertEqual(grid.count("M"), 1)
        # Block at (6,3) seals the orb nook: orb (6,2) flanked by walls.
        self.assertEqual(rows[2][6], "*")
        self.assertEqual(rows[2][5], "#")
        self.assertEqual(rows[2][7], "#")
        self.assertEqual(rows[3][6], "M")
        # Wall in the row pulling line, clear column pulling line.
        self.assertEqual(rows[3][4], "#")
        self.assertEqual(rows[4][6], ".")
        self.assertEqual(rows[5][6], ".")
        self.assertEqual(rows[6][6], ".")


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-63-magnet-glove-room');
  const snap = () => ({ pos: { ...s.player },
    inv: core.readout(s).inventory, status: s.status,
    orbs: core.readout(s).orbs_left,
    block: (() => { for (let y = 0; y < s.grid.length; y++) {
      const x = s.grid[y].indexOf('M'); if (x >= 0) return { x, y }; }
      return null; })() });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const glove = ['right', 'right'];
const toBelow = [...glove, 'down', 'down', 'down', 'down', 'down',
  'right', 'right', 'right']; // stands at (6,6), block 3 above
// A: solution pulls in the clear column line, then finishes the room.
const a = run([...toBelow, 'up', 'up', 'up', 'left', 'up', 'up', 'up',
  'right', 'up', 'up', 'left', 'left', 'left',
  'down', 'down', 'down', 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right']);
// B: naive pull along the block's row, where a wall is in the line.
const b = run([...glove, 'down', 'down', 'right', 'right']);
// C: boundary distances from (6,7) then (6,6), (6,5).
const c = run([...toBelow, 'down', 'up', 'up', 'up']);
// D: repeated presses with the wall in the line never pull.
const d = run([...glove, 'down', 'down', 'right', 'right', 'right']);
// E: without the glove the same press just moves normally.
const e = run(['down', 'down', 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'up']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-63-magnet-glove-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ a, b, c, d, e,
  fresh: (() => { const f = core.initialState(level,
    'mech-63-magnet-glove-room');
    return { pos: { ...f.player }, inv: core.readout(f).inventory,
      row3: f.grid[3] }; })(),
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MagnetMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_glove_is_held_in_a_slot(self):
        a = self.r["a"]
        self.assertEqual(a[1]["inv"], [])
        self.assertEqual(a[2]["inv"], ["magnet-glove"])
        # Held for the rest of the room, including at the win.
        self.assertEqual(a[-1]["inv"], ["magnet-glove"])

    def test_solution_pull_in_a_clear_line(self):
        a = self.r["a"]
        # Standing at (6,6); each press pulls one tile, player stays.
        self.assertEqual(a[10]["pos"], {"x": 6, "y": 6})
        self.assertEqual(a[10]["block"], {"x": 6, "y": 3})
        self.assertEqual(a[11]["pos"], {"x": 6, "y": 6})
        self.assertEqual(a[11]["block"], {"x": 6, "y": 4})
        self.assertEqual(a[12]["block"], {"x": 6, "y": 5})
        # Adjacent now: a further press cannot pull it onto the player.
        self.assertEqual(a[13]["pos"], {"x": 6, "y": 6})
        self.assertEqual(a[13]["block"], {"x": 6, "y": 5})
        # Retrieved block frees the nook orb; gate opens; room is won.
        self.assertEqual(a[-1]["status"], "won")
        self.assertEqual(a[-1]["orbs"], 0)

    def test_adversarial_pull_from_the_wrong_line(self):
        b = self.r["b"]
        # (2,3)->(3,3) moves normally; pressing into the wall line
        # pulls nothing, however the player got there.
        self.assertEqual(b[4]["pos"], {"x": 3, "y": 3})
        self.assertEqual(b[4]["block"], {"x": 6, "y": 3})
        self.assertEqual(b[5]["pos"], {"x": 3, "y": 3})
        self.assertEqual(b[5]["block"], {"x": 6, "y": 3})
        self.assertEqual(b[5]["status"], "playing")

    def test_boundary_three_tiles_and_one_tile_pull(self):
        c = self.r["c"]
        # From (6,7) the block is 4 away: no pull, player moves.
        self.assertEqual(c[10]["pos"], {"x": 6, "y": 6})
        self.assertEqual(c[11]["pos"], {"x": 6, "y": 7})
        self.assertEqual(c[11]["block"], {"x": 6, "y": 3})
        self.assertEqual(c[12]["pos"], {"x": 6, "y": 6})
        self.assertEqual(c[12]["block"], {"x": 6, "y": 3})
        # Exactly 3 away: pulled one tile, player stays.
        self.assertEqual(c[13]["pos"], {"x": 6, "y": 6})
        self.assertEqual(c[13]["block"], {"x": 6, "y": 4})

    def test_boundary_wall_blocks_the_pull(self):
        d = self.r["d"]
        for snap in d[3:]:
            self.assertEqual(snap["block"], {"x": 6, "y": 3})
            self.assertEqual(snap["status"], "playing")

    def test_without_the_glove_you_move_normally(self):
        e = self.r["e"]
        self.assertEqual(e[-1]["inv"], [])
        self.assertEqual(e[-1]["pos"], {"x": 6, "y": 5})
        self.assertEqual(e[-1]["block"], {"x": 6, "y": 3})

    def test_restart_restores_glove_and_block(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1}, "inv": [],
                          "row3": "#...#.M.....#"})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_is_wired_into_the_game(self):
        js = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("packs/magnet-glove/main.js", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/magnet-glove/main.js", html)


class MagnetAssetTests(unittest.TestCase):
    def test_manifest_lists_every_yaml_asset_bundled_with_file(self):
        import struct
        manifest = json.loads((PACK / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "magnet-glove")
        expected = ["magnet-glove.png", "magnet-glove-collected.png",
                    "jolly-magnet-glove.png", "jolly-magnet-pulling.png",
                    "magnet-glove-slot.png", "metal-block.png"]
        self.assertEqual([a["file"] for a in manifest["assets"]], expected)
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"], entry["file"])
            self.assertTrue(entry["shows"], entry["file"])
            path = PACK / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", entry["file"])
            self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512),
                             entry["file"])


class BlockedBySwitchTests(unittest.TestCase):
    @unittest.skip("blocked-by: 29 (weight switch): no weight switch "
                   "or held door exists on main, so pulling a block "
                   "off its switch cannot be exercised yet")
    def test_pulling_a_block_off_its_switch(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right',
  'down', 'down', 'down', 'down', 'down', 'right', 'right', 'right',
  'up', 'up', 'up', 'left', 'up', 'up', 'up', 'right', 'up',
  'up', 'left', 'left', 'left',
  'down', 'down', 'down', 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-63-magnet-glove-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-63-magnet-glove-room', log);
const replayed2 = core.replay(level, 'mech-63-magnet-glove-room',
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
                         {"pos": {"x": 11, "y": 7}, "status": "won",
                          "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 37)


if __name__ == "__main__":
    unittest.main()
