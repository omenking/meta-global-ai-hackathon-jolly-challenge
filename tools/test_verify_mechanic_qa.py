"""Checks for the Q&A gate (tools/verify_mechanic_qa.py).

Run with: python -m unittest tools.test_verify_mechanic_qa -v
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_sessions  # noqa: E402
import pm_store  # noqa: E402
import verify_mechanic_qa as qa  # noqa: E402


def _feature(fid="qa-demo", sessions=None):
    return {
        "id": fid, "title": "QA demo", "summary": "", "status": "in_review",
        "priority": "medium", "epic": "mechanic-sanity-checks",
        "requires": [], "test_level": "movement-room",
        "spec": {}, "sessions": sessions or [],
        "comments": [{"id": "c1", "author": "agent", "created": "2026-11-02T00:00:00",
                      "body": "shot", "labels": [],
                      "attachments": ["screenshots/features/qa-demo/x.png"],
                      "session_refs": []}],
        "tasks": [{"id": "sanity-check", "feature_id": fid, "title": "Sanity",
                   "description": "", "acceptance": "", "status": "completed",
                   "priority": "medium", "requires": [], "order": 2,
                   "kind": "qa", "commit": None, "archived": False,
                   "created": "2026-11-02T00:00:00", "updated": "2026-11-02T00:00:00",
                   "comments": [{"id": "c1", "author": "agent",
                                 "created": "2026-11-02T00:00:00",
                                 "body": "Rule -> evidence: move -> session s1",
                                 "labels": [], "attachments": [],
                                 "session_refs": []}]}],
        "review": {}, "archived": False,
        "created": "2026-11-02T00:00:00", "updated": "2026-11-02T00:00:00",
    }


def _write_pm(tmp: Path, feature) -> Path:
    data = {"features": [feature], "epics": [
        {"id": "mechanic-sanity-checks", "title": "Mechanics", "summary": "",
         "archived": False, "created": "2026-11-02T00:00:00",
         "updated": "2026-11-02T00:00:00"}]}
    pm = tmp / "pm.yml"
    pm_store.save_pm(data, "# test\n", pm)
    return pm


def _session(tmp: Path, sid, label="", result="quit", steps=None, extra=None):
    header = {"type": "session", "id": sid, "created_at": "2026-11-02T00:00:00Z",
              "created_by": "agent", "label": label, "level": "movement-room",
              "level_source": {"file": "levels/movement-room.json", "hash": "x"},
              "feature": "qa-demo", "task": "qa-verification",
              "branch": "feat/qa-demo", "commit": "abc123",
              "engine_version": "game-core-2"}
    lines = [header] + (steps or [{"type": "step", "n": 1, "t_ms": 100,
                                   "input": "right"}])
    lines.append({"type": "end", "result": result,
                  "steps": len(lines) - 1, "orbs_left": None})
    lines += extra or []
    path = tmp / f"{sid}.jsonl"
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return {"id": sid, "path": f"sessions/{sid}.jsonl", "level": "movement-room",
            "created_by": "agent", "result": result, "label": label}


class VerifyMechanicQaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qa-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _run(self, feature):
        pm = _write_pm(self.tmp, feature)
        return qa.verify(feature["id"], ROOT, pm, [self.tmp])

    def _by_name(self, report):
        return {c["name"]: c for c in report["checks"]}

    def test_no_sessions_fails_gate(self):
        report = self._run(_feature())
        by = self._by_name(report)
        self.assertFalse(by["sessions_linked"]["ok"])
        self.assertFalse(by["agent_success_session_won"]["ok"])
        self.assertFalse(by["agent_naive_failure_session"]["ok"])

    def test_human_only_session_does_not_count_as_agent(self):
        ref = _session(self.tmp, "s-human", result="won")
        # Rewrite creator to human.
        p = self.tmp / "s-human.jsonl"
        recs = [json.loads(x) for x in p.read_text().splitlines()]
        recs[0]["created_by"] = "human"
        p.write_text("".join(json.dumps(x) + "\n" for x in recs))
        report = self._run(_feature(sessions=[ref]))
        by = self._by_name(report)
        self.assertFalse(by["agent_success_session_won"]["ok"])

    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_agent_won_session_replays_and_passes_core_checks(self):
        # movement-room: win by collecting orbs + warp is level-specific;
        # a one-step agent session proves replay plumbing, and the
        # won-classification checks stay honest about the end result.
        ref = _session(self.tmp, "s-quit", result="quit")
        report = self._run(_feature(sessions=[ref]))
        by = self._by_name(report)
        self.assertTrue(by["session:s-quit:deterministic_replay"]["ok"])
        self.assertTrue(by["session:s-quit:end_state_matches"]["ok"])
        self.assertTrue(by["empty_log_does_not_win"]["ok"])

    def test_tampered_step_count_fails(self):
        ref = _session(self.tmp, "s-tamper", result="quit")
        p = self.tmp / "s-tamper.jsonl"
        recs = [json.loads(x) for x in p.read_text().splitlines()]
        recs[-1]["steps"] = 99
        p.write_text("".join(json.dumps(x) + "\n" for x in recs))
        report = self._run(_feature(sessions=[ref]))
        by = self._by_name(report)
        self.assertFalse(by["session:s-tamper:step_count_matches"]["ok"])


if __name__ == "__main__":
    unittest.main()
