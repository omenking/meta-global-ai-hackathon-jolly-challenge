"""Checks for the Muse asset driver bookkeeping CLI.

Only the brief composition is exercised here; generation and judging
happen in a Muse session against a live asset server.

Run with: python -m unittest tools.test_asset_driver -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_driver import (compose_brief, cost_record_cmd, cost_session_id,
                          report_judgements, report_publish, report_turn)

MANIFEST = {"pack": "crumbling", "assets": [
    {"file": "crumbling.png", "kind": "tiles", "bundled": True,
     "shows": "intact tile"},
    {"file": "void.png", "kind": "tiles", "bundled": True,
     "shows": "fallen hole"},
]}


class BriefTests(unittest.TestCase):
    def test_brief_carries_manifest_shows_and_checklist(self):
        brief = compose_brief(MANIFEST, "void.png")
        self.assertIn("fallen hole", brief)
        self.assertIn("64px", brief)

    def test_brief_rejects_unknown_asset(self):
        with self.assertRaises(SystemExit):
            compose_brief(MANIFEST, "missing.png")


class CostCentreTests(unittest.TestCase):
    def test_cost_record_groups_one_run_under_a_named_session(self):
        cmd = cost_record_cmd("crumbling-void", "s20261101-164222-4", 1, 4,
                              "meta-global-ai-hackathon-jolly-challenge",
                              "Asset driver: crumbling void — grounded rerun",
                              parent="01a1989b-2d1f-7ae3-87b0-03b8655a0f98")
        self.assertEqual(cost_session_id("crumbling-void", "s20261101-164222-4"),
                         "asset-driver-crumbling-void-s20261101-164222-4")
        self.assertIn("muse-image-1.0", cmd)
        self.assertEqual(cmd[cmd.index("--images") + 1], "4")
        self.assertEqual(cmd[cmd.index("--name") + 1],
                         "Asset driver: crumbling void — grounded rerun")
        self.assertEqual(cmd[cmd.index("--id") + 1],
                         "asset-s20261101-164222-4-t1")
        self.assertEqual(cmd[cmd.index("--parent") + 1],
                         "01a1989b-2d1f-7ae3-87b0-03b8655a0f98")


class ReportCaptureTests(unittest.TestCase):
    def test_report_is_appended_live_turn_judge_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.yml"
            report_turn(path, {"asset": "void", "session": "s1"},
                        {"seq": 1, "prompt": "hole", "references": ["a.png"],
                         "outputs": [{"key": "k1", "path": "assets/outputs/k1.png"},
                                     {"key": "k2", "path": "assets/outputs/k2.png"}],
                         "cost_total": "0.02"})
            report_judgements(path, 1, {"k1": "good: winner", "k2": "bad: well"},
                              preferred="k1")
            done = report_publish(path, "k1", "packs/x/assets/void.png")
            loaded = yaml.safe_load(path.read_text())
            self.assertEqual(loaded["spend_usd"], "0.02")
            self.assertEqual(loaded["winner"], "k1")
            self.assertTrue(loaded["turns"][0]["outputs"][0]["preferred"])
            self.assertEqual(loaded["turns"][0]["outputs"][1]["verdict"],
                             "bad: well")
            self.assertEqual(done["pack_file"], "packs/x/assets/void.png")


if __name__ == "__main__":
    unittest.main()
