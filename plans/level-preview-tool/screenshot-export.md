# Screenshot Export for Level Preview

## Goal

Give the level-preview tool a way to export the rendered level as a PNG image into a `screenshots/` folder, so an agent (or human) can vision-review the render against `docs/chip-challenge.jpg` and iterate. The primary path must be runnable from the shell with no manual browser interaction.

## Success Criteria

- `bash tools/capture_level.sh chip1` writes `screenshots/chip1-<UTC stamp>.png` plus a stable `screenshots/chip1-latest.png` showing the fully rendered 9x9 board.
- A `--compare` flag also writes a side-by-side composite of the capture with the reference image.
- The preview page gains an "Export board PNG" button that downloads the board canvas.
- `screenshots/` is gitignored; the work adds no new pip dependencies.

## Approach

Two complementary paths: a headless-Chrome capture script (agent-runnable, writes directly to `screenshots/`) and an in-page export button (human convenience, downloads via the browser).

Key decisions:

1. **Capture via headless Chrome CLI flags, no new tools.** `google-chrome` 155 is verified present at `/usr/bin/google-chrome`, so capture needs zero installs. The official headless CLI reference grounds the mechanism: `--screenshot` captures the target page (usefully combined with `--window-size`), `--timeout` bounds the wait before capture, `--virtual-time-budget` fast-forwards time-dependent page code, and `--dump-dom` returns the DOM after scripts execute. The script runs Chrome with its working directory set to a scratch dir and moves `screenshot.png` into place, which avoids depending on any `--screenshot=path` form. Render completion is proven two ways: the page sets a `data-ready` marker only after the full board render, and validation greps for it via `--dump-dom` as well as vision-reading the PNG.
2. **In-page export via canvas `toBlob`.** `HTMLCanvasElement.toBlob()` creates a Blob of the canvas image (PNG by default), which the button downloads as `<level>-board.png`. Stated limitation: a browser download cannot land in the repo's `screenshots/` folder, so this path serves humans; the script in (1) is the agent path.
3. **Folder and naming: `screenshots/` at repo root, gitignored.** Matches the existing generated-artifact precedent (`assets/outputs/` in `.gitignore`). Each capture writes a timestamped file for history plus a `-latest.png` stable copy so the vision loop always has a fixed path to read.
4. **Compare composite via ffmpeg `hstack`.** ffmpeg is already a verified repo toolchain dependency (`scripts/gen-image` shells out to it). The `--compare` output stacks the capture against the 864x864 reference (scaled to common height) for one-glance review.
5. **Tests: one E2E unittest, skipped honestly without Chrome.** `tools/test_level_capture.py` spawns `tools/server.py` on an ephemeral port, runs the capture script against it, and asserts the PNG exists with sane dimensions (via ffprobe) and the readiness marker is present. It skips via `skipUnless` when `google-chrome` is absent. Pixel-exact assertions are rejected as too brittle across renders and fonts.

Rejected: a Playwright-driven capture (python-playwright happens to be installed, but scripted-browser control is heavier than CLI flags for a static shot; kept as a conditional fallback if virtual-time timing proves flaky) and a PIL server-side composite as the screenshot itself (it would verify layout math, not the actual page render).

## Steps

1. **Page: readiness marker + export button — edit `tools/static/level-preview.html`.**
   After the board render loop completes, set `document.body.dataset.ready` and a `ready:<level>` title suffix; add an "Export board PNG" button to the panel that downloads the board canvas via `toBlob`. No visual redesign. Data flow unchanged otherwise.
2. **Capture script — new `tools/capture_level.sh`, one `.gitignore` entry.**
   Usage: `tools/capture_level.sh [--url ...] [--compare] <level>`. Resolves Chrome (`google-chrome` with `google-chrome-stable` fallback, honoring a `CHROME` override), captures at ~1024x800 (board plus panel; exact size at implementation), writes timestamped + `-latest.png` files to `screenshots/`, and with `--compare` produces the ffmpeg side-by-side. Fails loudly if the server URL is unreachable or the readiness marker is missing from `--dump-dom`.
3. **E2E test — new `tools/test_level_capture.py` (stdlib unittest, repo convention).**
   Spawns the server on a free port, captures `chip1`, asserts outputs exist, are valid PNGs of matching window size, and contain the readiness marker; cleans up its server process and writes captures to a temp dir (never the real `screenshots/`).
4. **First capture + vision review loop.**
   Run the script for `chip1`, vision-read `screenshots/chip1-latest.png` against `docs/chip-challenge.jpg`, and fix any transcription, keying, or render issues found (one loop inside execution; further iteration is normal follow-up work, not scope creep).
5. **Document — short README paragraph.**
   Capture command, output naming, `--compare`, and the in-page button. Non-goals: committed golden screenshots, automated pixel diffing with thresholds, and video/GIF capture.

## Validation Plan

- Step 1: extract the inline script and `node --check` it (existing method); then `google-chrome --headless --dump-dom <preview-url> | grep data-ready` proves the render path executes end to end in headless Chrome.
- Step 2: `bash tools/capture_level.sh chip1` (server running) then `ls screenshots/` and `ffprobe` dims; `--compare` variant produces the composite. Expected evidence: timestamped PNG, `-latest.png`, composite, all non-trivial byte sizes.
- Step 3: `python3 -m unittest tools.test_level_capture -v` passes with Chrome present; regression `python3 -m unittest tools.test_level_sprites tools.test_asset_tool` still green.
- Step 4: agent vision-read of `-latest.png` vs the reference, with findings recorded and fixed or filed.
- Highest-risk check is the Step 4 vision read combined with Step 1's `--dump-dom` marker: headless WebGL rendering and async texture timing are the only parts that cannot be proven until Chrome actually renders the page.

## Risks / Open Questions

- **Headless WebGL:** if the board canvas comes out blank, the fix is headless GL flags (verified via local `google-chrome --help` at implementation) or the conditional Playwright fallback; the `--dump-dom` marker distinguishes "page didn't render" from "screenshot timing" failures.
- **Async timing:** `--timeout` plus `--virtual-time-budget` cover fetch/texture latency; if captures flake, the fallback is a readiness-polling driver instead of fixed budgets.
- **Screenshots stay out of git** by design (generated artifacts); if golden-file review is ever wanted, that is a separate decision.
- Open questions: None. Assumption: gitignored `screenshots/` (dump folder) is what "dump into a screenshots folder" means, not committed goldens.
gitgnore for now.
## Sources

- https://developer.chrome.com/docs/automation-and-testing/headless-cli
- https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob
