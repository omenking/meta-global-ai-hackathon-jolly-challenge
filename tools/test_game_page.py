"""Static checks for the game page scaffold (game-shell/scaffold-game-page).

Run with: python -m unittest tools.test_game_page -v
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME_HTML = ROOT / "tools" / "static" / "game.html"
GAME_JS = ROOT / "tools" / "static" / "game.js"


class GamePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = GAME_HTML.read_text(encoding="utf-8")
        cls.js = GAME_JS.read_text(encoding="utf-8")

    def test_game_page_exists_and_loads_scripts(self):
        self.assertIn('src="vendor/pixi.min.js"', self.html)
        self.assertIn('src="game.js"', self.html)
        self.assertIn('id="stage"', self.html)

    def test_renders_chosen_level_from_rows_and_legend(self):
        self.assertIn("params.get('level')", self.js)
        self.assertIn("'levels/' + levelName + '.json'", self.js)
        self.assertIn("level.rows", self.js)
        self.assertIn("level.legend", self.js)
        self.assertIn("'level-sprites/' + name", self.js)

    def test_sets_capture_readiness_marker(self):
        # capture_level.py --page game waits for body[data-ready="<level>"].
        self.assertIn("document.body.dataset.ready = levelName", self.js)


if __name__ == "__main__":
    unittest.main()
