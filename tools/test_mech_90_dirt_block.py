"""Checks for the dirt block (mech-90-dirt-block).

The mechanic lives in the pure GameCore step (packs/dirt-block);
driven here under Node against the teaching room and synthetic
mini-rooms. Rules (blocks.yml #90): on land it moves only onto
empty floor or a switch plate, exactly as a push block (81);
pushed into void, shallow water, deep water or lava it is
consumed and that one tile becomes permanent floor; fire blocks
it like a wall, because ice blocks (82) are the fire canceller.

YAML test_cases coverage: "solution fill the channel in order",
"adversarial fill the nearest tile first" and "restart and
replay" run for real in the teaching room. "One block fills
exactly one tile" runs for real across synthetic trials; void,
deep water and lava use this pack's local stand-in terrains
(dirt:void / dirt:deep / dirt:lava) because mechanics 41/44 and
crumbling's void terrain are not on main yet. "Fire blocks dirt"
runs its blocking half for real against dirt:fire; only the ice
block cancelling that fire is skipped below (blocked-by: 82).

Run with: python -m unittest tools.test_mech_90_dirt_block -v
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

LEVEL_ID = "mech-90-dirt-block-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "dirt-block"

# Corrected order: the far (west-lane) block fills the west
# channel tile first; the near (alcove) block is then pushed south
# onto the filled tile and east to fill the second tile.
SOLUTION = ['down', 'down', 'down', 'right',
            'right', 'right', 'right', 'right',
            'up', 'up', 'up', 'right',
            'down', 'down',
            'left', 'down',
            'right',
            'right', 'right', 'right', 'right']

# Naive order (teaching moment): the easy alcove block fills the
# nearest tile first, leaving the crossing half-finished; wading
# into the remaining water loses the attempt.
NAIVE = ['right', 'right', 'right', 'right', 'right', 'right',
         'down', 'down', 'left', 'down', 'right', 'right']


class DirtBlockRoomLevelTests(unittest.TestCase):
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
        # Two dirt blocks and a two-tile water channel, orb + warp.
        self.assertEqual(grid.count("D"), 2)
        self.assertEqual(grid.count("~"), 2)
        self.assertIn("P", grid)
        self.assertIn("*", grid)
        self.assertIn("X", grid)
        chan = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "~"]
        # The channel is two adjacent tiles in one divider row.
        self.assertEqual(chan, [(7, 4), (8, 4)])
        blocks = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "D"]
        # Far block west in the channel row; near block in the
        # north alcove above the channel's west tile.
        self.assertIn((3, 4), blocks)
        self.assertIn((7, 2), blocks)


def run_core(script, *extra):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL),
                          *extra],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function blocksOf(st) {
  const out = [];
  for (let y = 0; y < st.height; y++) for (let x = 0; x < st.width; x++) {
    if (st.objects[y][x] === 'dirt:dirt-block') out.push({ x, y });
  }
  return out;
}
function run(seq) {
  let s = core.initialState(level, 'mech-90-dirt-block-room');
  const snap = () => ({ pos: { ...s.player }, blocks: blocksOf(s),
    west: s.terrain[4][7], east: s.terrain[4][8], status: s.status });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const sol = run(JSON.parse(process.argv[3]));
const naive = run(JSON.parse(process.argv[4]));
const s0 = core.initialState(level, 'mech-90-dirt-block-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
const fresh = core.initialState(level, 'mech-90-dirt-block-room');
console.log(JSON.stringify({
  sol: sol.snaps, naive: naive.snaps,
  solFinal: { pos: { ...sol.final.player },
    orbs: core.readout(sol.final).orbs_left, status: sol.final.status },
  fresh: { blocks: blocksOf(fresh), west: fresh.terrain[4][7],
    east: fresh.terrain[4][8] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class DirtBlockMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT,
                         json.dumps(SOLUTION), json.dumps(NAIVE))

    def test_solution_fills_channel_in_order_and_crosses(self):
        sol = self.r["sol"]
        # West tile filled first by the far block (snap 8 stands
        # after the fourth eastward push).
        self.assertEqual(sol[8]["west"], "dirt:filled-floor")
        self.assertEqual(sol[8]["east"], "dirt:shallow")
        self.assertEqual(sol[8]["blocks"], [{"x": 7, "y": 2}])
        # Both tiles filled, both blocks spent, crossing wins.
        self.assertEqual(sol[-1]["west"], "dirt:filled-floor")
        self.assertEqual(sol[-1]["east"], "dirt:filled-floor")
        self.assertEqual(sol[-1]["blocks"], [])
        self.assertEqual(self.r["solFinal"],
                         {"pos": {"x": 11, "y": 4}, "orbs": 0,
                          "status": "won"})

    def test_adversarial_fill_nearest_tile_first(self):
        naive = self.r["naive"]
        # The easy alcove block fills the nearest (west) tile: the
        # crossing is half-finished and the far block still waits.
        self.assertEqual(naive[8]["west"], "dirt:filled-floor")
        self.assertEqual(naive[8]["east"], "dirt:shallow")
        self.assertEqual(naive[8]["blocks"], [{"x": 3, "y": 4}])
        self.assertEqual(naive[8]["status"], "playing")
        # Standing on the filled tile is safe; wading into the
        # remaining water loses the attempt (never stranded: the
        # room restarts, checked below).
        self.assertEqual(naive[11]["pos"], {"x": 7, "y": 4})
        self.assertEqual(naive[11]["status"], "playing")
        self.assertEqual(naive[12]["status"], "lost")

    def test_restart_restores_blocks_and_channel(self):
        self.assertEqual(self.r["fresh"]["blocks"],
                         [{"x": 7, "y": 2}, {"x": 3, "y": 4}])
        self.assertEqual(self.r["fresh"]["west"], "dirt:shallow")
        self.assertEqual(self.r["fresh"]["east"], "dirt:shallow")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])


SYNTHETIC_SCRIPT = r"""
const core = require(process.argv[1]);
const LEG = {
  '.': { label: 'floor', sprite: 'floor_default.png' },
  '#': { label: 'wall', sprite: 'wall.png' },
  'P': { base: 'floor_default.png', label: 'player', sprite: 'jolly.png' },
  'D': { base: 'floor_default.png', label: 'dirt block', def: 'dirt:dirt-block' },
  '~': { base: 'floor_default.png', label: 'shallow water', text: '~', def: 'dirt:shallow' },
  'W': { base: 'floor_default.png', label: 'deep water', text: 'W', def: 'dirt:deep' },
  'L': { base: 'floor_default.png', label: 'lava', text: 'L', def: 'dirt:lava' },
  'V': { base: 'floor_default.png', label: 'void', text: 'V', def: 'dirt:void' },
  'F': { base: 'floor_default.png', label: 'fire', text: 'F', def: 'dirt:fire' },
  'S': { base: 'floor_default.png', label: 'switch plate', text: 'S', def: 'dirt:switch-plate' },
};
function trial(rows, seq, probes) {
  const level = { name: 'mini', time_limit: 120, test: true,
    tile: 64, legend: LEG, rows };
  let s = core.initialState(level, 'mini');
  const blocks = (st) => {
    const out = [];
    for (let y = 0; y < st.height; y++) for (let x = 0; x < st.width; x++) {
      if (st.objects[y][x] === 'dirt:dirt-block') out.push({ x, y });
    }
    return out;
  };
  const start = { pos: { ...s.player }, blocks: blocks(s) };
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
  });
  const terrains = {};
  for (const [x, y] of probes) terrains[x + ',' + y] = s.terrain[y][x];
  return { start, end: { pos: { ...s.player }, blocks: blocks(s),
    status: s.status, terrains } };
}
const out = {
  floor: trial(['######', '#PD..#', '######'], ['right'], []),
  plate: trial(['######', '#PD.S#', '######'],
    ['right', 'right'], [[4, 1]]),
  wall: trial(['#####', '#PD##', '#####'], ['right'], [[3, 1]]),
  otherBlock: trial(['######', '#PDD.#', '######'], ['right'], []),
  fire: trial(['######', '#PDF.#', '######'], ['right'], [[3, 1]]),
  fillShallow: trial(['#####', '#PD~#', '#####'],
    ['right', 'right'], [[3, 1]]),
  fillDeep: trial(['#####', '#PDW#', '#####'], ['right'], [[3, 1]]),
  fillLava: trial(['#####', '#PDL#', '#####'], ['right'], [[3, 1]]),
  fillVoid: trial(['#####', '#PDV#', '#####'], ['right'], [[3, 1]]),
  exactlyOne: trial(['######', '#PD~~#', '######'],
    ['right'], [[3, 1], [4, 1]]),
};
// The block occupies its tile for a non-player actor.
const level = { name: 'mini', time_limit: 120, test: true, tile: 64,
  legend: LEG, rows: ['######', '#PD..#', '######'] };
const st = core.initialState(level, 'mini');
const def = core.getTileDef('dirt:dirt-block');
out.enemyOccupies = def.blocks(
  JSON.parse(JSON.stringify(st)),
  { x: 2, y: 1, def, meta: {} },
  { id: 'enemy-0', x: 1, y: 1 });
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SyntheticTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(
            ["node", "-e", SYNTHETIC_SCRIPT, str(CORE), str(LEVEL)],
            capture_output=True, text=True, check=True)
        cls.r = json.loads(out.stdout.strip().splitlines()[-1])

    def test_land_push_moves_one_tile_onto_floor(self):
        t = self.r["floor"]
        self.assertEqual(t["end"]["blocks"], [{"x": 3, "y": 1}])
        self.assertEqual(t["end"]["pos"], {"x": 2, "y": 1})

    def test_land_push_onto_switch_plate_moves(self):
        t = self.r["plate"]
        self.assertEqual(t["end"]["blocks"], [{"x": 4, "y": 1}])
        self.assertEqual(t["end"]["terrains"], {"4,1": "dirt:switch-plate"})

    def test_blocked_push_stays_put(self):
        for name in ("wall", "otherBlock"):
            t = self.r[name]
            self.assertEqual(t["end"]["blocks"], t["start"]["blocks"], name)
            self.assertEqual(t["end"]["pos"], t["start"]["pos"], name)
            self.assertEqual(t["end"]["status"], "playing", name)

    def test_one_block_fills_exactly_one_tile(self):
        for name in ("fillShallow", "fillDeep", "fillLava", "fillVoid"):
            t = self.r[name]
            self.assertEqual(t["end"]["terrains"],
                             {"3,1": "dirt:filled-floor"}, name)
            self.assertEqual(t["end"]["blocks"], [], name)
        # Single-push fills leave the player on the block's tile;
        # fillShallow takes a second step onto the filled floor
        # (covered by test_player_walks_safely_on_filled_floor).
        for name in ("fillDeep", "fillLava", "fillVoid"):
            self.assertEqual(self.r[name]["end"]["pos"],
                             {"x": 2, "y": 1}, name)
        one = self.r["exactlyOne"]
        self.assertEqual(one["end"]["terrains"],
                         {"3,1": "dirt:filled-floor",
                          "4,1": "dirt:shallow"})
        self.assertEqual(one["end"]["blocks"], [])

    def test_player_walks_safely_on_filled_floor(self):
        t = self.r["fillShallow"]
        self.assertEqual(t["end"]["pos"], {"x": 3, "y": 1})
        self.assertEqual(t["end"]["status"], "playing")

    def test_fire_blocks_dirt_and_does_not_consume_it(self):
        t = self.r["fire"]
        self.assertEqual(t["end"]["blocks"], [{"x": 2, "y": 1}])
        self.assertEqual(t["end"]["pos"], {"x": 1, "y": 1})
        self.assertEqual(t["end"]["terrains"], {"3,1": "dirt:fire"})
        self.assertEqual(t["end"]["status"], "playing")

    @unittest.skip("blocked-by: 82 (ice block) - the ice block is "
                   "not built on main, so an ice block cancelling "
                   "this fire cannot be exercised here; the dirt "
                   "side (fire blocks the push, block not consumed) "
                   "is covered for real above")
    def test_ice_block_cancels_the_fire(self):
        pass

    def test_block_occupies_its_tile_for_enemies(self):
        self.assertTrue(self.r["enemyOccupies"])


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = JSON.parse(process.argv[3]);
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-90-dirt-block-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-90-dirt-block-room', log);
const replayed2 = core.replay(level, 'mech-90-dirt-block-room',
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
        cls.r = run_core(SANITY_SCRIPT, json.dumps(SOLUTION))

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 11, "y": 4}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], len(SOLUTION))


class PackWiringTests(unittest.TestCase):
    def test_manifest_lists_bundled_assets_that_exist(self):
        manifest = json.loads((PACK / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "dirt-block")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["dirt-filled-floor.png", "dirt-block.png"])
        for entry in bundled:
            path = PACK / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]),
                             (512, 512), entry["file"])

    def test_game_page_loads_the_pack_and_renders_the_block(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/dirt-block/main.js", html)
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'D'", js)

    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_bundled_assets_load_from_the_pack(self):
        script = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
console.log(JSON.stringify({ paths: core.assetPathsForLevel(level) }));
"""
        out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                             capture_output=True, text=True, check=True)
        result = json.loads(out.stdout.strip().splitlines()[-1])
        by_name = {a["name"]: a["url"] for a in result["paths"]}
        self.assertEqual(by_name["dirt-block.png"],
                         "packs/dirt-block/assets/dirt-block.png")
        self.assertEqual(by_name["dirt-filled-floor.png"],
                         "packs/dirt-block/assets/dirt-filled-floor.png")


if __name__ == "__main__":
    unittest.main()
