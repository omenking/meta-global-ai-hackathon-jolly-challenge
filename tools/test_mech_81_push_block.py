"""Checks for the push block (mech-81-push-block).

The mechanic lives in the pure GameCore step (packs/push-block);
driven here under Node against the teaching room and synthetic
mini-rooms. Rules (blocks.yml #81): pressing toward the block
moves it one tile only onto empty floor or a switch plate; it
cannot be pulled; walls, locks, closed gates, other blocks and
enemies block the push with both staying put; water, deep water,
void, fire and lava destinations block it too; on a switch plate
it holds that switch down (here the pack's switch gate) for as
long as it sits there; it occupies its tile for enemies; restart
(fresh state) restores the block and clears the held switch.

YAML test_cases coverage: "solution hold the switch" is marked
blocked-by 21 (floor switch) - the standalone floor-switch tile
does not exist on main, so that integration is an explicit skip
below; the push-block hold rule itself is exercised for real
through this pack's switch plate + switch gate. "hazards block
the push" is exercised for real on water and void; deep water,
fire and lava tiles are likewise unbuilt on main, so those three
destinations are explicit skips (the pack's fail-closed terrain
allowlist is covered generically by the water case).

Run with: python -m unittest tools.test_mech_81_push_block -v
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

LEVEL_ID = "mech-81-push-block-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "push-block"

SOLUTION = ['left', 'up', 'up', 'right',
            'down', 'down', 'down',
            'left', 'down',
            'right', 'right', 'right', 'right',
            'left', 'left', 'down', 'down',
            'right', 'right', 'right']


class PushBlockRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("B"), 1)
        self.assertEqual(grid.count("S"), 1)
        block = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "B"][0]
        player = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "P"][0]
        # The player spawns south of the block, so the naive first
        # push is north, with open floor behind the block up to the
        # north wall where it corners and cannot be pulled back.
        self.assertEqual(player, (block[0], block[1] + 1))
        self.assertEqual(rows[block[1] - 1][block[0]], ".")
        self.assertEqual(rows[0][block[0]], "#")
        # The switch is across the room, not on the naive push line.
        switch = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "S"][0]
        self.assertNotEqual(switch[1], block[1] - 1)
        self.assertIn("D", grid)
        self.assertIn("*", grid)
        self.assertIn("X", grid)


def run_core(script, *extra):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL),
                          *extra],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-81-push-block-room');
  const held = (st) => st.objects.some((row, y) => row.some((id, x) =>
    id === 'blocks:push-block' && st.terrain[y][x] === 'blocks:switch-plate'));
  const blockAt = (st) => {
    for (let y = 0; y < st.height; y++) for (let x = 0; x < st.width; x++) {
      if (st.objects[y][x] === 'blocks:push-block') return { x, y };
    }
    return null;
  };
  const snap = () => ({ pos: { ...s.player }, block: blockAt(s),
    held: held(s), status: s.status });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
// Naive: first push north, then try to push it north again and
// slide it along the north wall (the teaching moment).
const naive = run(['up', 'up', 'right', 'right', 'down']);
// No pulling: push north once, walk around, move away south.
const pull = run(['up', 'left', 'down', 'down']);
// Gate closed before the switch is held: walk south to the gate.
const gateShut = run(['right', 'down', 'down', 'down', 'right', 'down']);
// Corrected solution onto the switch and through the held gate.
const sol = run(JSON.parse(process.argv[3]));
const s0 = core.initialState(level, 'mech-81-push-block-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'up' });
console.log(JSON.stringify({
  naive: naive.snaps, pull: pull.snaps, gateShut: gateShut.snaps,
  sol: sol.snaps,
  solFinal: { pos: { ...sol.final.player },
    orbs: core.readout(sol.final).orbs_left, status: sol.final.status },
  fresh: { block: (() => { const f = core.initialState(level,
    'mech-81-push-block-room');
    for (let y = 0; y < f.height; y++) for (let x = 0; x < f.width; x++) {
      if (f.objects[y][x] === 'blocks:push-block') return { x, y };
    } return null; })(),
    row: core.initialState(level, 'mech-81-push-block-room').grid[5] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class PushBlockMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT, json.dumps(SOLUTION))

    def test_solution_pushes_block_onto_switch_and_holds_it(self):
        sol = self.r["sol"]
        # Block ends on the switch plate at (9,5) and holds it.
        self.assertEqual(sol[-4]["block"], {"x": 9, "y": 5})
        self.assertTrue(sol[-4]["held"])
        self.assertTrue(sol[-1]["held"])

    def test_walk_through_the_held_gate_to_the_warp(self):
        self.assertEqual(self.r["solFinal"],
                         {"pos": {"x": 9, "y": 7}, "orbs": 0,
                          "status": "won"})

    @unittest.skip("blocked-by: 21 (floor switch) - the standalone "
                   "floor-switch tile is not built on main; this "
                   "pack's switch plate covers the push-block hold "
                   "rule, the mech-21 integration is not faked here")
    def test_solution_hold_the_switch_floor_switch_integration(self):
        pass

    def test_adversarial_cornered_block(self):
        naive = self.r["naive"]
        # First push north moves the block to the north wall row.
        self.assertEqual(naive[1]["block"], {"x": 5, "y": 1})
        self.assertEqual(naive[1]["pos"], {"x": 5, "y": 2})
        # Second push north is blocked: block and player both stay.
        self.assertEqual(naive[2]["block"], {"x": 5, "y": 1})
        self.assertEqual(naive[2]["pos"], {"x": 5, "y": 2})
        # It can only slide along the wall; the switch (y=5) can
        # never be held from there and nobody is stranded or lost.
        self.assertFalse(naive[-1]["held"])
        self.assertEqual(naive[-1]["status"], "playing")

    def test_block_cannot_be_pulled(self):
        pull = self.r["pull"]
        self.assertEqual(pull[1]["block"], {"x": 5, "y": 1})
        # Moving away leaves the block exactly where it was pushed.
        self.assertEqual(pull[-1]["block"], {"x": 5, "y": 1})

    def test_gate_stays_shut_while_switch_unheld(self):
        shut = self.r["gateShut"]
        self.assertFalse(shut[-1]["held"])
        self.assertNotEqual(shut[-1]["pos"]["y"], 7)
        self.assertEqual(shut[-1]["status"], "playing")

    def test_restart_restores_block_and_clears_switch(self):
        self.assertEqual(self.r["fresh"]["block"], {"x": 5, "y": 2})
        self.assertEqual(self.r["fresh"]["row"], "#........S..#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])


SYNTHETIC_SCRIPT = r"""
const core = require(process.argv[1]);
const LEG = {
  '.': { label: 'floor', sprite: 'floor_default.png' },
  '#': { label: 'wall', sprite: 'wall.png' },
  'P': { base: 'floor_default.png', label: 'player', sprite: 'jolly.png' },
  '*': { base: 'floor_default.png', label: 'chip', sprite: 'orb.png' },
  'B': { base: 'floor_default.png', label: 'push block', def: 'blocks:push-block' },
  'S': { base: 'floor_default.png', label: 'switch plate', text: 'S', def: 'blocks:switch-plate' },
  'D': { label: 'switch gate', sprite: 'gate.png', def: 'blocks:switch-gate' },
  'G': { label: 'gate', sprite: 'gate.png' },
  'R': { label: 'lock red', sprite: 'wall_keyhole_red.png', lock_color: 'red' },
  '~': { base: 'floor_default.png', label: 'water', def: 'water:water' },
  'V': { base: 'floor_default.png', label: 'void', def: 'crumble:void' },
  'E': { base: 'floor_default.png', label: 'enemy', sprite: 'jolly.png', actor: 'test:enemy', terrain: 'core:floor' },
};
function mini(rows) {
  return { name: 'mini', time_limit: 120, test: true, tile: 64,
    legend: LEG, rows };
}
function trial(rows, seq) {
  const level = mini(rows);
  let s = core.initialState(level, 'mini');
  const blockAt = (st) => {
    for (let y = 0; y < st.height; y++) for (let x = 0; x < st.width; x++) {
      if (st.objects[y][x] === 'blocks:push-block') return { x, y };
    }
    return null;
  };
  const start = { pos: { ...s.player }, block: blockAt(s) };
  seq.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
  return { start, end: { pos: { ...s.player }, block: blockAt(s),
    status: s.status } };
}
const out = {
  floor: trial(['######', '#PB..#', '######'], ['right']),
  plate: trial(['######', '#PB.S#', '######'], ['right', 'right']),
  wall: trial(['#####', '#PB##', '#####'], ['right']),
  lock: trial(['######', '#PBR.#', '######'], ['right']),
  gate: trial(['######', '#PBG.#', '#.*..#', '######'], ['right']),
  switchGate: trial(['######', '#PBD.#', '######'], ['right']),
  otherBlock: trial(['######', '#PBB.#', '######'], ['right']),
  enemyBeyond: trial(['######', '#PBE.#', '######'], ['right']),
  water: trial(['######', '#PB~.#', '######'], ['right']),
  voidDest: trial(['######', '#PBV.#', '######'], ['right']),
};
// The block occupies its tile for a non-player actor: the tile's
// blocks predicate must refuse any actor that is not the player.
const lvl = mini(['######', '#PB..#', '######']);
const st = core.initialState(lvl, 'mini');
const def = core.getTileDef('blocks:push-block');
const enemyActor = st.actors.find((a) => a.id !== 'player')
  || { id: 'enemy-0', x: 1, y: 1 };
out.enemyOccupies = def.blocks(
  JSON.parse(JSON.stringify(st)),
  { x: 2, y: 1, def, meta: {} }, enemyActor);
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class BlockedPushTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(
            ["node", "-e", SYNTHETIC_SCRIPT, str(CORE), str(LEVEL)],
            capture_output=True, text=True, check=True)
        cls.r = json.loads(out.stdout.strip().splitlines()[-1])

    def test_push_onto_empty_floor_moves_one_tile(self):
        t = self.r["floor"]
        self.assertEqual(t["end"]["block"], {"x": 3, "y": 1})
        self.assertEqual(t["end"]["pos"], {"x": 2, "y": 1})

    def test_push_onto_switch_plate_moves(self):
        t = self.r["plate"]
        self.assertEqual(t["end"]["block"], {"x": 4, "y": 1})
        self.assertEqual(t["end"]["pos"], {"x": 3, "y": 1})

    def test_blocked_push_stays_put(self):
        # Wall, lock, closed gate, closed switch gate, another
        # block and an enemy beyond: block and player both stay.
        for name in ("wall", "lock", "gate", "switchGate",
                     "otherBlock", "enemyBeyond"):
            t = self.r[name]
            self.assertEqual(t["end"], t["start"] | {"status": "playing"},
                             name)
            self.assertEqual(t["end"]["block"], {"x": 2, "y": 1}, name)
            self.assertEqual(t["end"]["pos"], {"x": 1, "y": 1}, name)

    def test_hazards_block_the_push(self):
        for name in ("water", "voidDest"):
            t = self.r[name]
            self.assertEqual(t["end"]["block"], {"x": 2, "y": 1}, name)
            self.assertEqual(t["end"]["pos"], {"x": 1, "y": 1}, name)

    @unittest.skip("blocked-by: 41/43/44 (deep water, fire, lava) - "
                   "those hazard tiles are not built on main; the "
                   "fail-closed terrain allowlist that blocks them "
                   "is covered for real by the water case above")
    def test_deep_water_fire_lava_destinations(self):
        pass

    def test_block_occupies_its_tile_for_enemies(self):
        self.assertTrue(self.r["enemyOccupies"])


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = JSON.parse(process.argv[3]);
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-81-push-block-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-81-push-block-room', log);
const replayed2 = core.replay(level, 'mech-81-push-block-room',
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
                         {"pos": {"x": 9, "y": 7}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], len(SOLUTION))


class PackWiringTests(unittest.TestCase):
    def test_manifest_lists_bundled_assets_that_exist(self):
        manifest = json.loads((PACK / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "push-block")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["push-block.png", "push-block-on-switch.png"])
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
        self.assertIn("packs/push-block/main.js", html)
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'B'", js)
        self.assertIn("push-block-on-switch.png", js)

    def test_block_sprite_is_raised_above_the_destination_floor(self):
        # Regression (qa-verification): board sprites are added in
        # row-major order, so a destination floor drawn after the
        # block's origin covers the block after an east/south push;
        # the block looked picked up. The 'B' render branch must
        # bring its sprite to the front of its parent.
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        branch = js.split("dt.ch === 'B'", 1)[1].split("dt.ch === 'D'", 1)[0]
        self.assertIn("setChildIndex", branch)

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
        self.assertEqual(by_name["push-block.png"],
                         "packs/push-block/assets/push-block.png")
        self.assertEqual(by_name["push-block-on-switch.png"],
                         "packs/push-block/assets/push-block-on-switch.png")


if __name__ == "__main__":
    unittest.main()
