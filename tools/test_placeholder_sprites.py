"""Checks for the placeholder sprite maker (tools/make_placeholder_sprites.sh).

Placeholders stand in for pack assets listed in a candidate mechanic
file before real art exists: right size (512x512 RGBA, like every
level sprite), correct name, distinct per name, and never overwriting
an existing file unless forced.

Run with: python -m unittest tools.test_placeholder_sprites -v
"""
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "make_placeholder_sprites.sh"


def _ffprobe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,pix_fmt",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    width, height, pix_fmt = out.stdout.strip().split(",")
    return int(width), int(height), pix_fmt


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not available")
class PlaceholderSpriteTests(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="placeholders-"))

    def _make(self, *args):
        return subprocess.run(
            ["bash", str(SCRIPT), "--out", str(self.out), *args],
            capture_output=True, text=True, check=True)

    def test_named_placeholders_are_512_rgba_and_distinct(self):
        self._make("crumbling.png", "void.png")
        hashes = set()
        for name in ("crumbling.png", "void.png"):
            path = self.out / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(_ffprobe(path), (512, 512, "rgba"), name)
            hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(len(hashes), 2, "placeholders must differ per name")

    def test_existing_files_are_not_overwritten_without_force(self):
        self._make("crumbling.png")
        path = self.out / "crumbling.png"
        before = path.read_bytes()
        self._make("crumbling.png")
        self.assertEqual(path.read_bytes(), before)
        self._make("--force", "crumbling.png")
        self.assertTrue(path.is_file())

    def test_candidate_mode_reads_the_assets_list(self):
        result = self._make("--candidate", "terrain-and-hazards.yml", "5")
        self.assertIn("crumbling.png", result.stdout)
        for name in ("crumbling.png", "crumbling-minor.png",
                     "crumbling-major.png", "void.png"):
            path = self.out / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(_ffprobe(path), (512, 512, "rgba"), name)


if __name__ == "__main__":
    unittest.main()
