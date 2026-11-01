"""Checks for the pack folder design (review-fixes-1).

A pack is a folder: main.js (the code) plus manifest.json (the
assets it uses, grouped by kind). Bundled assets live in the pack's
assets/ and load from packs/<id>/assets/<file>; shared assets load
from level-sprites/. Placeholder art is 512x512 RGBA, like every
level sprite.

Run with: python -m unittest tools.test_pack_folders -v
"""
import json
import shutil
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "tools" / "static" / "packs"
CORE = ROOT / "tools" / "static" / "game-core.js"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


class PackFolderTests(unittest.TestCase):
    def test_every_pack_is_a_folder_with_main_and_manifest(self):
        pack_dirs = sorted(p for p in PACKS.iterdir() if p.is_dir())
        self.assertGreaterEqual(len(pack_dirs), 4)
        for pack_dir in pack_dirs:
            self.assertTrue((pack_dir / "main.js").is_file(), pack_dir.name)
            manifest_path = pack_dir / "manifest.json"
            self.assertTrue(manifest_path.is_file(), pack_dir.name)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["pack"], pack_dir.name)
            self.assertEqual(manifest["main"], "main.js")

    def test_bundled_assets_exist_and_are_512_rgba_placeholders(self):
        crumbling = PACKS / "crumbling"
        manifest = json.loads(
            (crumbling / "manifest.json").read_text(encoding="utf-8"))
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["crumbling.png", "crumbling-minor.png",
                          "crumbling-major.png", "void.png"])
        for entry in bundled:
            path = crumbling / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])

    def test_no_single_file_packs_remain(self):
        loose = [p.name for p in PACKS.glob("*.js")]
        self.assertEqual(loose, [], f"single-file packs remain: {loose}")


@unittest.skipUnless(shutil.which("node"), "node not available")
class PackAssetPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        level = ROOT / "levels" / "mech-5-crumbling-tile-room.json"
        script = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
console.log(JSON.stringify({
  names: core.assetsForLevel(level),
  paths: core.assetPathsForLevel(level),
}));
"""
        out = subprocess.run(["node", "-e", script, str(CORE), str(level)],
                             capture_output=True, text=True, check=True)
        cls.result = json.loads(out.stdout.strip().splitlines()[-1])
        cls.by_name = {a["name"]: a["url"] for a in cls.result["paths"]}

    def test_bundled_assets_load_from_their_pack(self):
        for name in ("crumbling.png", "crumbling-minor.png",
                     "crumbling-major.png", "void.png"):
            self.assertIn(name, self.result["names"])
            self.assertEqual(self.by_name[name],
                             f"packs/crumbling/assets/{name}")

    def test_shared_assets_load_from_level_sprites(self):
        self.assertEqual(self.by_name["floor_default.png"],
                         "level-sprites/floor_default.png")
        self.assertEqual(self.by_name["key.png"], "level-sprites/key.png")


if __name__ == "__main__":
    unittest.main()
