"""Checks for the swap tile (mech-93-swap-tile).

The mechanic lives in the pure GameCore step (packs/swap/main.js);
driven here under Node against the teaching room. Rules: a swap
tile sits under a block or bot; standing next to it and pressing
toward it exchanges the player's tile with that entity; the swap
tile stays and can be reused; restart (fresh state) restores the
placed entity.

Run with: python -m unittest tools.test_mech_93_swap_tile -v
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

LEVEL_ID = "mech-93-swap-tile-room"


class SwapRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("B"), 1)
        corridor = next(r for r in rows if "B" in r)
        # Orb behind the player, block on its swap tile ahead, and
        # the gate + warp beyond the block in a one-wide corridor.
        self.assertLess(corridor.index("*"), corridor.index("P"))
        self.assertLess(corridor.index("P"), corridor.index("B"))
        self.assertLess(corridor.index("B"), corridor.index("G"))
        self.assertLess(corridor.index("G"), corridor.index("X"))
        self.assertEqual(self.level["legend"]["B"]["def"], "swap:block")
        self.assertEqual(self.level["legend"]["B"]["terrain"], "swap:floor")


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function snapOf(s) {
  const row = s.grid[2];
  return { pos: { ...s.player }, row: row, status: s.status,
    orbs: core.readout(s).orbs_left,
    blockX: row.indexOf('B'), terrainAtPlayer:
      s.terrain[s.player.y][s.player.x] };
}
function run(seq) {
  let s = core.initialState(level, 'mech-93-swap-tile-room');
  const snaps = [snapOf(s)];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snapOf(s));
  });
  return { snaps, final: s };
}
// Solution: orb first, then swap, then through the gate to warp.
const sol = run(['left', 'right', 'right', 'right',
  'right', 'right', 'right', 'right']);
// Adversarial: swap first, gate stays shut, swap back, then orb.
const adv = run(['right', 'right', 'right', 'right', 'right',
  'left', 'left', 'left', 'left', 'left']);
// Reuse + empty-tile: swap, swap straight back, step on/off empty S.
const reuse = run(['left', 'right', 'right', 'right',
  'left', 'right', 'right', 'left']);
// Bot on a swap tile (synthetic room, same pack defs).
const botLegend = JSON.parse(JSON.stringify(level.legend));
botLegend.M = { label: 'bot on swap tile', text: 'M',
  def: 'swap:bot', terrain: 'swap:floor' };
const botLevel = { name: 'swap-bot-room', time_limit: 120, test: true,
  legend: botLegend, rows: ['#####', '#P.M#', '#####'] };
let bs = core.initialState(botLevel, 'swap-bot-room');
const bot0 = { pos: { ...bs.player }, row: bs.grid[1] };
bs = core.step(bs, { t_ms: 100, input: 'right' });
bs = core.step(bs, { t_ms: 200, input: 'right' });
const bot1 = { pos: { ...bs.player }, row: bs.grid[1] };
// A swap entity on plain floor (no swap tile in the pair) blocks.
const plainLevel = { name: 'swap-plain-room', time_limit: 120,
  test: true, legend: JSON.parse(JSON.stringify(level.legend)),
  rows: ['#####', '#P.B#', '#####'] };
delete plainLevel.legend.B.terrain;
let ps = core.initialState(plainLevel, 'swap-plain-room');
ps = core.step(ps, { t_ms: 100, input: 'right' });
ps = core.step(ps, { t_ms: 200, input: 'right' });
const plain = { pos: { ...ps.player }, row: ps.grid[1] };
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-93-swap-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, adv: adv.snaps, reuse: reuse.snaps,
  bot0: bot0, bot1: bot1, plain: plain,
  freshRow: core.initialState(level,
    'mech-93-swap-tile-room').grid[2],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SwapMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_swap_a_cornered_block_out(self):
        sol = self.r["sol"]
        self.assertEqual(sol[0]["pos"], {"x": 2, "y": 2})
        self.assertEqual(sol[0]["blockX"], 4)
        self.assertEqual(sol[1]["pos"], {"x": 1, "y": 2})
        self.assertEqual(sol[1]["orbs"], 0)
        # The swap: player takes the block's tile, block takes his.
        self.assertEqual(sol[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(sol[4]["blockX"], 3)
        self.assertEqual(sol[4]["terrainAtPlayer"], "swap:floor")
        self.assertEqual(sol[8]["status"], "won")

    def test_adversarial_swap_without_checking_both_places(self):
        adv = self.r["adv"]
        # Swapped first: block now closes the way back to the orb.
        self.assertEqual(adv[2]["pos"], {"x": 4, "y": 2})
        self.assertEqual(adv[2]["blockX"], 3)
        self.assertEqual(adv[2]["orbs"], 1)
        # The shut gate stops progress east (still at x=6).
        self.assertEqual(adv[5]["pos"], {"x": 6, "y": 2})
        self.assertEqual(adv[5]["status"], "playing")
        # Swapping again from the swap tile resolves the room.
        self.assertEqual(adv[8]["pos"], {"x": 3, "y": 2})
        self.assertEqual(adv[8]["blockX"], 4)
        self.assertEqual(adv[10]["pos"], {"x": 1, "y": 2})
        self.assertEqual(adv[10]["orbs"], 0)
        self.assertEqual(adv[10]["status"], "playing")

    def test_adjacent_only_tile_stays_reusable(self):
        reuse = self.r["reuse"]
        # First swap onto the swap tile.
        self.assertEqual(reuse[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(reuse[4]["blockX"], 3)
        # Second swap on the same tile works again (straight back).
        self.assertEqual(reuse[5]["pos"], {"x": 3, "y": 2})
        self.assertEqual(reuse[5]["blockX"], 4)
        # The swap tile stays: stepping back onto it empty is a
        # plain step (shown as S), and no entity is created.
        self.assertEqual(reuse[8]["pos"], {"x": 4, "y": 2})
        self.assertEqual(reuse[8]["row"][4], "S")
        self.assertEqual(reuse[8]["blockX"], 3)
        # A swap entity with no swap tile in the pair only blocks.
        self.assertEqual(self.r["plain"]["pos"], {"x": 2, "y": 1})
        self.assertEqual(self.r["plain"]["row"], "#P.B#")

    def test_bot_on_swap_tile_swaps_too(self):
        self.assertEqual(self.r["bot0"]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["bot1"]["pos"], {"x": 3, "y": 1})
        self.assertEqual(self.r["bot1"]["row"], "#PMS#")

    def test_restart_restores_block_on_swap_tile(self):
        self.assertEqual(self.r["freshRow"], "#*P.B..GX#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_wiring_and_assets(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("swap:block", js)
        core_js = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("packs/swap/main.js", core_js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/swap/main.js", html)
        manifest = json.loads((ROOT / "tools" / "static" / "packs" /
            "swap" / "manifest.json").read_text(encoding="utf-8"))
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["swap-tile.png", "swap-tile-occupied.png",
                          "jolly-swapping.png"])
        for entry in bundled:
            path = (ROOT / "tools" / "static" / "packs" / "swap" /
                    "assets" / entry["file"])
            self.assertTrue(path.is_file(), entry["file"])


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['left', 'right', 'right', 'right',
  'right', 'right', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-93-swap-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-93-swap-tile-room', log);
const replayed2 = core.replay(level, 'mech-93-swap-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row: replayed[replayed.length - 1].grid[2],
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
                         {"pos": {"x": 8, "y": 2}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 8)


if __name__ == "__main__":
    unittest.main()
