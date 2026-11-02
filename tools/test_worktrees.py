"""Checks for the /worktrees manager: discovery + stop safety.

Run with: python -m unittest tools.test_worktrees -v
"""
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
import json
import tempfile
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import worktree_mgr  # noqa: E402


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_up(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/worktrees", timeout=2) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(0.2)
    raise AssertionError(f"server on {port} did not come up")


class WorktreeMgrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, "tools/server.py", "--port", str(cls.port)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        cls.data = _wait_up(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    def test_collect_lists_main_worktree_and_self(self):
        paths = [w["path"] for w in self.data["worktrees"]]
        self.assertIn(str(ROOT), paths)
        self.assertEqual(self.data["self"]["port"], self.port)
        selfs = [s for s in self.data["servers"] if s["is_self"]]
        self.assertEqual(len(selfs), 1)
        self.assertEqual(selfs[0]["pid"], self.proc.pid)
        self.assertTrue(selfs[0]["listening"])

    def test_page_served(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/worktrees") as r:
            body = r.read().decode()
        self.assertIn("Worktrees", body)
        self.assertIn("/api/worktrees", body)
        self.assertIn("/api/worktrees/start", body)

    def test_stop_refuses_self_and_non_server(self):
        with self.assertRaises(ValueError):
            worktree_mgr.stop_server(self.proc.pid, self.proc.pid)
        with self.assertRaises(ValueError):
            worktree_mgr.stop_server(os.getpid(), self.proc.pid)  # test runner, not server.py
        with self.assertRaises(ValueError):
            worktree_mgr.stop_server(-1, self.proc.pid)

    def test_enrichment_names_purpose_and_start(self):
        wt = [w for w in self.data["worktrees"] if w["path"] == str(ROOT)][0]
        self.assertEqual(wt["name"], ROOT.name)
        self.assertIn("subject", wt["last_commit"])
        self.assertIsInstance(wt["changed_files"], list)
        srv = [s for s in self.data["servers"] if s["is_self"]][0]
        self.assertTrue(srv["started_at"])
        self.assertIn("worktree_name", srv)

    def test_label_roundtrip(self):
        import urllib.request as u
        def post_label(label):
            req = u.Request(f"http://127.0.0.1:{self.port}/api/worktrees/label",
                            data=json.dumps({"kind": "servers",
                                             "key": "test-cwd|9", "label": label}).encode(),
                            headers={"Content-Type": "application/json"})
            return json.loads(u.urlopen(req).read())
        self.assertEqual(post_label("my test server")["labels"]["servers"]["test-cwd|9"],
                         "my test server")
        self.assertNotIn("test-cwd|9", post_label("")["labels"]["servers"])

    def test_stop_kills_spawned_server(self):
        port = _free_port()
        proc = subprocess.Popen(
            [sys.executable, "tools/server.py", "--port", str(port)],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _wait_up(port)
            result = worktree_mgr.stop_server(proc.pid, self.proc.pid)
            self.assertTrue(result["stopped"])
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()


class LaunchTests(unittest.TestCase):
    def test_launch_reuse_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            (root / "tools/server.py").write_text(
                "import sys\nfrom http.server import HTTPServer, SimpleHTTPRequestHandler\n"
                "HTTPServer(('127.0.0.1', int(sys.argv[2])), SimpleHTTPRequestHandler).serve_forever()\n")
            registered = [{"path": str(root), "exists": True, "bare": False, "prunable": False}]
            with patch.object(worktree_mgr, "list_worktrees", return_value=registered):
                srv = worktree_mgr.start_server(root, str(root))
                try:
                    self.assertTrue(worktree_mgr._listening(srv["port"]))
                    self.assertEqual(worktree_mgr.start_server(root, str(root)), srv)
                finally:
                    worktree_mgr.stop_server(srv["pid"], os.getpid())

    def test_reject_unregistered_and_missing_script(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(worktree_mgr, "list_worktrees", return_value=[]):
                with self.assertRaisesRegex(ValueError, "not registered"):
                    worktree_mgr.start_server(root, str(root))
            registered = [{"path": str(root), "exists": True, "bare": False, "prunable": False}]
            with patch.object(worktree_mgr, "list_worktrees", return_value=registered):
                with self.assertRaisesRegex(ValueError, "no tools/server.py"):
                    worktree_mgr.start_server(root, str(root))


if __name__ == "__main__":
    unittest.main()
