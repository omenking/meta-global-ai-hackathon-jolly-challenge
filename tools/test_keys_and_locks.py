"""Checks for keys and locks (keys-and-locks).

The mechanics live in the pure GameCore step; driven here under
Node. The 5 colours are red, gold, green, blue, silver with real
per-colour art (assets/published/lock_and_keys, no hue shifting).

Run with: python -m unittest tools.test_keys_and_locks -v
"""
import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

COLORS = ("red", "gold", "green", "blue", "silver")


def run_core(script, level_name="keys-room"):
    level = ROOT / "levels" / f"{level_name}.json"
    out = subprocess.run(["node", "-e", script, str(CORE), str(level)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class KeysRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", "keys-room")

    def test_keys_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertTrue(by_id["keys-room"]["test"])

    def test_all_five_keys_locks_and_an_orb_placed(self):
        grid = "".join(self.level["rows"])
        key_colors = {e.get("key_color") for e in self.level["legend"].values()
                      if e.get("key_color")}
        lock_colors = {e.get("lock_color") for e in self.level["legend"].values()
                       if e.get("lock_color")}
        self.assertEqual(key_colors, set(COLORS))
        self.assertEqual(lock_colors, set(COLORS))
        for ch, entry in self.level["legend"].items():
            if entry.get("key_color") or entry.get("lock_color"):
                self.assertIn(ch, grid, f"tile {ch} not placed")
        self.assertIn("*", grid, "orb not placed")
        self.assertIn("P", grid)

    def test_real_sprites_exist_and_differ_per_colour(self):
        sprites = ROOT / "tools" / "static" / "level-sprites"
        for color in COLORS:
            for name in (f"key_{color}.png", f"wall_keyhole_{color}.png"):
                self.assertTrue((sprites / name).is_file(), name)
        hashes = {hashlib.sha256((sprites / f"key_{c}.png").read_bytes()).hexdigest()
                  for c in COLORS}
        self.assertEqual(len(hashes), 5)
        for name in ("key_red", "key_gold", "key_green", "key_blue", "key_sliver"):
            self.assertTrue((ROOT / "assets" / "published" / "lock_and_keys"
                             / f"{name}.png").is_file(), name)


if __name__ == "__main__":
    unittest.main()
