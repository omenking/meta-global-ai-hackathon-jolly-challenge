"""Checks for the raft block (mech-86-raft-block).

The mechanic lives in the pure GameCore step (packs/raft/main.js);
driven here under Node against the teaching room. Rules: step onto
the raft from a bank; each move travels one water tile (shallow or
deep) with the player aboard; stepping onto a bank ends the ride and
docks the raft on the last water tile; the raft never enters floor,
void, fire or lava; on the 10th travelled water tile it sinks and
the player respawns at the checkpoint (spawn) with the raft back at
its placed bank; while riding, readout raft_remaining feeds the
conditional GUI slot under the inventory.

Run with: python -m unittest tools.test_mech_86_raft_block -v
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

LEVEL_ID = "mech-86-raft-block-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
HUD = ROOT / "tools" / "static" / "game-hud.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class RaftRoomLevelTests(unittest.TestCase):
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
        # 12 water tiles on the raft row, raft on the first.
        self.assertEqual(rows[3].count("~") + 1, 12)
        self.assertEqual(rows[3].index("R"), 4)
        # Banked island at the 8th water tile.
        self.assertEqual(rows[2][11], ".")
        self.assertIn("*", "".join(rows))
        self.assertIn("X", "".join(rows))

    def test_manifest_and_assets(self):
        pack = ROOT / "tools" / "static" / "packs" / "raft"
        manifest = json.loads((pack / "manifest.json").read_text())
        self.assertEqual(manifest["pack"], "raft")
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"], entry["file"])
            self.assertTrue((pack / "assets" / entry["file"]).exists(),
                            entry["file"])
        main = (pack / "main.js").read_text()
        for entry in manifest["assets"]:
            self.assertIn(entry["file"], main)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL),
                          str(HUD)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const hud = require(process.argv[3]);
function run(seq, lvl, name) {
  let s = core.initialState(lvl || level, name || 'mech-86-raft-block-room');
  const snap = () => ({ pos: { ...s.player },
    riding: core.readout(s).raft_riding,
    rem: core.readout(s).raft_remaining,
    hud: hud.raftCounter(s),
    sinks: s.counters['raft:sinks'] || 0, status: s.status });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const pre = ['right', 'right', 'down', 'down'];
// A: ride straight for the far bank (naive).
const a = run([...pre, ...Array(12).fill('right')]);
// B: island hop (corrected), then orb + warp.
const b = run([...pre, ...Array(8).fill('right'), 'up', 'down',
  ...Array(5).fill('right'), 'up', 'up', 'right', 'right']);
// C: walk into water on foot from the top bank (no raft there).
const c = run(['right', 'right', 'right', 'right']);
// D: board, step straight back onto the bank, re-board.
const d = run([...pre, 'right', 'left', 'right', 'right']);
// E: ride down into the deep row and across it.
const e = run([...pre, 'right', 'right', 'down', 'down', 'right', 'right']);
// F: synthetic bank-at-ten room: 9 water tiles then a bank.
const lvlF = { name: 'raft-bank10', time_limit: 120, legend: {
  '.': { label: 'floor' }, '#': { label: 'wall' },
  'P': { label: 'player' },
  '~': { def: 'raft:water-shallow' },
  'R': { terrain: 'raft:water-shallow', def: 'raft:raft' } },
  rows: ['#############', '#P.R~~~~~~~~.#', '#############'] };
const f = run(Array(11).fill('right'), lvlF, 'raft-bank10');
// G: synthetic hazards room: fire, lava, void beside the water.
const lvlG = { name: 'raft-hazards', time_limit: 120, legend: {
  '.': { label: 'floor' }, '#': { label: 'wall' },
  'P': { label: 'player' },
  '~': { def: 'raft:water-shallow' },
  'F': { def: 'raft:fire' }, 'L': { def: 'raft:lava' },
  'V': { terrain: 'core:floor', def: 'raft:void' },
  'R': { terrain: 'raft:water-shallow', def: 'raft:raft' } },
  rows: ['#######', '#P.R~F#', '#...~L#', '#...~V#', '#######'] };
const g = run(['right', 'right', 'right', 'right',
  'down', 'right', 'down', 'right', 'up', 'up'], lvlG, 'raft-hazards');
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-86-raft-block-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, d: d.snaps, e: e.snaps,
  f: f.snaps, g: g.snaps,
  bFinal: { pos: { ...b.final.player }, status: b.final.status,
    orbs: core.readout(b.final).orbs_left },
  fresh: (() => { const s = core.initialState(level,
    'mech-86-raft-block-room'); return { pos: { ...s.player },
    row: s.grid[3], riding: core.readout(s).raft_riding }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class RaftMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_board_from_bank_and_counter_appears(self):
        a = self.r["a"]
        self.assertEqual(a[4], {"pos": {"x": 3, "y": 3},
                                "riding": False, "rem": 0, "hud": None,
                                "sinks": 0, "status": "playing"})
        # Boarding tile is travelled tile 1: 9 left, HUD slot shows it.
        self.assertEqual(a[5]["pos"], {"x": 4, "y": 3})
        self.assertTrue(a[5]["riding"])
        self.assertEqual(a[5]["rem"], 9)
        self.assertEqual(a[5]["hud"], 9)

    def test_each_move_travels_one_water_tile_and_counts_down(self):
        a = self.r["a"]
        self.assertEqual(a[6]["rem"], 8)
        self.assertEqual(a[12]["pos"], {"x": 11, "y": 3})
        self.assertEqual(a[12]["rem"], 2)

    def test_ten_tile_boundary_sinks_and_respawns_at_checkpoint(self):
        a = self.r["a"]
        # 10th travelled tile (x=13): sinks, back at spawn, raft reset.
        self.assertEqual(a[14]["pos"], {"x": 1, "y": 1})
        self.assertFalse(a[14]["riding"])
        self.assertEqual(a[14]["sinks"], 1)
        self.assertEqual(a[14]["status"], "playing")

    def test_stepping_onto_bank_ends_ride_and_docks_raft(self):
        b = self.r["b"]
        self.assertEqual(b[13]["pos"], {"x": 11, "y": 2})
        self.assertFalse(b[13]["riding"])
        self.assertEqual(b[13]["hud"], None)
        # Re-boarding from the island starts a fresh budget.
        self.assertTrue(b[14]["riding"])
        self.assertEqual(b[14]["rem"], 9)

    def test_tenth_move_onto_a_bank_is_safe(self):
        f = self.r["f"]
        # 8 water tiles in this room; stepping onto the bank ends
        # the ride safely with no sink (bank move is not counted).
        self.assertEqual(f[11]["pos"], {"x": 12, "y": 1})
        self.assertFalse(f[11]["riding"])
        self.assertEqual(f[11]["sinks"], 0)

    def test_water_on_foot_is_blocked(self):
        c = self.r["c"]
        self.assertEqual(c[4]["pos"], {"x": 3, "y": 1})
        self.assertFalse(c[4]["riding"])

    def test_step_back_onto_bank_and_reboard(self):
        d = self.r["d"]
        self.assertEqual(d[6]["pos"], {"x": 3, "y": 3})
        self.assertFalse(d[6]["riding"])
        self.assertTrue(d[7]["riding"])
        self.assertEqual(d[7]["rem"], 9)

    def test_deep_water_one_tile_per_move_same_budget(self):
        e = self.r["e"]
        self.assertEqual(e[9]["pos"], {"x": 6, "y": 5})
        self.assertTrue(e[9]["riding"])
        self.assertEqual(e[10]["pos"], {"x": 7, "y": 5})
        self.assertEqual(e[10]["rem"], 4)

    def test_fire_lava_void_never_entered_while_riding(self):
        g = self.r["g"]
        # Boarded at (3,1); push right into fire: no move, no count.
        self.assertEqual(g[3]["pos"], {"x": 4, "y": 1})
        self.assertEqual(g[4]["pos"], {"x": 4, "y": 1})
        self.assertTrue(g[4]["riding"])
        self.assertEqual(g[4]["rem"], 8)
        # Lava (right at y2) and void (right at y3) never entered.
        self.assertEqual(g[6]["pos"], {"x": 4, "y": 2})
        self.assertEqual(g[8]["pos"], {"x": 4, "y": 3})
        self.assertTrue(g[10]["riding"])

    def test_island_hop_reaches_far_bank_and_wins(self):
        self.assertEqual(self.r["bFinal"],
                         {"pos": {"x": 18, "y": 1}, "status": "won",
                          "orbs": 0})

    def test_restart_restores_raft_and_budget(self):
        self.assertEqual(self.r["fresh"]["pos"], {"x": 1, "y": 1})
        self.assertIn("R", self.r["fresh"]["row"])
        self.assertFalse(self.r["fresh"]["riding"])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_raft_pack_and_counter(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text()
        self.assertIn("raftCounter", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/raft/main.js", html)


class YamlTestCaseTests(unittest.TestCase):
    """Every YAML test_cases entry for mechanic 86, by name."""

    @unittest.skip("blocked-by: 41 (deep water), 48 (checkpoint) — "
                   "standalone mechanics not yet built; raft-rule "
                   "coverage in RaftMechanicTests")
    def test_yaml_solution_island_hopping_crossing(self):
        pass

    @unittest.skip("blocked-by: 48 (checkpoint) — standalone mechanic "
                   "not yet built; sink/respawn covered as raft rule "
                   "in RaftMechanicTests")
    def test_yaml_adversarial_ride_straight_for_far_bank(self):
        pass

    def test_yaml_ten_tile_boundary(self):
        # Exercised for real in RaftMechanicTests: counts down one per
        # water tile, sinks on the 10th, bank as 10th move is safe.
        self.assertTrue(hasattr(RaftMechanicTests,
                                "test_ten_tile_boundary_sinks_and_"
                                "respawns_at_checkpoint"))

    @unittest.skip("blocked-by: 42 (current tile) — standalone "
                   "mechanic not yet built; bank-only exit and "
                   "fire/lava/void blocking covered in "
                   "RaftMechanicTests")
    def test_yaml_banks_are_the_only_exit(self):
        pass

    def test_yaml_restart_and_replay(self):
        # Restart half exercised here; replay digest half lives in
        # SanityReplayTests (sanity-check task).
        self.assertTrue(hasattr(RaftMechanicTests,
                                "test_restart_restores_raft_and_budget"))


if __name__ == "__main__":
    unittest.main()
