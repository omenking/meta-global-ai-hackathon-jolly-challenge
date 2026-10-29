"""Checks for game menus (game-shell/game-menus).

Run with: python -m unittest tools.test_game_menus -v
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402


class GameMenuTests(unittest.TestCase):
    def test_levels_listed_with_test_flag(self):
        levels = game_levels.list_levels(ROOT / "levels")
        by_id = {l["id"]: l for l in levels}
        self.assertIn("chip1", by_id)
        self.assertFalse(by_id["chip1"]["test"])
        self.assertIn("test-room", by_id)
        self.assertTrue(by_id["test-room"]["test"])

    def test_test_room_is_a_valid_level(self):
        level = game_levels.load_level(ROOT / "levels", "test-room")
        rows = level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        flat = "".join(rows)
        self.assertIn("P", flat)
        for row in rows:
            for ch in row:
                self.assertIn(ch, level["legend"])

    def test_bad_level_id_rejected(self):
        with self.assertRaises(game_levels.LevelError):
            game_levels.load_level(ROOT / "levels", "../chip1")

    def test_menu_markup_and_start_wiring(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        for marker in ('id="menu-test-level"', 'id="btn-start-level"'):
            self.assertIn(marker, html)
        self.assertIn("fetch('/api/game/levels')", js)
        self.assertIn("next.set('level', chosen)", js)

    def test_test_play_shows_only_the_test_room(self):
        # Review fix: the full chip1 level must not be the game's
        # default or a menu choice; chip1 stays preserved in levels/.
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("params.get('level') || 'test-room'", js)
        self.assertIn("if (!item.test) continue;", js)
        self.assertTrue((ROOT / "levels" / "chip1.json").is_file())

    def test_test_room_has_player_orb_and_gate(self):
        level = game_levels.load_level(ROOT / "levels", "test-room")
        flat = "".join(level["rows"])
        for ch in ("P", "*", "G"):
            self.assertIn(ch, flat)
        self.assertEqual(len(level["rows"]), 6)
        self.assertTrue(all(len(r) == 7 for r in level["rows"]))

    def test_prep_stages_all_levels(self):
        script = (ROOT / "tools" / "prep_level_sprites.sh").read_text(
            encoding="utf-8")
        self.assertIn('cp "$ROOT/levels/"*.json "$LVL/"', script)


if __name__ == "__main__":
    unittest.main()
