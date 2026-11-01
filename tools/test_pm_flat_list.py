"""Checks for the flat PM feature list (/pm).

A feature is a single line item on the main board: the list must show
one row per feature and must not render subtasks (or other sub-info)
in full there. Subtasks live on the feature page and the kanban board.

Run with: python -m unittest tools.test_pm_flat_list -v
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "tools" / "web" / "src" / "App.jsx"


def _section(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


class FlatListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = APP.read_text(encoding="utf-8")

    def test_list_uses_single_line_feature_rows(self):
        self.assertIn("function FeatureRow", self.src)
        self.assertIn("<FeatureRow", self.src)
        row = _section(self.src, "function FeatureRow", "function Board")
        # The row is the feature itself: title links to its page,
        # with only feature-level status/priority/progress alongside.
        self.assertIn("featurePath(feature.id)", row)
        self.assertIn("StatusChip", row)
        self.assertIn("PriorityChip", row)
        self.assertIn("progress", row)

    def test_row_renders_no_subtasks_or_subinfo(self):
        row = _section(self.src, "function FeatureRow", "function Board")
        for forbidden in ("feature.tasks", "taskPath", "TaskStatusChip",
                          "feature.summary", "feature.requires",
                          "feature.branch", "No tasks"):
            self.assertNotIn(forbidden, row)


if __name__ == "__main__":
    unittest.main()
