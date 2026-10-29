"""Focused checks for PM HTML5 routing on the tools server.

The PM React app uses history routing (/pm, /pm/features/<id>, ...), so
the server must hand those paths the built app, not the asset tool.

Run with: python -m unittest tools.test_pm_routing -v
"""
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_INDEX = ROOT / "tools" / "static" / "app" / "index.html"


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _server_python():
    for exe in (sys.executable, str(ROOT / ".venv" / "bin" / "python")):
        proc = subprocess.run([exe, "-c", "import yaml"], capture_output=True)
        if proc.returncode == 0:
            return exe
    raise unittest.SkipTest("no python with pyyaml for the test server")


@unittest.skipUnless(APP_INDEX.is_file(), "tools web app not built (npm run build)")
class PmRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.server = subprocess.Popen(
            [_server_python(), str(ROOT / "tools" / "server.py"),
             "--port", str(cls.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 20
        while True:
            try:
                with urllib.request.urlopen(cls.base + "/", timeout=2) as res:
                    if res.status == 200:
                        break
            except Exception:
                pass
            if time.time() > deadline:
                cls.server.terminate()
                raise RuntimeError("test server did not start in 20s")
            time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.server.kill()

    def _get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as res:
            return res.status, res.read().decode("utf-8", "replace")

    def test_pm_routes_serve_the_tools_app(self):
        for path in ("/pm", "/pm/board", "/pm/features/keys-and-locks",
                     "/pm/features/keys-and-locks/edit",
                     "/pm/features/keys-and-locks/tasks/key-pickup"):
            status, body = self._get(path)
            self.assertEqual(status, 200, path)
            self.assertIn('id="root"', body, path)
            self.assertNotIn("Asset Design Tool", body.split("<script")[0], path)

    def test_other_tools_unaffected(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn('id="root"', body)
        status, body = self._get("/assets")
        self.assertEqual(status, 200)
        self.assertIn("Asset Design Tool", body)
        status, body = self._get("/static/level-preview.html")
        self.assertEqual(status, 200)
        self.assertIn("Level Preview", body)

    def test_api_still_json(self):
        status, body = self._get("/api/pm/features")
        self.assertEqual(status, 200)
        self.assertIn('"features"', body)


if __name__ == "__main__":
    unittest.main()
