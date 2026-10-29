#!/usr/bin/env python3
"""Capture the /game page (React overlay + embedded canvas) to a PNG.

Run with a Python that has Playwright (see capture_level.sh):
    python tools/game_screenshot.py <url> <out.png> [width] [height]
Waits until the embedded game iframe reports data-ready, then shoots
the full viewport — the closest a web page can get to "the entire
browser window" (browser chrome itself is not capturable).
"""
import sys
from pathlib import Path


def main(argv):
    if len(argv) < 3:
        print("usage: game_screenshot.py <url> <out.png> [width] [height]",
              file=sys.stderr)
        return 2
    url, out = argv[1], Path(argv[2])
    width = int(argv[3]) if len(argv) > 3 else 1200
    height = int(argv[4]) if len(argv) > 4 else 800
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, channel="chrome")
        except Exception:
            browser = p.chromium.launch(
                headless=True, executable_path="/usr/bin/google-chrome",
                args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_function(
                """() => { const f = document.querySelector('iframe');
                   return f && f.contentDocument &&
                     f.contentDocument.body.dataset.ready; }""",
                timeout=30000)
            page.wait_for_timeout(600)
            out.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out))
        finally:
            browser.close()
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
