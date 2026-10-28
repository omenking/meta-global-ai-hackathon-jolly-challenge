"""Focused checks for the asset tool's iteration-loop behaviour.

Run with: python -m unittest tools.test_asset_tool -v
(or: python tools/test_asset_tool.py)
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_store import (StoreError, add_version, build_prompt_draft,
                         create_asset, load_judgements, load_manifest,
                         lottery_keys, normalize_run_count, save_judgement,
                         save_judgements, save_manifest, split_cost_per_output,
                         update_version, validate_references,
                         validate_run_not_noop)


class JudgementTest(unittest.TestCase):
    def test_checklist_and_preferred_roundtrip(self):
        judgements = {}
        save_judgement(judgements, "asset-v1-123", "looks cracked",
                       checklist={"no_cracks": False, "square_corners": True},
                       preferred=True)
        save_judgement(judgements, "asset-v1-124", "better")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judgements.yml"
            save_judgements(judgements, "", path)
            loaded, _ = load_judgements(path)
        self.assertEqual(loaded["asset-v1-123"]["human_review"], "looks cracked")
        self.assertEqual(loaded["asset-v1-123"]["checklist"],
                         {"no_cracks": False, "square_corners": True})
        self.assertTrue(loaded["asset-v1-123"]["preferred"])
        self.assertEqual(loaded["asset-v1-124"]["human_review"], "better")

    def test_judgement_update_preserves_checklist_when_not_given(self):
        judgements = {}
        save_judgement(judgements, "k", "one", checklist={"no_cracks": True})
        save_judgement(judgements, "k", "two")
        self.assertEqual(judgements["k"]["checklist"], {"no_cracks": True})


class NoopGuardTest(unittest.TestCase):
    PROMPT = "light gray stone tile"

    def test_first_run_identical_prompt_without_reference_is_blocked(self):
        version = {"slug": "v2", "prompt": self.PROMPT, "parent": "v1",
                   "outputs": []}
        parent = {"slug": "v1", "prompt": self.PROMPT, "outputs": [{"key": "x"}]}
        with self.assertRaises(StoreError):
            validate_run_not_noop(version, parent, references=[])

    def test_changed_prompt_or_reference_or_rerun_is_allowed(self):
        parent = {"slug": "v1", "prompt": self.PROMPT, "outputs": [{"key": "x"}]}
        validate_run_not_noop({"slug": "v2", "prompt": "smooth concrete",
                               "parent": "v1", "outputs": []}, parent, [])
        validate_run_not_noop({"slug": "v2", "prompt": self.PROMPT,
                               "parent": "v1", "outputs": []}, parent, ["x.png"])
        validate_run_not_noop({"slug": "v2", "prompt": self.PROMPT,
                               "parent": "v1", "outputs": [{"key": "y"}]},
                              parent, [])
        validate_run_not_noop({"slug": "v1", "prompt": self.PROMPT,
                               "parent": None, "outputs": []}, None, [])


class LotteryCountTest(unittest.TestCase):
    def test_default_is_four(self):
        self.assertEqual(normalize_run_count(None), 4)

    def test_bounds_accepted(self):
        self.assertEqual(normalize_run_count(1), 1)
        self.assertEqual(normalize_run_count(10), 10)
        self.assertEqual(normalize_run_count("3"), 3)

    def test_out_of_range_rejected(self):
        for bad in (0, 11, -1, 2.5, "many", True):
            with self.assertRaises(StoreError, msg=f"num={bad!r}"):
                normalize_run_count(bad)


class LotteryRefsTest(unittest.TestCase):
    def test_none_and_empty_ok(self):
        self.assertEqual(validate_references(None), [])
        self.assertEqual(validate_references([]), [])

    def test_ten_ok_eleven_rejected(self):
        ok = [f"a-{i}.png" for i in range(10)]
        self.assertEqual(len(validate_references(ok)), 10)
        with self.assertRaises(StoreError):
            validate_references(ok + ["extra.png"])

    def test_shape_rejected(self):
        with self.assertRaises(StoreError):
            validate_references("a.png")
        with self.assertRaises(StoreError):
            validate_references([""])


class LotteryKeysTest(unittest.TestCase):
    def test_single_keeps_legacy_key(self):
        self.assertEqual(lottery_keys("a-v-123", 1), ["a-v-123"])

    def test_multi_uses_indexed_keys(self):
        self.assertEqual(lottery_keys("a-v-123", 3),
                         ["a-v-123-1", "a-v-123-2", "a-v-123-3"])
        keys = lottery_keys("a-v-123", 10)
        self.assertEqual(len(keys), 10)
        self.assertEqual(len(set(keys)), 10)


class LotteryCostTest(unittest.TestCase):
    def test_split_divides_total(self):
        self.assertEqual(split_cost_per_output("0.04", 4), "0.01")
        self.assertEqual(split_cost_per_output(0.03, 3), "0.01")

    def test_none_stays_none(self):
        self.assertIsNone(split_cost_per_output(None, 4))


class VersionRefsTest(unittest.TestCase):
    def _assets(self):
        assets = {}
        create_asset(assets, "tile", 512, 512)
        return assets

    def test_add_defaults_to_no_references(self):
        assets = self._assets()
        v = add_version(assets, "tile", "v1", "", "tile prompt")
        self.assertEqual(v["references"], [])

    def test_add_stores_references(self):
        assets = self._assets()
        v = add_version(assets, "tile", "v1", "", "tile prompt",
                        references=["a-v1.png", "b-v2.png"])
        self.assertEqual(v["references"], ["a-v1.png", "b-v2.png"])

    def test_add_rejects_too_many_references(self):
        assets = self._assets()
        with self.assertRaises(StoreError):
            add_version(assets, "tile", "v1", "", "tile prompt",
                        references=[f"a-{i}.png" for i in range(11)])

    def test_add_rejects_bad_reference_shape(self):
        assets = self._assets()
        with self.assertRaises(StoreError):
            add_version(assets, "tile", "v1", "", "tile prompt",
                        references="a.png")

    def test_update_none_leaves_references(self):
        assets = self._assets()
        add_version(assets, "tile", "v1", "", "tile prompt",
                    references=["a-v1.png"])
        v = update_version(assets, "tile", "v1", "", "tile prompt v2")
        self.assertEqual(v["references"], ["a-v1.png"])

    def test_update_replaces_and_clears_references(self):
        assets = self._assets()
        add_version(assets, "tile", "v1", "", "tile prompt",
                    references=["a-v1.png"])
        v = update_version(assets, "tile", "v1", "", "tile prompt",
                           references=["b-v2.png"])
        self.assertEqual(v["references"], ["b-v2.png"])
        v = update_version(assets, "tile", "v1", "", "tile prompt",
                           references=[])
        self.assertEqual(v["references"], [])

    def test_references_survive_save_load(self):
        assets = self._assets()
        add_version(assets, "tile", "v1", "", "tile prompt",
                    references=["a-v1.png"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.yml"
            save_manifest(assets, "", path)
            loaded, _ = load_manifest(path)
        self.assertEqual(loaded["tile"]["versions"][0]["references"],
                         ["a-v1.png"])

    def test_legacy_version_without_references_loads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.yml"
            path.write_text(
                "assets:\n"
                "  tile:\n"
                "    width: 512\n"
                "    height: 512\n"
                "    versions:\n"
                "    - slug: v1\n"
                "      prompt: tile prompt\n"
                "      outputs: []\n",
                encoding="utf-8")
            loaded, _ = load_manifest(path)
        self.assertEqual(loaded["tile"]["versions"][0]["references"], [])


class PromptDraftTest(unittest.TestCase):
    def test_no_judgement_returns_parent(self):
        self.assertEqual(build_prompt_draft("tile prompt", "", {}), "tile prompt")
        self.assertEqual(build_prompt_draft("tile prompt", None, None), "tile prompt")

    def test_review_only_appends_block(self):
        draft = build_prompt_draft("tile", "bad corners", {})
        self.assertIn("tile", draft)
        self.assertIn("Constraints from parent judgement: bad corners", draft)

    def test_failed_checklist_maps_to_constraints(self):
        draft = build_prompt_draft("tile", "", {
            "covers_frame": False,
            "square_corners": False,
            "no_cracks": True,
        })
        self.assertIn("edge to edge", draft)
        self.assertIn("90-degree", draft)
        self.assertNotIn("crack", draft.lower().split("constraints")[0])

    def test_constraints_plus_review(self):
        draft = build_prompt_draft("tile", "still framed", {"no_cracks": False})
        self.assertIn("no cracks", draft)
        self.assertIn('Parent noted: "still framed"', draft)


if __name__ == "__main__":
    unittest.main()
