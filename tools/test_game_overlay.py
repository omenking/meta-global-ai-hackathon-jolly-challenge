"""Checks for the operator replay interface (review-fixes-5).

Run with: python -m unittest tools.test_game_overlay -v
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class GameOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "tools/web/src/GamePage.jsx").read_text()
        cls.app = (ROOT / "tools/web/src/App.jsx").read_text()
        cls.game_js = (ROOT / "tools/static/game.js").read_text()
        cls.server = (ROOT / "tools/server.py").read_text()
        cls.sessions_py = (ROOT / "tools/game_sessions.py").read_text()

    def test_game_route_serves_operator_page(self):
        self.assertIn('"/game"', self.app + self.page)
        self.assertIn("GamePage", self.app)
        self.assertIn('"game"', self.server)

    def test_unobstructed_viewport(self):
        # Canvas fills its zone; no Leva/HeroUI overlay panel remains.
        self.assertIn("embed=1", self.page)
        self.assertNotIn("leva", self.page.lower())
        self.assertIn('title="Game"', self.page)

    def test_three_zones_and_unified_timeline(self):
        for marker in ("Sessions", "STEP INSPECTOR", "Timeline",
                       "Step back", "Step forward", "Speed"):
            self.assertIn(marker, self.page)
        # Exactly one timeline scrubber in the transport bar.
        self.assertEqual(self.page.count('aria-label="Timeline"'), 1)

    def test_current_session_step_and_annotate_at_step(self):
        for marker in ("Current" if False else "No session loaded",
                       "Annotate this step", "Fork from step", "duration_s"):
            self.assertIn(marker, self.page)
        self.assertIn('"step": step', self.sessions_py)
        self.assertIn("togglePlay", self.game_js)
        self.assertIn("ArrowLeft", self.game_js)

    def test_screenshot_button_saves_to_screenshots_game(self):
        self.assertIn("Screenshot", self.page)
        self.assertIn("/api/game/screenshot", self.page + self.server)
        helper = ROOT / "tools/game_screenshot.py"
        self.assertTrue(helper.is_file())
        self.assertIn("screenshot", helper.read_text().lower())

    def test_embed_keeps_aspect_ratio_on_resize(self):
        self.assertIn("fitBoard", self.game_js)
        self.assertIn("resize", self.game_js)
        html = (ROOT / "tools/static/game.html").read_text()
        self.assertNotIn("100% !important", html)

    def test_board_gets_space_at_narrow_windows(self):
        self.assertIn("innerWidth >= 1100", self.page)
        self.assertIn("min(300px,34vw)", self.page)

    def test_filters_and_diagnostics_disclosed(self):
        self.assertIn("More filters", self.page)
        self.assertIn("Diagnostics", self.page)
        self.assertIn("Hide empty", self.page)


if __name__ == "__main__":
    unittest.main()
