"""Checks for keyboard input scaffold (game-shell/keyboard-input).

Run with: python -m unittest tools.test_game_input -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"

SCRIPT = r"""
const core = require(process.argv[1]);
const keys = ['w','a','s','d','W','ArrowUp','ArrowLeft','ArrowDown',
              'ArrowRight','x','Enter',''];
console.log(JSON.stringify(keys.map((k) => [k, core.inputForKey(k)])));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class KeyboardInputTests(unittest.TestCase):
    def test_wasd_and_arrows_map_to_directions(self):
        out = subprocess.run(["node", "-e", SCRIPT, str(CORE)],
                             capture_output=True, text=True, check=True)
        mapping = dict(json.loads(out.stdout.strip().splitlines()[-1]))
        self.assertEqual(mapping, {
            "w": "up", "a": "left", "s": "down", "d": "right",
            "W": "up", "ArrowUp": "up", "ArrowLeft": "left",
            "ArrowDown": "down", "ArrowRight": "right",
            "x": None, "Enter": None, "": None,
        })

    def test_game_page_registers_input_in_debug_readout(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn('id="dbg-input"', html)
        self.assertIn("addEventListener('keydown'", js)
        self.assertIn("GameCore.inputForKey(ev.key)", js)
        self.assertIn("dbg-input", js)


if __name__ == "__main__":
    unittest.main()
