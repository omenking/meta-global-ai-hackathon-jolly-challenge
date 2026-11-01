"""Checks for the mule bot (mech-40-mule-bot).

The mechanic lives in the pure GameCore step (packs/mule-bot);
driven here under Node against the teaching room. Rules: base
inventory 4 slots, bot carries 4 more (second HUD row), bot
follows the exact walked path one tile behind, backing into it
swaps tiles, it waits at a hazard and catches up, restart (fresh
state) restores bot and both inventories.

Run with: python -m unittest tools.test_mech_40_mule_bot -v
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

LEVEL_ID = "mech-40-mule-bot-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class MuleRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id)

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
        # Bot starts exactly one tile behind (west of) the player.
        prow = next(r for r in rows if "P" in r)
        self.assertEqual(prow.index("M"), prow.index("P") - 1)
        # At least five keys and a twin (double) lock.
        self.assertGreaterEqual(grid.count("r"), 5)
        self.assertEqual(grid.count("R"), 2)
        # One-tile pinch: the divider row has exactly one gap.
        pinch = next(r for r in rows if r.count("#") > 10 and "." in r)
        self.assertEqual(pinch.count("."), 1)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-40-mule-bot-room');
  const snap = () => {
    const bot = s.actors.find((a) => a.def === 'mule:bot');
    return { pos: { ...s.player }, bot: { x: bot.x, y: bot.y },
      inv: core.readout(s).inventory, status: s.status,
      orbs: core.readout(s).orbs_left,
      ps: s.counters['mule:player_slots'], bs: s.counters['mule:bot_slots'],
      waiting: !!s.flags['mule:waiting'] };
  };
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const eight = run([...Array(8).fill('right')]);
// Adversarial: fill 4 then back into the bot.
const adv = run([...Array(8).fill('right'), 'left']);
// Immediate back-into-bot swap from spawn.
const swap0 = run(['left']);
// Full: 14 right (7 keys), down (8th key), lefts toward 9th key.
const full = run([...Array(14).fill('right'), 'down',
  ...Array(13).fill('left')]);
// Solution: 5th key in bot slots, through pinch, twin locks, orb, portal.
const sol = run(['right','right','right','right','right','right',
  'right','right','right','right','down','down','left','left','left',
  'down','down','right','right','right','right','down','left','left',
  'left','right','right','right','right']);
const s0 = core.initialState(level, 'mech-40-mule-bot-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
const fresh = core.initialState(level, 'mech-40-mule-bot-room');
const fbot = fresh.actors.find((a) => a.def === 'mule:bot');
console.log(JSON.stringify({ eight, adv, swap0, full, sol,
  pure: JSON.stringify(s0) === before,
  fresh: { pos: { ...fresh.player }, bot: { x: fbot.x, y: fbot.y },
    inv: core.readout(fresh).inventory } }));
"""

HAZARD_SCRIPT = r"""
const core = require(process.argv[1]);
const level = { name: 'hazard-room', time_limit: 120, test: true, tile: 64,
  legend: {
    '.': { label: 'floor', sprite: 'floor_default.png' },
    '#': { label: 'wall', sprite: 'wall.png' },
    'P': { base: 'floor_default.png', label: 'player', sprite: 'jolly.png' },
    'M': { base: 'floor_default.png', label: 'mule bot', sprite: 'mule-bot.png',
      actor: 'mule:bot', terrain: 'core:floor' },
    'H': { label: 'hazard', def: 'mule:hazard' } },
  rows: ['#####', '#PM.#', '#...#', '#####'] };
let s = core.initialState(level, 'hazard-room');
// Bot's next path tile is (1,2); make it a hazard, then clear it.
s.flags['mule:path'] = [{ x: 2, y: 1 }, { x: 2, y: 2 }];
s.flags['mule:bot_idx'] = 0;
s.terrain[2][2] = 'mule:hazard';
s = core.step(s, { t_ms: 100, input: 'up' });
const bot1 = s.actors.find((a) => a.def === 'mule:bot');
const waited = { bot: { x: bot1.x, y: bot1.y },
  waiting: !!s.flags['mule:waiting'], status: s.status };
s.terrain[2][2] = 'core:floor';
s = core.step(s, { t_ms: 200, input: 'up' });
const bot2 = s.actors.find((a) => a.def === 'mule:bot');
console.log(JSON.stringify({ waited,
  caughtUp: { bot: { x: bot2.x, y: bot2.y },
    waiting: !!s.flags['mule:waiting'] } }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MuleMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)
        cls.h = run_core(HAZARD_SCRIPT)

    def test_bot_starts_one_tile_behind(self):
        self.assertEqual(self.r["fresh"]["pos"], {"x": 2, "y": 1})
        self.assertEqual(self.r["fresh"]["bot"], {"x": 1, "y": 1})
        self.assertEqual(self.r["fresh"]["inv"], [])

    def test_follows_exact_path_one_tile_behind(self):
        eight = self.r["eight"]
        self.assertEqual(eight[1]["bot"], {"x": 2, "y": 1})
        self.assertEqual(eight[8]["pos"], {"x": 10, "y": 1})
        self.assertEqual(eight[8]["bot"], {"x": 9, "y": 1})

    def test_four_plus_four_slots_and_further_key_blocked(self):
        # YAML: four plus four slots, one tile behind.
        eight = self.r["eight"]
        self.assertEqual(eight[8]["ps"], 4)
        self.assertEqual(eight[8]["bs"], 0)
        full = self.r["full"]
        last = full[-1]
        self.assertEqual(len(last["inv"]), 8)
        self.assertEqual(last["ps"], 4)
        self.assertEqual(last["bs"], 4)
        # The 9th key tile cannot be entered when full: never stranded.
        self.assertEqual(last["pos"], {"x": 4, "y": 2})
        self.assertEqual(last["status"], "playing")

    def test_adversarial_fill_then_back_into_pinch_swaps(self):
        adv = self.r["adv"]
        # Filled the 4 player slots, then backed into the bot: swap.
        self.assertEqual(adv[8]["inv"], ["red"] * 4)
        self.assertEqual(adv[9]["pos"], {"x": 9, "y": 1})
        self.assertEqual(adv[9]["bot"], {"x": 10, "y": 1})
        self.assertEqual(adv[9]["status"], "playing")

    def test_swap_from_spawn_never_blocks(self):
        swap0 = self.r["swap0"]
        self.assertEqual(swap0[1]["pos"], {"x": 1, "y": 1})
        self.assertEqual(swap0[1]["bot"], {"x": 2, "y": 1})
        self.assertEqual(swap0[1]["status"], "playing")

    def test_waits_at_hazard_then_catches_up(self):
        self.assertEqual(self.h["waited"]["bot"], {"x": 2, "y": 1})
        self.assertTrue(self.h["waited"]["waiting"])
        self.assertEqual(self.h["caughtUp"]["bot"], {"x": 2, "y": 2})
        self.assertFalse(self.h["caughtUp"]["waiting"])

    def test_solution_carries_fifth_key_and_wins(self):
        sol = self.r["sol"]
        # After the 5th key the bot slots hold it (second HUD row).
        self.assertEqual(sol[10]["bs"], 1)
        self.assertEqual(sol[-1]["status"], "won")
        self.assertEqual(sol[-1]["orbs"], 0)

    @unittest.skip("blocked-by: 11 (twin lock) - twin-lock mechanic "
                   "not built; two single red locks stand in and are "
                   "consumed in the solution test above")
    def test_carry_fifth_key_to_twin_lock(self):
        pass

    def test_restart_restores_bot_and_inventories(self):
        self.assertEqual(self.r["fresh"]["bot"], {"x": 1, "y": 1})
        self.assertEqual(self.r["fresh"]["inv"], [])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_mule_pack_and_bot_sprite(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("mule:bot", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/mule-bot/main.js", html)


if __name__ == "__main__":
    unittest.main()
