#!/usr/bin/env python3
"""Capture the level-preview page to screenshots/ via headless Chrome.

Headless CLI flags alone cannot wait for the page's post-load async render
(fetch + texture upload finish after window load), so this drives system
Chrome through Playwright and waits for the body's data-ready marker.

Usage: capture_level.py [--url URL] [--outdir DIR] [--window-size WxH]
                        [--page preview|game] [--feature ID] [--compare]
                        <level>

--page game captures the game page (static/game.html) instead of the
level preview, so the agent can screenshot a feature's Test Level from
whichever checkout (main or worktree) and port it is told; --feature
files the shot under screenshots/features/<feature-id>/ by default.
Both pages must set body[data-ready="<level>"] when rendered.
"""
import argparse
import datetime
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def resolve_chrome():
    import os
    override = os.environ.get("CHROME")
    if override:
        return {"executable_path": override}
    return {"channel": "chrome"}


def launch_browser(p):
    try:
        return p.chromium.launch(headless=True, **resolve_chrome())
    except Exception:
        return p.chromium.launch(headless=True,
                                 executable_path="/usr/bin/google-chrome")


def capture(url, out_path, width, height, timeout_ms=30000):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = launch_browser(p)
        try:
            page = browser.new_page(viewport={"width": width,
                                              "height": height})
            page.goto(url, timeout=timeout_ms)
            page.wait_for_selector("body[data-ready]",
                                   timeout=timeout_ms)
            page.screenshot(path=str(out_path))
            return page.get_attribute("body", "data-ready")
        finally:
            browser.close()


def compare_shot(reference, shot, out_path, height):
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-v", "error",
         "-i", str(reference), "-i", str(shot),
         "-filter_complex",
         f"[0:v]scale=-1:{height}[ref];[ref][1:v]hstack=inputs=2",
         str(out_path)],
        check=True)


PAGE_PATHS = {"preview": "static/level-preview.html",
              "game": "static/game.html"}


def build_page_url(base_url, page, level):
    return f"{base_url.rstrip('/')}/{PAGE_PATHS[page]}?level={level}"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Capture a level-preview render to screenshots/.")
    parser.add_argument("level")
    parser.add_argument("--url", default="http://127.0.0.1:8321")
    parser.add_argument("--outdir", default=None,
                        help="default: screenshots/, or "
                             "screenshots/features/<feature-id>/ with --feature")
    parser.add_argument("--page", choices=sorted(PAGE_PATHS), default="preview",
                        help="page to capture (default: preview)")
    parser.add_argument("--feature", default=None,
                        help="feature id; files the shot as feature evidence")
    parser.add_argument("--window-size", default="1024x800")
    parser.add_argument("--compare", action="store_true",
                        help="also write a side-by-side with the reference")
    args = parser.parse_args(argv)

    try:
        width, height = (int(v) for v in args.window_size.split("x"))
    except ValueError:
        parser.error("--window-size must look like 1024x800")

    page_url = build_page_url(args.url, args.page, args.level)
    try:
        with urllib.request.urlopen(page_url, timeout=10) as res:
            if res.status != 200:
                raise IOError(f"HTTP {res.status}")
    except Exception as exc:
        print(f"server check failed for {page_url}: {exc}", file=sys.stderr)
        print("Is tools/server.py running?", file=sys.stderr)
        return 1

    if args.outdir:
        outdir = Path(args.outdir)
    elif args.feature:
        outdir = ROOT / "screenshots" / "features" / args.feature
    else:
        outdir = ROOT / "screenshots"
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%d-%H%M%S")
    shot = outdir / f"{args.level}-{stamp}.png"
    latest = outdir / f"{args.level}-latest.png"

    try:
        ready = capture(page_url, shot, width, height)
    except Exception as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1
    if ready != args.level:
        print(f"readiness marker mismatch: want {args.level!r}, "
              f"got {ready!r}", file=sys.stderr)
        return 1
    shutil.copy(shot, latest)
    print(f"wrote {shot}")
    print(f"wrote {latest}")

    if args.compare:
        reference = ROOT / "docs" / "chips-first-level.png"
        comp = outdir / f"{args.level}-compare-{stamp}.png"
        comp_latest = outdir / f"{args.level}-compare-latest.png"
        compare_shot(reference, shot, comp, height)
        shutil.copy(comp, comp_latest)
        print(f"wrote {comp}")
        print(f"wrote {comp_latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
