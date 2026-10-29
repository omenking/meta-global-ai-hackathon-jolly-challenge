"""Focused checks for the asset tool's iteration-loop behaviour.

Run with: python -m unittest tools.test_asset_tool -v
(or: python tools/test_asset_tool.py)
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_store import (StoreError, add_turn, add_version,
                         build_prompt_draft, create_asset, create_session,
                         get_session, load_sessions, load_judgements,
                         load_manifest, lottery_keys, mark_turn_failed,
                         normalize_run_count, publish_slug,
                         record_turn_outputs, save_judgement, save_judgements,
                         save_manifest, save_sessions, session_context_refs,
                         split_cost_per_output, update_version,
                         validate_references, validate_run_not_noop,
                         validate_upload)


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


class SessionStoreTest(unittest.TestCase):
    def _sessions(self):
        sessions = {}
        create_session(sessions, "s1", "tile", title="try cracks")
        return sessions

    def test_create_rejects_bad_and_duplicate_ids(self):
        sessions = {}
        with self.assertRaises(StoreError):
            create_session(sessions, "bad id!", "tile")
        with self.assertRaises(StoreError):
            create_session(sessions, "s1", "")
        create_session(sessions, "s1", "tile")
        with self.assertRaises(StoreError):
            create_session(sessions, "s1", "tile")

    def test_get_missing_raises(self):
        with self.assertRaises(StoreError):
            get_session({}, "nope")

    def test_add_turn_sequences_and_validates(self):
        sessions = self._sessions()
        t1 = add_turn(sessions, "s1", "first delta", [], 1)
        t2 = add_turn(sessions, "s1", "second delta", ["a.png"], 2)
        self.assertEqual((t1["seq"], t2["seq"]), (1, 2))
        self.assertIsNone(t1["status"])
        self.assertIsNone(t1["provider_session"])
        with self.assertRaises(StoreError):
            add_turn(sessions, "s1", "   ", [], 1)
        with self.assertRaises(StoreError):
            add_turn(sessions, "s1", "x", [f"a-{i}.png" for i in range(11)], 1)

    def test_record_and_fail_turn(self):
        sessions = self._sessions()
        add_turn(sessions, "s1", "delta", [], 2)
        info = [{"key": "k1", "path": "assets/outputs/k1.png"},
                {"key": "k2", "path": "assets/outputs/k2.png"}]
        turn = record_turn_outputs(sessions, "s1", 1, info, "0.02",
                                   full_prompt_sent="delta")
        self.assertEqual(turn["status"], "completed")
        self.assertEqual(turn["cost_total"], "0.02")
        self.assertEqual(turn["full_prompt_sent"], "delta")
        self.assertEqual([o["key"] for o in turn["outputs"]], ["k1", "k2"])
        add_turn(sessions, "s1", "next", [], 1)
        mark_turn_failed(sessions, "s1", 2)
        self.assertEqual(sessions["s1"]["turns"][1]["status"], "failed")
        with self.assertRaises(StoreError):
            record_turn_outputs(sessions, "s1", 9, [], None)

    def test_sessions_survive_save_load(self):
        sessions = self._sessions()
        add_turn(sessions, "s1", "delta", [], 1)
        record_turn_outputs(sessions, "s1", 1,
                            [{"key": "k1", "path": "assets/outputs/k1.png"}],
                            "0.01", full_prompt_sent="delta")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sessions.yml"
            save_sessions(sessions, "", path)
            loaded, _ = load_sessions(path)
        self.assertEqual(loaded["s1"]["turns"][0]["outputs"][0]["key"], "k1")
        self.assertEqual(loaded["s1"]["turns"][0]["full_prompt_sent"], "delta")


class SessionContextTest(unittest.TestCase):
    def _session(self):
        return {"turns": [
            {"outputs": [{"key": "a"}, {"key": "b"}]},
            {"outputs": [{"key": "c"}]},
        ]}

    def test_empty_session_carries_nothing(self):
        self.assertEqual(session_context_refs({"turns": []}), [])

    def test_newest_first_order(self):
        self.assertEqual(session_context_refs(self._session()),
                         ["c.png", "b.png", "a.png"])

    def test_preferred_sorts_first(self):
        judgements = {"a": {"preferred": True}}
        self.assertEqual(session_context_refs(self._session(), judgements)[0],
                         "a.png")

    def test_cap_respected(self):
        session = {"turns": [{"outputs": [{"key": f"k{i}"} for i in range(12)]}]}
        self.assertEqual(len(session_context_refs(session)), 10)


class PublishSlugTest(unittest.TestCase):
    def test_slug_shape(self):
        slug = publish_slug("s20261028-120000", 2)
        self.assertEqual(slug, "s20261028-120000-t2")

    def test_slug_sanitizes_weird_ids(self):
        slug = publish_slug("weird id", 1)
        self.assertRegex(slug, r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class UploadValidationTest(unittest.TestCase):
    def test_good_names_accepted(self):
        self.assertEqual(validate_upload("ref.png", 10), "ref.png")
        self.assertEqual(validate_upload("a/b.JPG", 10), "b.JPG")

    def test_bad_extension_rejected(self):
        with self.assertRaises(StoreError):
            validate_upload("notes.txt", 10)

    def test_empty_and_oversized_rejected(self):
        with self.assertRaises(StoreError):
            validate_upload("a.png", 0)
        with self.assertRaises(StoreError):
            validate_upload("a.png", 8 * 1024 * 1024 + 1)

    def test_blank_name_rejected(self):
        with self.assertRaises(StoreError):
            validate_upload("   ", 10)


if __name__ == "__main__":
    unittest.main()
