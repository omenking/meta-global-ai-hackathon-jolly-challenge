"""Checks for JSONL session recording (game-shell/session-recording).

Run with: python -m unittest tools.test_game_sessions -v
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

RECORDER = ROOT / "tools" / "static" / "game-session.js"

SCRIPT = r"""
const rec = require(process.argv[1]);
const r = rec.createRecorder({
  id: 'game-chip1-test1', created_at: '2026-10-29T00:00:00Z',
  created_by: 'agent', level: 'chip1',
  level_file: 'levels/chip1.json', level_data: { rows: ['P.'] },
  feature: 'game-shell', task: 'session-recording',
});
r.recordStep(1, 0, 'up');
r.recordStep(2, 500, 'left');
r.end('quit', { time_left: null });
process.stdout.write(r.toJSONL());
"""


def _node_jsonl():
    out = subprocess.run(["node", "-e", SCRIPT, str(RECORDER)],
                         capture_output=True, text=True, check=True)
    return out.stdout


@unittest.skipUnless(shutil.which("node"), "node not available")
class SessionRecorderTests(unittest.TestCase):
    def test_recorder_emits_header_steps_end(self):
        records = [json.loads(l) for l in _node_jsonl().splitlines()]
        self.assertEqual(records[0]["type"], "session")
        self.assertEqual(records[0]["created_by"], "agent")
        self.assertEqual(records[0]["level"], "chip1")
        self.assertIn("hash", records[0]["level_source"])
        self.assertEqual([r["type"] for r in records[1:]],
                         ["step", "step", "end"])
        self.assertEqual(records[1], {"type": "step", "n": 1,
                                      "t_ms": 0, "input": "up"})
        self.assertEqual(records[-1]["result"], "quit")
        self.assertEqual(records[-1]["steps"], 2)


class SessionWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gamesess-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_write_then_read_round_trip(self):
        text = _node_jsonl() if shutil.which("node") else (
            '{"type":"session","id":"game-chip1-test1"}\n'
            '{"type":"step","n":1,"t_ms":0,"input":"up"}\n'
            '{"type":"end","result":"quit","steps":1}\n')
        path = game_sessions.write_session(
            self.tmp, "game-chip1-test1", text)
        self.assertTrue(path.is_file())
        records = game_sessions.read_session(self.tmp, "game-chip1-test1")
        self.assertEqual(records[0]["type"], "session")
        self.assertEqual(records[-1]["type"], "end")

    def test_rejects_bad_id_and_malformed_lines(self):
        with self.assertRaises(game_sessions.SessionError):
            game_sessions.write_session(self.tmp, "../evil", "{}")
        with self.assertRaises(game_sessions.SessionError):
            game_sessions.write_session(
                self.tmp, "game-x-1", '{"type":"step","n":1,"t_ms":0}\n')
        with self.assertRaises(game_sessions.SessionError):
            game_sessions.write_session(
                self.tmp, "game-x-1",
                '{"type":"session","id":"game-x-2"}\n')

    def test_game_page_records_from_first_move_not_load(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("GameSession.createRecorder", js)
        self.assertIn("ensureRecorder", js)
        self.assertIn("no session yet", js)
        self.assertIn("pagehide", js)


if __name__ == "__main__":
    unittest.main()
