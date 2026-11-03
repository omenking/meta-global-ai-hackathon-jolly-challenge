"""Checks for the power gloves (mech-89-power-gloves).

The mechanic lives in the pure GameCore step (packs/power-gloves);
driven here under Node against the teaching room. Rules: gloves
held in a slot; a heavy block moves in one push with the gloves
(strain skipped) and two consecutive pushes without; pushing a
block into a line shifts the whole line only with the gloves and
only when the tile beyond the far block is empty floor or a switch
plate. YAML cases blocked by unbuilt mechanics 81/87 are explicit
skips below, never fake passes; the same behaviours are verified
pack-locally against this pack's own block stand-ins.

Run with: python -m unittest tools.test_mech_89_power_gloves -v
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

LEVEL_ID = "mech-89-power-gloves-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "power-gloves"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class PowerGlovesRoomLevelTests(unittest.TestCase):
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
        self.assertIn("g", grid)  # gloves pickup
        self.assertIn("H", grid)  # heavy block
        self.assertIn("S", grid)  # switch plate
        # Line of three ending one tile from a wall: BBB . #
        line_row = next(r for r in rows if "BBB" in r)
        self.assertEqual(line_row.count("B"), 3)
        self.assertEqual(grid.count("B"), 4)  # line + single below
        i = line_row.index("BBB")
        self.assertEqual(line_row[i + 3], ".")
        self.assertEqual(line_row[i + 4], "#")
        self.assertGreaterEqual(grid.count("*"), 1)
        self.assertIn("X", grid)


class PowerGlovesPackTests(unittest.TestCase):
    def test_manifest_lists_every_yaml_asset_bundled(self):
        manifest = json.loads((PACK / "manifest.json").read_text())
        self.assertEqual(manifest["pack"], "power-gloves")
        files = [a["file"] for a in manifest["assets"]]
        self.assertEqual(files, ["power-gloves.png",
                                 "power-gloves-collected.png",
                                 "jolly-power-gloves.png",
                                 "jolly-power-gloves-pushing.png",
                                 "jolly-line-push.png",
                                 "power-gloves-slot.png"])
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"], entry["file"])
            self.assertTrue(entry["shows"], entry["file"])
            path = PACK / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])

    def test_pack_declares_assets_and_tiles(self):
        js = (PACK / "main.js").read_text(encoding="utf-8")
        for name in ("power-gloves.png", "power-gloves-collected.png",
                     "jolly-power-gloves.png",
                     "jolly-power-gloves-pushing.png",
                     "jolly-line-push.png", "power-gloves-slot.png"):
            self.assertIn(name, js)
        self.assertIn("gloves:gloves", js)
        self.assertIn("gloves:push-block", js)
        self.assertIn("gloves:heavy-block", js)
        self.assertNotIn("Date.now", js)
        self.assertNotIn("Math.random", js)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-89-power-gloves-room');
  const snap = () => ({ pos: { ...s.player },
    inv: core.readout(s).inventory, grid: s.grid.slice(),
    flags: { ...s.flags },
    budge: Object.values(s.meta).map((m) => m.heavy_budge || null)
      .filter(Boolean) });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// A: gloves pickup fills a slot (right, right onto g at (3,1)).
const a = run(['right', 'right']);
// B: no gloves, walk west of the line and shove: nothing shifts.
const b = run(['down', 'down', 'down', 'down',
  'right', 'right', 'right']);
// C: gloves, route around the heavy block, shove the line twice:
// first shifts onto the free tile, second jams against the wall.
const c = run(['right', 'right', 'left',
  'down', 'down', 'down', 'down', 'right', 'right', 'right']);
// D: single push block moves without gloves.
const d = run(['down', 'down', 'down', 'down', 'down', 'down',
  'right', 'right']);
// E: heavy block without gloves: budge, then move; and a broken
// (non-consecutive) pair only budges twice.
const e = run(['down', 'down', 'right', 'right', 'right']);
const e2 = run(['down', 'down', 'right', 'right', 'up', 'down', 'right']);
// F: heavy block with gloves moves in one push, no budge.
const f = run(['right', 'right', 'left', 'down', 'down',
  'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-89-power-gloves-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ a, b, c, d, e, e2, f,
  fresh: { pos: { ...s0.player }, grid: s0.grid.slice() },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class PowerGlovesMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_gloves_held_in_a_slot(self):
        a = self.r["a"]
        self.assertEqual(a[2]["pos"], {"x": 3, "y": 1})
        self.assertEqual(a[2]["inv"], ["power-gloves"])
        self.assertNotIn("g", a[2]["grid"][1])

    def test_line_without_gloves_does_not_shift(self):
        b = self.r["b"]
        self.assertEqual(b[-1]["pos"], {"x": 3, "y": 5})
        self.assertEqual(b[-1]["grid"][5], "#...BBB.#.....#")
        self.assertEqual(b[-1]["inv"], [])

    def test_adversarial_shoving_a_line_into_a_wall(self):
        # YAML: adversarial shoving a line into a wall.
        c = self.r["c"]
        # First gloved shove shifts the whole line one tile.
        self.assertEqual(c[9]["grid"][5], "#....BBB#.....#")
        self.assertEqual(c[9]["pos"], {"x": 4, "y": 5})
        # Second shove: wall beyond the far block, nothing moves
        # and the player is not stranded (still playing, can walk).
        self.assertEqual(c[10]["grid"][5], "#....BBB#.....#")
        self.assertEqual(c[10]["pos"], {"x": 4, "y": 5})

    def test_single_block_pushes_without_gloves(self):
        d = self.r["d"]
        self.assertEqual(d[-1]["grid"][7], "#...B...X.....#")
        self.assertEqual(d[-1]["pos"], {"x": 3, "y": 7})

    def test_heavy_block_two_pushes_without_gloves_pack_local(self):
        e = self.r["e"]
        # First push budges only: block and player stay, strain set.
        self.assertEqual(e[4]["pos"], {"x": 2, "y": 3})
        self.assertEqual(e[4]["grid"][3], "#..H...S..*...#")
        self.assertEqual(e[4]["budge"], ["right"])
        # Second consecutive push moves it one tile.
        self.assertEqual(e[5]["pos"], {"x": 3, "y": 3})
        self.assertEqual(e[5]["grid"][3], "#...H..S..*...#")
        self.assertEqual(e[5]["budge"], [])

    def test_heavy_budge_needs_consecutive_pushes_pack_local(self):
        e2 = self.r["e2"]
        # Budge, step away and back, push again: only a fresh
        # budge, the block has still not moved.
        self.assertEqual(e2[-1]["pos"], {"x": 2, "y": 3})
        self.assertEqual(e2[-1]["grid"][3], "#..H...S..*...#")
        self.assertEqual(e2[-1]["budge"], ["right"])

    def test_heavy_block_one_push_with_gloves_pack_local(self):
        f = self.r["f"]
        self.assertEqual(f[-1]["pos"], {"x": 3, "y": 3})
        self.assertEqual(f[-1]["grid"][3], "#...H..S..*...#")
        self.assertEqual(f[-1]["budge"], [])
        self.assertTrue(f[-1]["flags"].get("gloves_heavy_one_push"))

    def test_restart_restores_room_and_step_is_pure(self):
        # YAML: restart and replay (fresh state part).
        self.assertEqual(self.r["fresh"]["grid"][5], "#...BBB.#.....#")
        self.assertEqual(self.r["fresh"]["grid"][3], "#..H...S..*...#")
        self.assertEqual(self.r["fresh"]["pos"], {"x": 1, "y": 1})
        self.assertTrue(self.r["pure"])

    def test_game_wires_power_gloves_pack(self):
        core_js = (ROOT / "tools" / "static" / "game-core.js").read_text()
        self.assertIn("packs/power-gloves/main.js", core_js)
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/power-gloves/main.js", html)
        js = (ROOT / "tools" / "static" / "game.js").read_text()
        self.assertIn("jolly-power-gloves.png", js)
        self.assertIn("dt.ch === 'B' || dt.ch === 'H'", js)


BOUNDARY_SCRIPT = r"""
const core = require(process.argv[1]);
const LEGEND = {
  '.': { label: 'floor' }, '#': { label: 'wall' },
  'P': { label: 'player' },
  'g': { label: 'gloves', def: 'gloves:gloves' },
  'B': { label: 'push block', def: 'gloves:push-block' },
  'S': { label: 'switch plate', def: 'gloves:switch-plate' },
  'L': { label: 'lock red', lock_color: 'red' },
  '*': { label: 'orb' },
  '~': { label: 'water', def: 'water:water' },
  'd': { label: 'deep water', def: 'gloves:deep-water' },
  'v': { label: 'void terrain', def: 'gloves:void' },
  'V': { label: 'void object', def: 'crumble:void' },
  'f': { label: 'fire', def: 'gloves:fire' },
  'l': { label: 'lava', def: 'gloves:lava' } };
function trial(dest) {
  const lvl = { rows: ['#######', '#PgBB' + dest + '#', '#######'],
    legend: LEGEND, time_limit: 120 };
  let s = core.initialState(lvl, 'trial');
  s = core.step(s, { t_ms: 100, input: 'right' }); // collect gloves
  s = core.step(s, { t_ms: 200, input: 'right' }); // shove the line
  return { pos: { ...s.player }, row: s.grid[1],
    beyondTerrain: s.terrain[1][5],
    inv: core.readout(s).inventory };
}
const out = {};
for (const dest of ['.', 'S', '#', 'L', '*', '~', 'd', 'v', 'V', 'f', 'l']) {
  out[dest] = trial(dest);
}
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class PowerGlovesBoundaryTests(unittest.TestCase):
    """Pack-local far-tile checks (the YAML 81 case itself is
    skipped below: push block 81 is not on main yet)."""

    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BOUNDARY_SCRIPT)

    def test_line_shifts_onto_empty_floor_or_switch_pack_local(self):
        self.assertEqual(self.r["."]["row"], "#P..BB#")
        self.assertEqual(self.r["."]["pos"], {"x": 3, "y": 1})
        self.assertEqual(self.r["S"]["row"], "#P..BB#")
        self.assertEqual(self.r["S"]["pos"], {"x": 3, "y": 1})
        self.assertEqual(self.r["S"]["beyondTerrain"],
                         "gloves:switch-plate")

    def test_far_tile_stops_the_whole_line_pack_local(self):
        for dest in ("#", "L", "*", "~", "d", "v", "V", "f", "l"):
            with self.subTest(dest=dest):
                self.assertEqual(self.r[dest]["pos"], {"x": 2, "y": 1})
                # Both blocks stay at their placed tiles (3 and 4).
                self.assertEqual(self.r[dest]["row"][3:5], "BB")


class YamlBlockedByTests(unittest.TestCase):
    """Every YAML test_cases entry for mechanic 89. Entries whose
    check is marked blocked-by another unbuilt mechanic are
    explicit skips with the reason, never fake passes."""

    @unittest.skip("blocked-by: 87 (heavy block): heavy block pack "
                   "is not on main yet; pack-local one-push verified "
                   "in PowerGlovesMechanicTests")
    def test_yaml_solution_one_push_heavy_block_and_line_shift(self):
        pass

    @unittest.skip("blocked-by: 81 (push block): push block pack is "
                   "not on main yet; pack-local far-tile verified "
                   "in PowerGlovesBoundaryTests")
    def test_yaml_boundary_far_tile_decides_the_whole_line(self):
        pass

    @unittest.skip("blocked-by: 87 (heavy block): heavy block pack "
                   "is not on main yet; pack-local two-push verified "
                   "in PowerGlovesMechanicTests")
    def test_yaml_boundary_heavy_block_one_push_not_two(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'left',
  'down', 'down', 'right', 'right', 'right', 'right',
  'left', 'left', 'left', 'down', 'down', 'right',
  'down', 'left', 'left', 'down', 'right',
  'up', 'right', 'right', 'right', 'right', 'right', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-89-power-gloves-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-89-power-gloves-room', log);
const replayed2 = core.replay(level, 'mech-89-power-gloves-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row3: live.grid[3], row5: live.grid[5], row7: live.grid[7],
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        # YAML: restart and replay (recorded session part).
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["replaySteps"], 27)
        # Heavy block pushed onto the switch plate, line shifted,
        # single block pushed, warp reached.
        self.assertEqual(self.r["row3"], "#......H..*...#")
        self.assertEqual(self.r["row5"], "#....BBB#.....#")
        self.assertEqual(self.r["row7"], "#...B...X.....#")
        self.assertEqual(self.r["liveFinal"]["status"], "won")


if __name__ == "__main__":
    unittest.main()
