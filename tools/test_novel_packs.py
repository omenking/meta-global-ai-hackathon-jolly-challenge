"""Novel-mechanics packs built on the kernel registry.

Each pack is proven in Node against its own Test Level: the mechanic
must work through the public GameCore API with no kernel edits beyond
generic hooks. Run: python -m unittest tools.test_novel_packs -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"


def run_node(script, level_name):
    out = subprocess.run(
        ["node", "-e", script, str(CORE), str(ROOT / "levels" / level_name)],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BUTTONS_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function play(inputs) {
  let s = core.initialState(level, 'trap-room');
  inputs.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
  return s;
}
const R = (n) => Array(n).fill('right');
// Closed: the corridor forces one button press (opens), so press it
// a second time to toggle shut, then try to drop through the trap.
const closed = play([...R(3), 'left', ...R(5), 'down']);
const closedPos = { ...closed.player };
// Open: press the button (4th step lands on it), then drop through.
const opened = play([...R(7), 'down', 'down', 'right', 'right', 'right']);
console.log(JSON.stringify({
  closedPos: closedPos,
  openedPos: { ...opened.player },
  openedStatus: opened.status,
  orbs: core.readout(opened).orbs_left,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class ButtonsTrapsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_node(BUTTONS_SCRIPT, "trap-room.json")

    def test_trap_blocks_while_closed(self):
        self.assertEqual(self.r["closedPos"], {"x": 8, "y": 1})

    def test_button_opens_trap_to_orb_and_warp(self):
        self.assertEqual(self.r["openedPos"], {"x": 11, "y": 3})
        self.assertEqual(self.r["openedStatus"], "won")
        self.assertEqual(self.r["orbs"], 0)


if __name__ == "__main__":
    unittest.main()
