"""Checks for session logs, replay and forks.

Run with: python -m unittest tools.test_session_replay -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_sessions  # noqa: E402

HEADER = {"type": "session", "id": "game-movement-room-test1",
          "created_at": "2026-10-29T10:00:00Z", "created_by": "agent",
          "label": "", "level": "movement-room",
          "level_source": {"file": "levels/movement-room.json", "hash": "abc"},
          "feature": "player-movement", "task": None,
          "engine_version": "game-core-1"}
STEPS = [{"type": "step", "n": 1, "t_ms": 500, "input": "right"},
         {"type": "step", "n": 2, "t_ms": 1500, "input": "down"}]
END = {"type": "end", "result": "quit", "steps": 2}


def _text(extra=None):
    lines = [HEADER] + STEPS + [END] + (extra or [])
    return "".join(json.dumps(x) + "\n" for x in lines)


class SessionReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sessreplay-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        game_sessions.write_session(self.tmp, HEADER["id"], _text())

    def test_list_and_filter(self):
        all_ = game_sessions.list_sessions(self.tmp)
        self.assertEqual([s["id"] for s in all_], [HEADER["id"]])
        self.assertEqual(all_[0]["result"], "quit")
        self.assertEqual(len(game_sessions.list_sessions(
            self.tmp, level="movement-room", creator="agent",
            feature="player-movement", date="2026-10-29", result="quit")), 1)
        self.assertEqual(game_sessions.list_sessions(self.tmp, level="nope"), [])

    def test_annotate_appends_without_touching_steps(self):
        before = game_sessions.read_session(self.tmp, HEADER["id"])
        rec = game_sessions.append_annotation(
            self.tmp, HEADER["id"], "human", "wrong turn here",
            labels="Bug, failed")
        self.assertEqual(rec["labels"], ["bug", "failed"])
        after = game_sessions.read_session(self.tmp, HEADER["id"])
        self.assertEqual(after[:len(before)], before)
        self.assertEqual(after[-1]["type"], "annotation")
        self.assertEqual(len(game_sessions.list_sessions(
            self.tmp, label="bug")), 1)
        with self.assertRaises(game_sessions.SessionError):
            game_sessions.append_annotation(
                self.tmp, HEADER["id"], "human", "", labels=[])
        with self.assertRaises(game_sessions.SessionError):
            game_sessions.append_annotation(
                self.tmp, HEADER["id"], "human", "x", labels=["Bad Label!"])

    def test_step_index_at_time_is_time_based(self):
        records = game_sessions.read_session(self.tmp, HEADER["id"])
        self.assertEqual(game_sessions.step_index_at_time(records, 0), 0)
        self.assertEqual(game_sessions.step_index_at_time(records, 0.5), 1)
        self.assertEqual(game_sessions.step_index_at_time(records, 1.4), 1)
        self.assertEqual(game_sessions.step_index_at_time(records, 99), 2)

    def test_fork_keeps_created_by_and_copies_prefix(self):
        forked = game_sessions.write_fork(
            self.tmp, HEADER["id"], 1, "game-movement-room-fork1", "human",
            created_at="2026-10-29T11:00:00Z")
        self.assertEqual(forked[0]["created_by"], "agent")
        self.assertEqual(forked[0]["forked_by"], "human")
        self.assertEqual(forked[0]["forked_from"], HEADER["id"])
        self.assertEqual(forked[0]["fork_step"], 1)
        self.assertEqual([r["type"] for r in forked], ["session", "step"])
        with self.assertRaises(game_sessions.SessionError):
            game_sessions.write_fork(self.tmp, HEADER["id"], 99, "game-x-9", "human")

    def test_version_warnings(self):
        self.assertEqual(game_sessions.version_warnings(
            HEADER, level_hash="abc", engine_version="game-core-1"), [])
        w = game_sessions.version_warnings(
            HEADER, level_hash="zzz", engine_version="game-core-2")
        self.assertTrue(any("level mismatch" in x for x in w))
        self.assertTrue(any("engine mismatch" in x for x in w))

    def test_game_ui_has_sessions_replay_and_fork(self):
        html = (ROOT / "tools/static/game.html").read_text()
        js = (ROOT / "tools/static/game.js").read_text()
        for marker in ("game-replay.js", "sessions-list", "replay-scrub",
                       "replay-speed", "btn-fork", "annotate"):
            self.assertIn(marker, html + js)
        self.assertIn("GameReplay.stepIndexAtTime", js)
        self.assertIn("?replay=", js + html)

    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_replay_js_record_then_replay_same_end_state(self):
        script = r"""
const core = require(process.argv[1]);
const replay = require(process.argv[2]);
const level = { rows: ['#######','#.P...#','#######'],
  legend: { '#':{}, '.':{}, 'P':{} } };
const records = [
 {type:'session', id:'x', level_source:{hash:'a'}, engine_version:'game-core-1'},
 {type:'step', n:1, t_ms:500, input:'right'},
 {type:'step', n:2, t_ms:1500, input:'right'},
 {type:'annotation', author:'human', body:'hi', labels:['bug']},
 {type:'end', result:'quit', steps:2}];
const { states } = replay.stateAt(core, level, 'movement-room', records, 2);
const live = core.replay(level, 'movement-room',
  [{t_ms:500,input:'right'},{t_ms:1500,input:'right'}]);
console.log(JSON.stringify({
  digest: core.stateDigest(states[states.length-1]),
  live: core.stateDigest(live[live.length-1]),
  atTime: replay.stepIndexAtTime(records, 1.0),
  delay: replay.delayMs(records, 2, 2),
  readout: core.readout(states[states.length-1]),
  warnings: replay.warnings(records[0], 'b', 'game-core-1'),
}));
"""
        out = subprocess.run(
            ["node", "-e", script, str(ROOT / "tools/static/game-core.js"),
             str(ROOT / "tools/static/game-replay.js")],
            capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        self.assertEqual(data["digest"], data["live"])
        self.assertEqual(data["atTime"], 1)
        self.assertEqual(data["delay"], 500)
        self.assertEqual(data["readout"]["position"], {"x": 4, "y": 1})
        self.assertTrue(any("level mismatch" in w for w in data["warnings"]))


if __name__ == "__main__":
    unittest.main()
