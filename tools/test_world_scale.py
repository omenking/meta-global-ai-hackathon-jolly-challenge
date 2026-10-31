"""Checks for fixed world scale (fixed-world-scale feature).

The pure scale math lives in tools/static/engine/world-scale.js (UMD,
like camera.js) and is driven here under Node: one renderer-owned tile
size for every level size, a uniform (square) board transform, and a
camera that moves the board without ever rescaling it.

Run with: python -m unittest tools.test_world_scale -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCALE_JS = ROOT / "tools" / "static" / "engine" / "world-scale.js"
GAME_JS = ROOT / "tools" / "static" / "game.js"
GAME_HTML = ROOT / "tools" / "static" / "game.html"

SCRIPT = r"""
const ws = require(process.argv[1]);
const cam = require(process.argv[2]);
const sizes = [[7,6],[11,7],[17,16],[32,24],[64,64]];
const out = { tile: ws.WORLD_TILE_PX, levels: [], framed: [] };
for (const [cols, rows] of sizes) {
  const view = { w: Math.min(cols, 17), h: Math.min(rows, 16) };
  const atRest = ws.boardTransform({ availW: 1280, availH: 800,
    viewW: view.w, viewH: view.h, camX: 0, camY: 0 });
  const scrolled = ws.boardTransform({ availW: 1280, availH: 800,
    viewW: view.w, viewH: view.h, camX: 5, camY: 3 });
  out.levels.push({ cols, rows, rest: atRest, scrolled });
}
// Player must be fully on screen for every position in a 32x24 level,
// at any window size, when the camera frames the visible view.
for (const [availW, availH] of [[1096,800],[900,600],[700,500],[1400,1000]]) {
  const view = ws.visibleView({ availW, availH, cols: 32, rows: 24, maxW: 17, maxH: 16 });
  let worst = null;
  for (let y = 0; y < 24 && !worst; y++) for (let x = 0; x < 32; x++) {
    const c = cam.compute({ cols: 32, rows: 24, viewW: view.w, viewH: view.h, player: { x, y } });
    const t = ws.boardTransform({ availW, availH, viewW: view.w, viewH: view.h, camX: c.x, camY: c.y });
    const px = t.x + x * t.tilePx, py = t.y + y * t.tilePx;
    if (px < 0 || py < 0 || px + t.tilePx > availW || py + t.tilePx > availH) {
      worst = { x, y, px, py }; break;
    }
  }
  out.framed.push({ availW, availH, view, worst });
}
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class WorldScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", "-e", SCRIPT, str(SCALE_JS),
                              str(ROOT / "tools/static/engine/camera.js")],
                             capture_output=True, text=True, check=True)
        cls.data = json.loads(out.stdout.strip().splitlines()[-1])

    def test_one_tile_size_for_every_level(self):
        # movement-room's native tile: 64px, whatever the level size.
        self.assertEqual(self.data["tile"], 64)
        for lvl in self.data["levels"]:
            self.assertEqual(lvl["rest"]["tilePx"], 64, lvl)
            self.assertEqual(lvl["scrolled"]["tilePx"], 64, lvl)

    def test_transform_is_uniform_and_camera_never_rescales(self):
        for lvl in self.data["levels"]:
            for t in (lvl["rest"], lvl["scrolled"]):
                self.assertEqual(t["scaleX"], t["scaleY"], lvl)
            self.assertEqual(lvl["rest"]["scaleX"], lvl["scrolled"]["scaleX"])
            # Scrolling only translates the board, by whole tiles.
            self.assertEqual(lvl["rest"]["x"] - lvl["scrolled"]["x"], 5 * 64)
            self.assertEqual(lvl["rest"]["y"] - lvl["scrolled"]["y"], 3 * 64)

    def test_player_always_fully_in_frame(self):
        for framed in self.data["framed"]:
            self.assertIsNone(framed["worst"], framed)
            # Visible view never exceeds what fits at 64px, nor MAX view.
            self.assertLessEqual(framed["view"]["w"] * 64, framed["availW"])
            self.assertLessEqual(framed["view"]["h"] * 64, framed["availH"])
            self.assertLessEqual(framed["view"]["w"], 17)
            self.assertLessEqual(framed["view"]["h"], 16)

    def test_small_levels_letterbox_not_zoom(self):
        small = self.data["levels"][0]  # 7x6 movement-room
        large = self.data["levels"][3]  # 32x24 scroll-room
        self.assertEqual(small["rest"]["scaleX"], large["rest"]["scaleX"])
        self.assertGreater(small["rest"]["x"], 0)
        self.assertGreater(small["rest"]["y"], 0)


class WorldScaleWiringTests(unittest.TestCase):
    def test_game_uses_world_scale_and_loads_it(self):
        game = GAME_JS.read_text()
        self.assertIn("GameWorldScale", game)
        self.assertIn("engine/world-scale.js", GAME_HTML.read_text())
        # The old per-level fit-to-viewport must not come back.
        self.assertNotIn("availW / (VIEW.w * TILE)", game)
        self.assertNotIn("availH / (VIEW.h * TILE)", game)


if __name__ == "__main__":
    unittest.main()
