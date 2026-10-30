"""Checks for keys and locks (keys-and-locks).

The mechanics live in the pure GameCore step; driven here under
Node. The 5 colours are red, gold, green, blue, silver with real
per-colour art (assets/published/lock_and_keys, no hue shifting).

Run with: python -m unittest tools.test_keys_and_locks -v
"""
import hashlib
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

COLORS = ("red", "gold", "green", "blue", "silver")


def run_core(script, level_name="keys-room"):
    level = ROOT / "levels" / f"{level_name}.json"
    out = subprocess.run(["node", "-e", script, str(CORE), str(level)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class KeysRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", "keys-room")

    def test_keys_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertTrue(by_id["keys-room"]["test"])

    def test_all_five_keys_locks_and_an_orb_placed(self):
        grid = "".join(self.level["rows"])
        key_colors = {e.get("key_color") for e in self.level["legend"].values()
                      if e.get("key_color")}
        lock_colors = {e.get("lock_color") for e in self.level["legend"].values()
                       if e.get("lock_color")}
        self.assertEqual(key_colors, set(COLORS))
        self.assertEqual(lock_colors, set(COLORS))
        for ch, entry in self.level["legend"].items():
            if entry.get("key_color") or entry.get("lock_color"):
                self.assertIn(ch, grid, f"tile {ch} not placed")
        self.assertIn("*", grid, "orb not placed")
        self.assertIn("P", grid)

    def test_real_sprites_exist_and_differ_per_colour(self):
        sprites = ROOT / "tools" / "static" / "level-sprites"
        for color in COLORS:
            for name in (f"key_{color}.png", f"wall_keyhole_{color}.png"):
                self.assertTrue((sprites / name).is_file(), name)
        hashes = {hashlib.sha256((sprites / f"key_{c}.png").read_bytes()).hexdigest()
                  for c in COLORS}
        self.assertEqual(len(hashes), 5)
        for name in ("key_red", "key_gold", "key_green", "key_blue", "key_sliver"):
            self.assertTrue((ROOT / "assets" / "published" / "lock_and_keys"
                             / f"{name}.png").is_file(), name)


PICKUP_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
let s = core.initialState(level, 'keys-room');
const start = { ...s.player };
// right, right onto the red key at (4,1)
s = core.step(s, { t_ms: 100, input: 'right' });
s = core.step(s, { t_ms: 200, input: 'right' });
s = core.step(s, { t_ms: 300, input: 'right' });
const afterRed = { pos: { ...s.player }, inv: core.readout(s).inventory,
  tile: s.grid[1][4] };
// purity: initial state untouched
const s0 = core.initialState(level, 'keys-room');
console.log(JSON.stringify({ start, afterRed,
  freshInv: core.readout(s0).inventory, freshTile: s0.grid[1][4] }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class KeyPickupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(PICKUP_SCRIPT)

    def test_walk_onto_key_fills_first_slot(self):
        self.assertEqual(self.r["afterRed"]["inv"], ["red"])
        self.assertEqual(self.r["afterRed"]["pos"], {"x": 4, "y": 1})
        self.assertEqual(self.r["afterRed"]["tile"], ".")

    def test_step_is_pure(self):
        self.assertEqual(self.r["freshInv"], [])
        self.assertEqual(self.r["freshTile"], "r")

    def test_game_renders_tiles_from_state(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("dynamicTiles", js)
        self.assertIn("state.grid", js)


FULL_SCRIPT = r"""
const core = require(process.argv[1]);
const legend = { '.': { label: 'floor' }, '#': { label: 'wall' },
  'P': { label: 'player' },
  'r': { label: 'key red', key_color: 'red' } };
const level = { rows: ['#############', '#Prrrrrrrrr.#', '#############'],
  legend, time_limit: 120 };
let s = core.initialState(level, 'full-room');
for (let i = 0; i < 9; i++) s = core.step(s, { t_ms: (i + 1) * 100, input: 'right' });
const log = Array.from({ length: 9 }, (_, i) => ({ t_ms: (i + 1) * 100, input: 'right' }));
const replayed = core.replay(level, 'full-room', log);
console.log(JSON.stringify({ pos: s.player, inv: core.readout(s).inventory,
  ninthTile: s.grid[1][10],
  replayInv: core.readout(replayed[replayed.length - 1]).inventory,
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  liveDigest: core.stateDigest(s) }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class InventoryFullTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(FULL_SCRIPT)

    def test_ninth_key_stays_on_floor(self):
        self.assertEqual(len(self.r["inv"]), 8)
        self.assertEqual(self.r["ninthTile"], "r")
        self.assertEqual(self.r["pos"], {"x": 9, "y": 1})

    def test_full_inventory_replays_identically(self):
        self.assertEqual(self.r["replayInv"], self.r["inv"])
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])


LOCK_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
let s = core.initialState(level, 'keys-room');
const seq = ['right', 'right', 'right', 'right', 'right'];
seq.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
console.log(JSON.stringify({ pos: s.player, inv: core.readout(s).inventory,
  lockTile: s.grid[1][6] }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MatchingLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(LOCK_SCRIPT)

    def test_matching_lock_consumes_key_and_dissolves(self):
        self.assertEqual(self.r["inv"], [])
        self.assertEqual(self.r["pos"], {"x": 6, "y": 1})
        self.assertEqual(self.r["lockTile"], ".")


if __name__ == "__main__":
    unittest.main()
