"""End-to-end checks for level-preview screenshot capture.

Spawns tools/server.py on an ephemeral port, runs tools/capture_level.sh
against it into a temp dir, and asserts the screenshots land with the
expected shape. Needs google-chrome and a Python with Playwright;
skips honestly when either is absent.

Run with: python -m unittest tools.test_level_capture -v
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from capture_level import launch_browser
CAPTURE_SH = ROOT / "tools" / "capture_level.sh"
PREP_SH = ROOT / "tools" / "prep_level_sprites.sh"
SPRITES_DIR = ROOT / "tools" / "static" / "level-sprites"
STAGED_LEVEL = ROOT / "tools" / "static" / "levels" / "chip1.json"


def _chrome_present():
    if os.environ.get("CHROME"):
        return True
    return any(shutil.which(name) for name in
               ("google-chrome", "google-chrome-stable"))


def _playwright_python():
    candidates = [ROOT / ".venv" / "bin" / "python",
                  Path(sys.executable)]
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        exe = str(candidate) if isinstance(candidate, Path) else candidate
        if shutil.which(exe) is None and not Path(exe).is_file():
            continue
        proc = subprocess.run(
            [exe, "-c", "import playwright.sync_api"],
            capture_output=True)
        if proc.returncode == 0:
            return exe
    proc = subprocess.run(["python3", "-c", "import playwright.sync_api"],
                          capture_output=True)
    return "python3" if proc.returncode == 0 else None


def _server_python():
    for exe in (sys.executable, str(ROOT / ".venv" / "bin" / "python")):
        proc = subprocess.run([exe, "-c", "import yaml"],
                              capture_output=True)
        if proc.returncode == 0:
            return exe
    raise unittest.SkipTest("no python with pyyaml for the test server")


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _ffprobe_dims(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,codec_name",
         "-of", "default=noprint_wrappers=1", str(path)],
        capture_output=True, text=True, check=True)
    fields = dict(line.split("=", 1)
                  for line in out.stdout.strip().splitlines())
    return int(fields["width"]), int(fields["height"]), fields["codec_name"]


@unittest.skipUnless(_chrome_present(), "google-chrome not available")
@unittest.skipUnless(_playwright_python(), "no python with playwright")
class LevelCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (SPRITES_DIR / "jolly.png").is_file() \
                or not STAGED_LEVEL.is_file():
            subprocess.run(["bash", str(PREP_SH)], check=True)
        cls.port = _free_port()
        cls.server = subprocess.Popen(
            [_server_python(), str(ROOT / "tools" / "server.py"),
             "--port", str(cls.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        deadline = time.time() + 20
        while True:
            try:
                with urllib.request.urlopen(
                        cls.base_url + "/static/level-preview.html",
                        timeout=2) as res:
                    if res.status == 200:
                        break
            except Exception:
                pass
            if time.time() > deadline:
                cls.server.terminate()
                raise RuntimeError("test server did not start in 20s")
            time.sleep(0.2)
        cls.tmp = Path(tempfile.mkdtemp(prefix="levelcap-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.server.kill()

    def _run_capture(self, *extra):
        outdir = self.tmp / "shots"
        cmd = ["bash", str(CAPTURE_SH), "--url", self.base_url,
               "--outdir", str(outdir), *extra, "chip1"]
        subprocess.run(cmd, check=True, capture_output=True, text=True,
                       timeout=180)
        return outdir

    def test_capture_writes_screenshots(self):
        outdir = self._run_capture()
        shots = sorted(outdir.glob("chip1-????????-??????.png"))
        self.assertEqual(len(shots), 1,
                         f"expected one timestamped shot, got {shots}")
        latest = outdir / "chip1-latest.png"
        self.assertTrue(latest.is_file(), "expected chip1-latest.png")
        self.assertEqual(_ffprobe_dims(latest), (1024, 800, "png"))
        self.assertGreater(latest.stat().st_size, 50_000,
                           "screenshot suspiciously small")

    def test_debug_toggle_hides_panel_and_header(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = launch_browser(p)
            try:
                page = browser.new_page(viewport={"width": 1024,
                                                  "height": 800})
                page.goto(self.base_url +
                          "/static/level-preview.html?level=chip1")
                page.wait_for_selector("body[data-ready]", timeout=30000)
                self.assertTrue(page.is_visible("#panel"))
                self.assertTrue(page.is_visible("header"))
                page.uncheck("#opt-debug")
                self.assertFalse(page.is_visible("#panel"))
                self.assertFalse(page.is_visible("header"))
                page.keyboard.press("d")
                self.assertTrue(page.is_visible("#panel"))
                self.assertTrue(page.is_visible("header"))
            finally:
                browser.close()

    def test_compare_writes_composite(self):
        outdir = self._run_capture("--compare")
        comps = sorted(outdir.glob("chip1-compare-????????-??????.png"))
        self.assertEqual(len(comps), 1,
                         f"expected one composite, got {comps}")
        comp_latest = outdir / "chip1-compare-latest.png"
        self.assertTrue(comp_latest.is_file(),
                        "expected chip1-compare-latest.png")
        self.assertEqual(_ffprobe_dims(comp_latest), (1894, 800, "png"))


if __name__ == "__main__":
    unittest.main()
