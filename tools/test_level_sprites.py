"""Focused checks for level-preview sprite preparation.

Verifies that tools/prep_level_sprites.sh derived keyed RGBA sprites from
assets/published, staged the level JSON next to the preview page, and that
every sprite id referenced by levels/chip1.json resolves to a file.

Run with: python -m unittest tools.test_level_sprites -v
(or: python tools/test_level_sprites.py)
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVEL_SRC = ROOT / "levels" / "chip1.json"
LEVEL_STAGED = ROOT / "tools" / "static" / "levels" / "chip1.json"
SPRITES_DIR = ROOT / "tools" / "static" / "level-sprites"

KEYED_SPRITES = ("jolly.png", "key.png", "orb.png", "gate.png")
FULLBLEED_SPRITES = ("floor_default.png", "wall.png", "portal.png",
                     "wall_keyhole.png")


def _ffprobe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,pix_fmt",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    width, height, pix_fmt = out.stdout.strip().split(",")
    return int(width), int(height), pix_fmt


def _pixel(path, x, y):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", f"crop=1:1:{x}:{y},format=rgba",
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
        capture_output=True, check=True)
    return tuple(out.stdout[:4])


def _referenced_sprites(level):
    names = set()
    for entry in level["legend"].values():
        for key in ("base", "sprite"):
            if entry.get(key):
                names.add(entry[key])
    return names


class LevelSpriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(LEVEL_SRC, encoding="utf-8") as fh:
            cls.level = json.load(fh)

    def test_level_grid_shape(self):
        rows = self.level["rows"]
        self.assertEqual(len(rows), 16, "level must have 16 rows")
        for row in rows:
            self.assertEqual(len(row), 17, f"row {row!r} must have 17 cells")
            for cell in row:
                self.assertIn(cell, self.level["legend"],
                              f"cell {cell!r} missing from legend")

    def test_staged_level_matches_source(self):
        self.assertTrue(LEVEL_STAGED.is_file(),
                        "prep script must stage levels/chip1.json for serving")
        self.assertEqual(LEVEL_STAGED.read_bytes(), LEVEL_SRC.read_bytes(),
                         "staged level JSON must equal the source")

    def test_referenced_sprites_are_rgba_512(self):
        for name in sorted(_referenced_sprites(self.level)):
            path = SPRITES_DIR / name
            self.assertTrue(path.is_file(), f"missing derived sprite {name}")
            width, height, pix_fmt = _ffprobe(path)
            self.assertEqual((width, height, pix_fmt), (512, 512, "rgba"),
                             f"{name} must be 512x512 RGBA")

    def test_keyed_sprites_have_transparency(self):
        for name in KEYED_SPRITES:
            path = SPRITES_DIR / name
            self.assertTrue(path.is_file(), f"missing derived sprite {name}")
            self.assertEqual(_pixel(path, 5, 5)[3], 0,
                             f"{name} corner must be transparent")
            self.assertEqual(_pixel(path, 256, 256)[3], 255,
                             f"{name} center must be opaque")

    def test_fullbleed_sprites_are_opaque(self):
        for name in FULLBLEED_SPRITES:
            path = SPRITES_DIR / name
            self.assertTrue(path.is_file(), f"missing derived sprite {name}")
            self.assertEqual(_pixel(path, 5, 5)[3], 255,
                             f"{name} must stay fully opaque")

    def test_color_variants_are_distinct(self):
        key_hashes = set()
        for color in ("red", "blue", "green", "yellow"):
            data = (SPRITES_DIR / f"key_{color}.png").read_bytes()
            key_hashes.add(hashlib.sha256(data).hexdigest())
        self.assertEqual(len(key_hashes), 4,
                         "key color variants must all differ")
        lock_hashes = set()
        for color in ("red", "blue", "green", "yellow"):
            data = (SPRITES_DIR / f"wall_keyhole_{color}.png").read_bytes()
            lock_hashes.add(hashlib.sha256(data).hexdigest())
        self.assertEqual(len(lock_hashes), 4,
                         "lock color variants must all differ")


if __name__ == "__main__":
    unittest.main()
