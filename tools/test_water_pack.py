"""Water pack (kept pack): water kills without flippers, safe with.

Drives the real GameCore under Node on levels/water-room.json, and
checks the pack carries its own assets (glyphs on defs, declared
sprite/icon names for preload). Run: python -m unittest
tools.test_water_pack -v
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
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function play(inputs) {
  let s = core.initialState(level, 'water-room');
  inputs.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
  return s;
}
const dry = play(['down', 'right', 'right', 'right', 'right', 'right']);
const wet = play(['right', 'right', 'right', 'right', 'right', 'right', 'right', 'right']);
const waterDef = core.getTileDef('water:water');
const flipDef = core.getTileDef('water:flipper');
console.log(JSON.stringify({
  dryStatus: dry.status, wetStatus: wet.status,
  inv: core.readout(wet).inventory,
  glyphs: [waterDef && waterDef.glyph, flipDef && flipDef.glyph],
  assets: core.assetsForLevel(level),
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class WaterPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(
            ["node", "-e", SCRIPT, str(CORE), str(ROOT / "levels" / "water-room.json")],
            capture_output=True, text=True, check=True)
        cls.r = json.loads(out.stdout.strip().splitlines()[-1])

    def test_water_kills_without_flippers(self):
        self.assertEqual(self.r["dryStatus"], "lost")

    def test_flippers_cross_collect_and_warp(self):
        self.assertEqual(self.r["wetStatus"], "won")
        self.assertEqual(self.r["inv"], ["flipper"])

    def test_pack_carries_its_assets(self):
        self.assertEqual(self.r["glyphs"], ["~", "F"])
        self.assertIn("key.png", self.r["assets"])
        self.assertIn("orb.png", self.r["assets"])


if __name__ == "__main__":
    unittest.main()
