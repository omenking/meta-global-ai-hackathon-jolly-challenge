"""Focused checks for the project-manager store.

Run with: python -m unittest tools.test_pm_store -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pm_store import (StoreError, add_feature_comment, add_task_comment,
                      archive_feature, archive_task, claim_task,
                      create_feature, create_task, delete_comment,
                      derived_unblocks, export_all, export_feature_md,
                      feature_progress, get_feature, link_session, load_pm,
                      move_task, next_review_fixes_id, record_merge,
                      review_rollup, save_pm, seed_pm, set_review,
                      update_comment, update_feature, update_task,
                      validate_attachment_path)


def _data():
    data = {"features": []}
    create_feature(data, "game-shell", "Game shell", priority="urgent")
    create_feature(data, "player-movement", "Movement", requires=["game-shell"])
    return data


class FeatureCrudTest(unittest.TestCase):
    def test_create_and_progress(self):
        data = _data()
        f = get_feature(data, "game-shell")
        self.assertEqual(f["status"], "proposed")
        create_task(data, "game-shell", "t1", "First task")
        create_task(data, "game-shell", "t2", "Second task")
        self.assertEqual(feature_progress(f)["label"], "0/2")
        update_task(data, "game-shell", "t1", {"status": "completed"})
        self.assertEqual(feature_progress(f)["label"], "1/2")

    def test_duplicate_and_bad_slug_rejected(self):
        data = _data()
        with self.assertRaises(StoreError):
            create_feature(data, "game-shell", "Dup")
        with self.assertRaises(StoreError):
            create_feature(data, "Bad Id!", "Bad")
        with self.assertRaises(StoreError):
            create_feature(data, "x", "   ")

    def test_requires_integrity(self):
        data = {"features": []}
        with self.assertRaises(StoreError):
            create_feature(data, "a", "A", requires=["missing"])
        create_feature(data, "a", "A")
        with self.assertRaises(StoreError):
            update_feature(data, "a", {"requires": ["missing"]})
        with self.assertRaises(StoreError):
            update_feature(data, "a", {"requires": ["a"]})

    def test_enums(self):
        data = _data()
        with self.assertRaises(StoreError):
            update_feature(data, "game-shell", {"status": "doing"})
        with self.assertRaises(StoreError):
            update_feature(data, "game-shell", {"priority": "whenever"})
        with self.assertRaises(StoreError):
            create_task(data, "game-shell", "t", "T", status="nope")

    def test_unblocks_derived(self):
        data = _data()
        self.assertEqual(derived_unblocks(data, "game-shell"), ["player-movement"])
        self.assertEqual(derived_unblocks(data, "player-movement"), [])

    def test_archive_hides_from_progress(self):
        data = _data()
        create_task(data, "game-shell", "t1", "One")
        create_task(data, "game-shell", "t2", "Two")
        archive_task(data, "game-shell", "t2")
        self.assertEqual(feature_progress(get_feature(data, "game-shell"))["total"], 1)
        archive_feature(data, "game-shell")
        self.assertTrue(get_feature(data, "game-shell")["archived"])


class TaskTest(unittest.TestCase):
    def test_task_scoping_and_uniqueness(self):
        data = _data()
        create_task(data, "game-shell", "same", "In shell")
        create_task(data, "player-movement", "same", "In movement")
        with self.assertRaises(StoreError):
            create_task(data, "game-shell", "same", "Dup")
        with self.assertRaises(StoreError):
            create_task(data, "nope", "t", "T")

    def test_move_and_claim(self):
        data = _data()
        create_task(data, "game-shell", "t1", "One")
        # Tasks have no in_review stage: the agent saying done means done.
        moved = move_task(data, "game-shell", "t1", "in_review", order=5)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["order"], 5)
        moved = move_task(data, "game-shell", "t1", "completed")
        self.assertEqual(moved["status"], "completed")
        claim_task(data, "game-shell", "t1")
        with self.assertRaises(StoreError):
            claim_task(data, "game-shell", "t1")

    def test_review_fixes_id(self):
        data = _data()
        f = get_feature(data, "game-shell")
        self.assertEqual(next_review_fixes_id(f), "review-fixes-1")
        create_task(data, "game-shell", "review-fixes-1", "Fixes", kind="review-fixes")
        self.assertEqual(next_review_fixes_id(f), "review-fixes-2")


class CommentTest(unittest.TestCase):
    def test_comment_rules(self):
        data = _data()
        c = add_feature_comment(data, "game-shell", "human", "hello",
                                attachments=["screenshots/features/game-shell/a.png"])
        self.assertEqual(c["attachments"], ["screenshots/features/game-shell/a.png"])
        with self.assertRaises(StoreError):
            add_feature_comment(data, "game-shell", "robot", "hi")
        with self.assertRaises(StoreError):
            add_feature_comment(data, "game-shell", "human", "  ")
        edited = update_comment(get_feature(data, "game-shell")["comments"],
                                c["id"], "edited")
        self.assertEqual(edited["body"], "edited")
        agent = add_feature_comment(data, "game-shell", "agent", "agent note")
        with self.assertRaises(StoreError):
            update_comment(get_feature(data, "game-shell")["comments"],
                           agent["id"], "rewrite")
        with self.assertRaises(StoreError):
            delete_comment(get_feature(data, "game-shell")["comments"], agent["id"])
        delete_comment(get_feature(data, "game-shell")["comments"], c["id"])
        self.assertEqual(len(get_feature(data, "game-shell")["comments"]), 1)

    def test_task_comment_and_attachment_guard(self):
        data = _data()
        create_task(data, "game-shell", "t1", "One")
        c = add_task_comment(data, "game-shell", "t1", "agent", "done",
                             session_refs=[{"id": "s1", "level": "chip1",
                                            "created_by": "agent", "result": "won"}])
        self.assertEqual(c["session_refs"][0]["id"], "s1")
        with self.assertRaises(StoreError):
            validate_attachment_path("../secret.png")
        with self.assertRaises(StoreError):
            validate_attachment_path("/etc/passwd")
        self.assertEqual(validate_attachment_path("features/x/a.png"),
                         "screenshots/features/x/a.png")


class ReviewAndSessionTest(unittest.TestCase):
    def test_review_decisions_recorded(self):
        data = _data()
        with self.assertRaises(StoreError):
            set_review(data, "game-shell", "changes_requested", "human")
        f = set_review(data, "game-shell", "changes_requested", "human",
                       comment_body="fix the thing")
        self.assertEqual(f["review"]["decision"], "changes_requested")
        self.assertEqual(f["status"], "in_progress")
        f = set_review(data, "game-shell", "approved_for_merge", "human")
        self.assertEqual(f["review"]["decision"], "approved_for_merge")
        # approved_for_merge must NOT complete the feature.
        self.assertNotEqual(f["status"], "completed")

    def test_stored_in_review_task_loads_as_completed(self):
        data = _data()
        create_task(data, "game-shell", "t1", "One")
        get_feature(data, "game-shell")["tasks"][0]["status"] = "completed"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pm.yml"
            save_pm(data, "", path)
            text = path.read_text(encoding="utf-8").replace(
                "status: completed", "status: in_review", 1)
            path.write_text(text, encoding="utf-8")
            loaded, _ = load_pm(path)
        self.assertEqual(loaded["features"][0]["tasks"][0]["status"], "completed")

    def test_merge_completes(self):
        data = _data()
        create_task(data, "game-shell", "t1", "One")
        update_task(data, "game-shell", "t1", {"status": "in_review"})
        self.assertEqual(get_feature(data, "game-shell")["tasks"][0]["status"],
                         "completed")
        f = record_merge(data, "game-shell", "abc123")
        self.assertEqual(f["status"], "completed")
        self.assertEqual(f["merged"]["commit"], "abc123")
        self.assertEqual(f["tasks"][0]["status"], "completed")

    def test_session_link_and_rollup(self):
        data = _data()
        create_task(data, "game-shell", "t1", "One")
        add_task_comment(data, "game-shell", "t1", "agent", "played it",
                         attachments=["screenshots/features/game-shell/a.png"],
                         session_refs=[{"id": "s1", "level": "chip1",
                                        "created_by": "agent", "result": "won"}])
        link_session(data, "game-shell",
                     {"id": "s2", "level": "chip1", "created_by": "human",
                      "result": "lost"})
        roll = review_rollup(data, "game-shell")
        self.assertEqual(roll["gallery"], ["screenshots/features/game-shell/a.png"])
        self.assertEqual(len(roll["sessions"]), 2)
        self.assertEqual(roll["progress"]["label"], "0/1")


class RoundTripAndSeedTest(unittest.TestCase):
    def test_atomic_roundtrip(self):
        data = _data()
        create_task(data, "game-shell", "t1", "One")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pm.yml"
            save_pm(data, "# header\n", path)
            loaded, header = load_pm(path)
            self.assertEqual(header, "# header\n")
            self.assertEqual(loaded["features"][0]["tasks"][0]["id"], "t1")
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# header"))

    def test_seed_idempotent(self):
        data = {"features": []}
        first = seed_pm(data)
        self.assertGreater(first["features_added"], 0)
        ids = [f["id"] for f in data["features"]]
        self.assertIn("keys-and-locks", ids)
        self.assertIn("session-logs-replay", ids)
        total_tasks = sum(len(f["tasks"]) for f in data["features"])
        self.assertGreater(total_tasks, 20)
        second = seed_pm(data)
        self.assertEqual(second, {"features_added": 0, "tasks_added": 0})
        self.assertEqual(sum(len(f["tasks"]) for f in data["features"]), total_tasks)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pm.yml"
            save_pm(data, "", path)
            loaded, _ = load_pm(path)
            self.assertEqual(len(loaded["features"]), len(data["features"]))

    def test_export(self):
        data = {"features": []}
        seed_pm(data)
        md = export_feature_md(get_feature(data, "keys-and-locks"), data)
        self.assertIn("# Feature: Keys and locks", md)
        self.assertIn("## Tasks", md)
        self.assertIn("keys-and-locks/key-pickup", md)
        self.assertIn("## Testing", md)
        with tempfile.TemporaryDirectory() as tmp:
            written = export_all(data, Path(tmp))
            self.assertEqual(len(written), len(data["features"]))
            self.assertTrue((Path(tmp) / "keys-and-locks.md").is_file())


if __name__ == "__main__":
    unittest.main()
