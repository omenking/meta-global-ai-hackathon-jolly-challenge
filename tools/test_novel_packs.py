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


ICE_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function play(inputs) {
  let s = core.initialState(level, 'ice-room');
  inputs.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
  return s;
}
// Three rights: the third steps on ice and slides to the first floor.
const slid = play(['right', 'right', 'right']);
// Force lane: down then three rights steps onto force, conveyed east.
const conveyed = play(['down', 'right', 'right', 'right']);
const won = play(['right', 'right', 'right', 'right', 'right', 'right', 'right', 'right']);
console.log(JSON.stringify({
  slid: { ...slid.player }, conveyed: { ...conveyed.player },
  wonPos: { ...won.player }, wonStatus: won.status,
}));
"""


MONSTER_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function play(inputs) {
  let s = core.initialState(level, 'monster-room');
  inputs.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
  return s;
}
function monster(s) { const a = s.actors.find((a) => a.id !== 'player'); return { x: a.x, y: a.y }; }
// Patrol: bump the top wall; the monster advances one tile per step.
const after3 = play(['up', 'up', 'up']);
// Contact: wait in place until the patrol reaches the player.
const contact = play(Array(25).fill('up'));
// Detour: along the lower row, up to the orb, right onto the warp.
const detour = play(['down', ...Array(9).fill('right'), 'up', 'right']);
console.log(JSON.stringify({
  start: monster(core.initialState(level, 'monster-room')),
  after3: monster(after3), contactStatus: contact.status,
  detourStatus: detour.status, detourOrbs: core.readout(detour).orbs_left,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MonstersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_node(MONSTER_SCRIPT, "monster-room.json")

    def test_monster_patrols_one_tile_per_step(self):
        self.assertEqual(self.r["start"], {"x": 6, "y": 1})
        self.assertEqual(self.r["after3"], {"x": 9, "y": 1})

    def test_contact_loses(self):
        self.assertEqual(self.r["contactStatus"], "lost")

    def test_detour_reaches_warp(self):
        self.assertEqual(self.r["detourStatus"], "won")
        self.assertEqual(self.r["detourOrbs"], 0)


@unittest.skipUnless(shutil.which("node"), "node not available")
class IceForceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_node(ICE_SCRIPT, "ice-room.json")

    def test_ice_slides_along_entry_direction(self):
        self.assertEqual(self.r["slid"], {"x": 7, "y": 1})

    def test_force_floor_conveys_east(self):
        self.assertEqual(self.r["conveyed"], {"x": 8, "y": 2})

    def test_slide_run_reaches_warp(self):
        self.assertEqual(self.r["wonStatus"], "won")


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
