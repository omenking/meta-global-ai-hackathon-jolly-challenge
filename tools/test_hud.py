"""Checks for the in-game HUD (hud feature).

The pure HUD helpers live in tools/static/game-hud.js (UMD, like
game-core.js) and are driven here under Node: digit splitting must
pad/clamp to the 3-digit boxes, and the timer value must come from
GameCore state (time_left_s) only. Static checks pin the right-hand
column wiring in game.js and the GUI sprite derivation.

Run with: python -m unittest tools.test_hud -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUD_JS = ROOT / "tools" / "static" / "game-hud.js"
CORE_JS = ROOT / "tools" / "static" / "game-core.js"
GAME_JS = ROOT / "tools" / "static" / "game.js"


def run_hud(script):
    out = subprocess.run(["node", "-e", script, str(HUD_JS), str(CORE_JS)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


TIMER_SCRIPT = r"""
const hud = require(process.argv[1]);
const core = require(process.argv[2]);
const level = { rows: ['###', '#P#', '###'], time_limit: 120 };
const s0 = core.initialState(level, 'chip1');
const s1 = core.step(s0, { t_ms: 61000, input: 'right' });
console.log(JSON.stringify({
  d120: hud.digitsFor(120), d5: hud.digitsFor(5), d0: hud.digitsFor(0),
  dOver: hud.digitsFor(1234), dNeg: hud.digitsFor(-3),
  dFloat: hud.digitsFor(59.9),
  start: hud.timerSeconds(s0), after61: hud.timerSeconds(s1),
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class TimerDigitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_hud(TIMER_SCRIPT)

    def test_digits_pad_to_three(self):
        self.assertEqual(self.r["d5"], [0, 0, 5])
        self.assertEqual(self.r["d0"], [0, 0, 0])
        self.assertEqual(self.r["d120"], [1, 2, 0])

    def test_digits_clamp_and_floor(self):
        self.assertEqual(self.r["dOver"], [9, 9, 9])
        self.assertEqual(self.r["dNeg"], [0, 0, 0])
        self.assertEqual(self.r["dFloat"], [0, 5, 9])

    def test_timer_seconds_come_from_core_state(self):
        self.assertEqual(self.r["start"], 120)
        self.assertEqual(self.r["after61"], 59)


ORBS_SCRIPT = r"""
const hud = require(process.argv[1]);
const core = require(process.argv[2]);
const level = { rows: ['#####', '#P*.#', '#.*O#', '#####'], time_limit: 60 };
const s0 = core.initialState(level, 'chip1');
console.log(JSON.stringify({
  hud: hud.orbsLeft(s0), core: core.readout(s0).orbs_left,
  empty: hud.orbsLeft(core.initialState({ rows: ['#P#'] }, 'x')),
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class OrbsTests(unittest.TestCase):
    def test_orbs_left_matches_core_readout(self):
        r = run_hud(ORBS_SCRIPT)
        self.assertEqual(r["hud"], 3)
        self.assertEqual(r["hud"], r["core"])
        self.assertEqual(r["empty"], 0)

    def test_game_wires_orbs_readout_from_state(self):
        js = GAME_JS.read_text(encoding="utf-8")
        self.assertIn("makeReadout('orbs')", js)
        self.assertIn("GameHud.orbsLeft(state)", js)
        self.assertIn("orbsReadout.set", js)


class GuiSpriteTests(unittest.TestCase):
    def test_prep_derives_gui_sprites_from_published_gui(self):
        prep = (ROOT / "tools" / "prep_level_sprites.sh").read_text(
            encoding="utf-8")
        self.assertIn("gui-sprites", prep)
        for name in ("digit-", "label-", "backplate"):
            self.assertIn(name, prep)
        for d in "0123456789":
            src = ROOT / "assets" / "published" / "gui" / f"{d}.png"
            self.assertTrue(src.is_file(), src)
        for name in ("level_label", "time_label", "orbs_label", "backplate"):
            src = ROOT / "assets" / "published" / "gui" / f"{name}.png"
            self.assertTrue(src.is_file(), src)

    def test_game_uses_right_column_not_top_bar(self):
        js = GAME_JS.read_text(encoding="utf-8")
        self.assertIn("HUD_W", js)
        self.assertIn("gui-sprites/digit-", js)
        self.assertIn("gui-sprites/label-", js)
        self.assertIn("gui-sprites/backplate", js)
        self.assertIn("game-hud.js", (ROOT / "tools" / "static" / "game.html")
                      .read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
