"""Checks for the orb bank (mech-94-orb-bank).

The mechanic lives in the pure GameCore step (packs/orb-bank);
driven here under Node against the teaching room. Rules (orbs.yml
#94): a bonus orb taken before the bank warp is banked at the
warp; the bank gate in the next chamber deducts exactly its
stated cost from the bank and never touches counted orbs; with
the bank one short the gate deducts nothing and stays shut; only
bonus orbs bank. Restart (fresh state) restores the entry bank.

Run with: python -m unittest tools.test_mech_94_orb_bank -v
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

LEVEL_ID = "mech-94-orb-bank-room"


class OrbBankRoomLevelTests(unittest.TestCase):
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
        for ch in ("P", "B", "W", "E", "K", "X"):
            self.assertIn(ch, grid)
        # Bonus orb beside the bank warp (directly below it), so the
        # direct line to the warp walks past it without collecting.
        warp = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "W"][0]
        bonus = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "B"][0]
        self.assertEqual(bonus, (warp[0], warp[1] + 1))
        # A full wall divider separates the chambers: the bank warp
        # is the only way from the first chamber to the bank gate.
        divider_y = next(y for y, r in enumerate(rows)
                         if set(r) == {"#"} and y > warp[1])
        self.assertLess(warp[1], divider_y)
        gate = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "K"][0]
        self.assertGreater(gate[1], divider_y)
        # Counted orbs on both sides prove the gate ignores them.
        self.assertGreaterEqual(grid.count("*"), 2)


CORE = ROOT / "tools" / "static" / "game-core.js"
HUD = ROOT / "tools" / "static" / "game-hud.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL),
                          str(HUD)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const hud = require(process.argv[3]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-94-orb-bank-room');
  const snap = () => ({ pos: { ...s.player },
    bank: core.readout(s).bank, pending: core.readout(s).bank_pending,
    orbs: core.readout(s).orbs_left, status: s.status,
    gate: s.grid[8][9], hudBank: hud.bankCount(s) });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const rep = (n, v) => Array(n).fill(v);
// Solution: detour down to the bonus orb, then warp, pay the gate.
const sol = run([...rep(10, 'right'), 'down', 'right', 'up',
  ...rep(7, 'right'), ...rep(3, 'down'),
  'right', 'right', 'right', 'right']);
// Adversarial: warp straight past the bonus, gate stays shut,
// long way round the south side to the exit.
const adv = run([...rep(11, 'right'),
  ...rep(7, 'right'), ...rep(3, 'down'), 'right',
  'down', 'down', 'right', 'right', 'up', 'right', 'right', 'up']);
// Bonus collected but not yet warped: pending, not banked.
const pend = run([...rep(10, 'right'), 'down', 'right']);
const s0 = core.initialState(level, 'mech-94-orb-bank-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ sol, adv, pend,
  fresh: { bank: core.readout(s0).bank, gate: s0.grid[8][9] },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class OrbBankMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_bank_then_spend(self):
        sol = self.r["sol"]
        # Bonus taken: pending until the warp banks it.
        self.assertEqual(sol[12]["pos"], {"x": 12, "y": 2})
        self.assertEqual(sol[12]["pending"], 1)
        self.assertEqual(sol[12]["bank"], 0)
        # Warp banks it and lands at the next chamber's entry with
        # the bank visible to the HUD readout.
        self.assertEqual(sol[13]["pos"], {"x": 1, "y": 5})
        self.assertEqual(sol[13]["bank"], 1)
        self.assertEqual(sol[13]["pending"], 0)
        self.assertEqual(sol[13]["hudBank"], 1)
        # Short way: the gate deducts exactly its cost (1) and opens.
        self.assertEqual(sol[23]["pos"], {"x": 8, "y": 8})
        self.assertEqual(sol[23]["bank"], 1)
        self.assertEqual(sol[24]["pos"], {"x": 9, "y": 8})
        self.assertEqual(sol[24]["bank"], 0)
        self.assertEqual(sol[24]["gate"], "k")
        self.assertEqual(sol[27]["pos"], {"x": 12, "y": 8})
        self.assertEqual(sol[27]["status"], "won")

    def test_adversarial_warp_past_the_bonus_long_way_round(self):
        adv = self.r["adv"]
        # Warping past the bonus arrives with nothing banked.
        self.assertEqual(adv[11]["pos"], {"x": 1, "y": 5})
        self.assertEqual(adv[11]["bank"], 0)
        # The shut gate blocks like a wall and deducts nothing.
        self.assertEqual(adv[22]["pos"], {"x": 8, "y": 8})
        self.assertEqual(adv[22]["bank"], 0)
        self.assertEqual(adv[22]["gate"], "K")
        self.assertEqual(adv[22]["status"], "playing")
        # The long way round reaches the exit: never stranded.
        self.assertEqual(adv[30]["pos"], {"x": 12, "y": 8})
        self.assertEqual(adv[30]["status"], "won")

    def test_boundary_exact_deduction_and_one_short(self):
        sol, adv = self.r["sol"], self.r["adv"]
        # Counted orbs in the gate's own chamber are unchanged by
        # paying: both counted orbs were collected before the gate
        # step in the solution run, and the count does not move.
        self.assertEqual(sol[23]["orbs"], sol[24]["orbs"])
        # One short (bank 0, cost 1): no deduction, gate stays shut.
        self.assertEqual(adv[21]["bank"], adv[22]["bank"])
        self.assertEqual(adv[21]["orbs"], adv[22]["orbs"])
        self.assertEqual(adv[22]["gate"], "K")

    def test_only_bonus_orbs_bank(self):
        adv, pend = self.r["adv"], self.r["pend"]
        # The adversarial run collects a counted orb on the direct
        # line yet banks nothing at the warp.
        self.assertEqual(adv[11]["orbs"], 1)
        self.assertEqual(adv[11]["bank"], 0)
        self.assertEqual(adv[11]["pending"], 0)
        # A taken bonus orb is only pending until the warp banks it.
        self.assertEqual(pend[12]["pending"], 1)
        self.assertEqual(pend[12]["bank"], 0)

    def test_restart_restores_entry_bank_and_gate(self):
        self.assertEqual(self.r["fresh"], {"bank": 0, "gate": "K"})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_bank_gate_and_hud_counter(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'K'", js)
        self.assertIn("bankCount", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/orb-bank/main.js", html)

    def test_pack_assets_are_bundled_and_present(self):
        pack = ROOT / "tools" / "static" / "packs" / "orb-bank"
        manifest = json.loads((pack / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "orb-bank")
        for entry in manifest["assets"]:
            if entry["bundled"]:
                self.assertTrue(
                    (pack / "assets" / entry["file"]).is_file(),
                    entry["file"])


if __name__ == "__main__":
    unittest.main()
