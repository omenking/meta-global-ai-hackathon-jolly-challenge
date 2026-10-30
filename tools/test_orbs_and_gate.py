"""Checks for orbs and the gate (orbs-and-gate).

The mechanics live in the pure GameCore step; driven here under
Node. Orbs ('*' tiles) never enter the inventory: each one walked
onto decrements the orbs-left counter. The gate ('G') blocks like a
wall while orbs remain and opens at zero.

Run with: python -m unittest tools.test_orbs_and_gate -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402


def run_core(script, level_name="orbs-room"):
    level = ROOT / "levels" / f"{level_name}.json"
    out = subprocess.run(["node", "-e", script, str(CORE), str(level)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class OrbsRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", "orbs-room")

    def test_orbs_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertTrue(by_id["orbs-room"]["test"])

    def test_rows_rectangular_and_legend_covers_tiles(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_gated_portal_with_orbs_placed(self):
        grid = "".join(self.level["rows"])
        self.assertIn("P", grid)
        self.assertIn("G", grid, "gate not placed")
        self.assertIn("X", grid, "portal behind the gate not placed")
        self.assertGreaterEqual(grid.count("*"), 2, "need at least 2 orbs")
        # Every orb is reachable without crossing the gate: the gate
        # row is the only divider, so no orb may sit behind it.
        gate_y = next(y for y, r in enumerate(self.level["rows"])
                      if "G" in r)
        orb_rows = [y for y, r in enumerate(self.level["rows"])
                    if "*" in r]
        self.assertTrue(all(y < gate_y for y in orb_rows),
                        "an orb behind the gate would deadlock the level")
        portal_y = next(y for y, r in enumerate(self.level["rows"])
                        if "X" in r)
        self.assertGreater(portal_y, gate_y)

    def test_orb_and_gate_sprites_exist(self):
        sprites = ROOT / "tools" / "static" / "level-sprites"
        for name in ("orb.png", "gate.png", "portal.png"):
            self.assertTrue((sprites / name).is_file(), name)


PICKUP_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
let s = core.initialState(level, 'orbs-room');
const start = { pos: { ...s.player }, orbs: core.readout(s).orbs_left,
  inv: core.readout(s).inventory };
// right x3 onto the first orb at (4,1)
for (let i = 0; i < 3; i++) s = core.step(s, { t_ms: (i + 1) * 100, input: 'right' });
const afterOne = { pos: { ...s.player }, orbs: core.readout(s).orbs_left,
  inv: core.readout(s).inventory, tile: s.grid[1][4] };
// stepping back and forth over the collected tile must not decrement again
s = core.step(s, { t_ms: 400, input: 'left' });
s = core.step(s, { t_ms: 500, input: 'right' });
const recross = { orbs: core.readout(s).orbs_left };
// right x4 onto the second orb at (8,1)
for (let i = 0; i < 4; i++) s = core.step(s, { t_ms: 600 + i * 100, input: 'right' });
const afterBoth = { pos: { ...s.player }, orbs: core.readout(s).orbs_left,
  inv: core.readout(s).inventory };
const s0 = core.initialState(level, 'orbs-room');
console.log(JSON.stringify({ start, afterOne, recross, afterBoth,
  freshOrbs: core.readout(s0).orbs_left, freshTile: s0.grid[1][4] }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class OrbPickupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(PICKUP_SCRIPT)

    def test_orbs_left_starts_at_placed_count(self):
        self.assertEqual(self.r["start"]["orbs"], 2)
        self.assertEqual(self.r["start"]["inv"], [])

    def test_walk_onto_orb_decrements_orbs_left_only(self):
        self.assertEqual(self.r["afterOne"]["pos"], {"x": 4, "y": 1})
        self.assertEqual(self.r["afterOne"]["orbs"], 1)
        self.assertEqual(self.r["afterOne"]["inv"], [],
                         "orbs must never enter the inventory")
        self.assertEqual(self.r["afterOne"]["tile"], ".")

    def test_recrossing_collected_tile_does_not_decrement(self):
        self.assertEqual(self.r["recross"]["orbs"], 1)

    def test_collecting_all_orbs_reaches_zero(self):
        self.assertEqual(self.r["afterBoth"]["pos"], {"x": 8, "y": 1})
        self.assertEqual(self.r["afterBoth"]["orbs"], 0)
        self.assertEqual(self.r["afterBoth"]["inv"], [])

    def test_step_is_pure(self):
        self.assertEqual(self.r["freshOrbs"], 2)
        self.assertEqual(self.r["freshTile"], "*")

    def test_game_renders_orbs_from_state(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("dynamicTiles", js)
        self.assertIn("ch === '*'", js)


GATE_BLOCK_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function play(inputs) {
  let s = core.initialState(level, 'orbs-room');
  inputs.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
  return s;
}
// Above the gate at (5,2) with both orbs remaining (approach along
// row 2 so no orb is crossed), press down into it.
let s = play(['down', 'right', 'right', 'right', 'right']);
const aboveGate = { ...s.player };
s = core.step(s, { t_ms: 600, input: 'down' });
const blockedFull = { pos: { ...s.player }, orbs: core.readout(s).orbs_left,
  gateTile: s.grid[3][5], steps: s.steps };
// Collect one orb, return above the gate with one orb left, press down.
let t = play(['right', 'right', 'right', 'down', 'right']);
t = core.step(t, { t_ms: 600, input: 'down' });
const blockedOne = { pos: { ...t.player }, orbs: core.readout(t).orbs_left,
  gateTile: t.grid[3][5] };
console.log(JSON.stringify({ aboveGate, blockedFull, blockedOne }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GateBlocksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(GATE_BLOCK_SCRIPT)

    def test_gate_blocks_with_all_orbs_remaining(self):
        self.assertEqual(self.r["aboveGate"], {"x": 5, "y": 2})
        self.assertEqual(self.r["blockedFull"]["pos"], {"x": 5, "y": 2})
        self.assertEqual(self.r["blockedFull"]["orbs"], 2)
        self.assertEqual(self.r["blockedFull"]["gateTile"], "G")
        self.assertEqual(self.r["blockedFull"]["steps"], 6,
                         "a blocked press still records a step")

    def test_gate_blocks_with_one_orb_remaining(self):
        self.assertEqual(self.r["blockedOne"]["pos"], {"x": 5, "y": 2})
        self.assertEqual(self.r["blockedOne"]["orbs"], 1)
        self.assertEqual(self.r["blockedOne"]["gateTile"], "G")


GATE_OPEN_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = [
  'right', 'right', 'right',           // collect orb at (4,1)
  'right', 'right', 'right', 'right',  // collect orb at (8,1)
  'left', 'left', 'left',              // back to (5,1)
  'down',                              // (5,2) above the gate
];
let s = core.initialState(level, 'orbs-room');
const startOpen = core.readout(s).gate_open;
inputs.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
const aboveOpen = { pos: { ...s.player }, orbs: core.readout(s).orbs_left,
  open: core.readout(s).gate_open };
s = core.step(s, { t_ms: 1200, input: 'down' });
const onGate = { pos: { ...s.player }, open: core.readout(s).gate_open,
  gateTile: s.grid[3][5] };
s = core.step(s, { t_ms: 1300, input: 'down' });
const pastGate = { ...s.player };
// Back through the open gate both ways before the final warp:
// warp-and-levels freezes the run once the portal is stepped on.
s = core.step(s, { t_ms: 1400, input: 'up' });
s = core.step(s, { t_ms: 1500, input: 'up' });
const backThrough = { ...s.player };
s = core.step(s, { t_ms: 1600, input: 'down' });
s = core.step(s, { t_ms: 1700, input: 'down' });
s = core.step(s, { t_ms: 1800, input: 'down' });
const atPortal = { pos: { ...s.player }, tile: s.grid[5][5],
  status: s.status };
const log = inputs.concat(
  ['down', 'down', 'up', 'up', 'down', 'down', 'down'])
  .map((input, i) => ({ t_ms: (i + 1) * 100, input }));
const replayed = core.replay(level, 'orbs-room', log).slice(-1)[0];
console.log(JSON.stringify({ startOpen, aboveOpen, onGate, pastGate,
  atPortal, backThrough, liveDigest: core.stateDigest(s),
  replayDigest: core.stateDigest(replayed),
  replayPos: replayed.player, replayOpen: core.readout(replayed).gate_open }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GateOpensTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(GATE_OPEN_SCRIPT)

    def test_gate_opens_at_zero_orbs(self):
        self.assertFalse(self.r["startOpen"])
        self.assertEqual(self.r["aboveOpen"],
                         {"pos": {"x": 5, "y": 2}, "orbs": 0, "open": True})

    def test_open_gate_is_passable_and_tile_remains(self):
        self.assertEqual(self.r["onGate"]["pos"], {"x": 5, "y": 3})
        self.assertTrue(self.r["onGate"]["open"])
        self.assertEqual(self.r["onGate"]["gateTile"], "G")
        self.assertEqual(self.r["pastGate"], {"x": 5, "y": 4})
        self.assertEqual(self.r["backThrough"], {"x": 5, "y": 2},
                         "open gate must be passable both ways")

    def test_portal_is_the_warp_since_warp_and_levels(self):
        # Superseded by warp-and-levels: stepping onto the portal
        # now wins the run (covered in tools/test_warp_and_levels.py).
        self.assertEqual(self.r["atPortal"]["pos"], {"x": 5, "y": 5})
        self.assertEqual(self.r["atPortal"]["tile"], "X")
        self.assertEqual(self.r["atPortal"]["status"], "won")

    def test_recorded_log_replays_to_same_end_state(self):
        self.assertEqual(self.r["liveDigest"], self.r["replayDigest"])
        self.assertEqual(self.r["replayPos"], {"x": 5, "y": 5})
        self.assertTrue(self.r["replayOpen"])

    def test_game_renders_open_gate_from_state(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("ch === 'G'", js)
        self.assertIn("gate_open", js)


if __name__ == "__main__":
    unittest.main()
