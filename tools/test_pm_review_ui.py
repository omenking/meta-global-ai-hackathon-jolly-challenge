"""Checks for Review page action feedback (game-shell/review-fixes-1).

Pressing Request changes recorded the decision but showed nothing,
so it was pressed twice and duplicated the comment. The page must
confirm the recorded decision, clear the comment box, and block a
second submit while/after recording.

Run with: python -m unittest tools.test_pm_review_ui -v
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "tools" / "web" / "src" / "App.jsx"


class ReviewUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = APP.read_text(encoding="utf-8")

    def test_review_action_shows_confirmation(self):
        self.assertIn("reviewNotice", self.src)
        self.assertIn("Recorded:", self.src)

    def test_review_action_clears_comment_and_guards_resubmit(self):
        self.assertIn("setComment('')", self.src)
        self.assertIn("isDisabled={busy || !!reviewNotice}", self.src)


if __name__ == "__main__":
    unittest.main()
