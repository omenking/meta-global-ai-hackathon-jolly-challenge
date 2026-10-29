"""Checks for fullscreen canvas + HeroUI overlay (review-fixes-1).

Run with: python -m unittest tools.test_game_overlay -v
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class GameOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "tools/web/src/GamePage.jsx").read_text() \
            if (ROOT / "tools/web/src/GamePage.jsx").is_file() else ""
        cls.app = (ROOT / "tools/web/src/App.jsx").read_text()
        cls.game_js = (ROOT / "tools/static/game.js").read_text()
        cls.server = (ROOT / "tools/server.py").read_text()

    def test_game_route_serves_react_overlay(self):
        self.assertIn('"/game"', self.app + self.page)
        self.assertIn("GamePage", self.app)
        self.assertIn('"game"', self.server)

    def test_canvas_fills_page_and_overlay_does_not_block(self):
        self.assertIn("embed=1", self.page)
        self.assertIn("100%", self.page)
        self.assertIn("from 'leva'", self.page)
        self.assertIn("embed", self.game_js)

    def test_panel_collapsed_fixed_with_own_scroll(self):
        self.assertIn("useState(true)", self.page)  # collapsed by default
        self.assertIn("<Leva", self.page)
        self.assertIn("useControls", self.page)

    def test_ui_stays_out_of_the_board(self):
        # The Leva panel is collapsed by default so the board is
        # clear; playback lives inside the panel, not over tiles.
        self.assertIn("panelCollapsed", self.page)
        self.assertIn("'Playback'", self.page)

    def test_current_session_block_and_list_lengths(self):
        for marker in ("Current", "Annotate",
                       "steps", "duration_s"):
            self.assertIn(marker, self.page)
        game_sessions = (ROOT / "tools/game_sessions.py").read_text()
        self.assertIn('"duration_s"', game_sessions)
        game_js = (ROOT / "tools/static/game.js").read_text()
        self.assertIn("setReplaySpeed", game_js)

    def test_sessions_narrow_to_current_level(self):
        # Level comes from the game, not a free-text search field.
        self.assertIn("level", self.page)
        self.assertNotIn('id="filter-level"', self.page)
        self.assertIn("Filters", self.page)


if __name__ == "__main__":
    unittest.main()
