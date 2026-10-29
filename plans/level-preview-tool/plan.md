# Level Preview Tool

## Goal

Build a local HTML tool that renders the `docs/chip-challenge.jpg` layout as a tile grid using the sprites in `assets/published`, so level layouts can be composed and judged visually before any game code exists. The tool must handle two known asset gaps: three sprites ship on green-screen backgrounds that must be keyed out, and the red/blue/green/yellow key and lock color variants do not exist yet.

## Success Criteria

- Opening the preview page shows the 9x9 reference arrangement: portal top-center, gate below it, player center, info tile, 2 blue + 2 red keys, 8 colored locks (2 each of green/blue/red/yellow), 4 chips, walls and floor matching the reference.
- Keyed sprites (Jolly, key, orb, gate) render with transparent backgrounds — no green or white boxes.
- All four key/lock colors are visible on the grid, clearly marked as placeholders where they are hue-shifted stand-ins rather than generated art.
- The layout is editable by editing a JSON file, with no HTML/JS changes needed to move tiles.
- Runs locally with the existing toolchain and no new pip dependencies.

## Approach

Static PixiJS page + JSON level file + an offline sprite-prep step. The reference image is static, so the tool renders a static grid; no game loop, physics, or input beyond preview aids (coordinates, tint toggles).

Key decisions:

1. **Renderer: PixiJS, vendored local build.** PixiJS is the rendering-focused option the user suggested: the fastest, most lightweight 2D library for the web with WebGL and WebGPU renderers, installed via `npm install pixi.js`. A static grid needs rendering only, which is exactly that scope. Phaser (a fast, free, open-source HTML5 game framework with WebGL and Canvas rendering, shipped as a JS library via download, CDN, or npm) is the fuller game framework; it is heavier than a non-interactive preview needs, so it is rejected for this build and revisited if the preview grows into a playable clone. The PixiJS build file is vendored next to the page (download once at build time) so the tool works offline; a CDN script tag is a conditional alternative — no PixiJS CDN URL was verified during planning, so it must be taken from the official docs at build time if preferred.
2. **Key-out: offline ffmpeg pass, not a runtime shader.** `ffmpeg` 4.4.2 is verified present at `/usr/bin/ffmpeg`, and `scripts/gen-image` already shells out to ffmpeg for image post-processing, so this adds zero new dependencies and matches repo practice. Measured corner pixels confirm jolly/key/orb sit on near-`#00FF00` green (e.g. `(0, 253, 1)`, `(0, 254, 32)`, `(0, 253, 4)`), while floor/wall/wall_keyhole/portal have varied full-bleed borders and are copied as-is. `gate.png` has a near-white uniform border (~253-254), so it is keyed on white and verified visually. Offline keying is deterministic and inspectable; a runtime chroma-key shader would pay per-frame cost and hide artifacts.
3. **Missing colors: ffmpeg hue-rotate placeholders + runtime tint toggle.** The single gold `key.png` and single `wall_keyhole.png` cannot cover the red/blue/green/yellow sets required by `docs/minimal-graphical-assets.md` and visible in the reference. The prep step generates placeholder variants by hue rotation; the preview page adds a tint toggle for experimenting with lock/key colors live. Real generated variants come later through the existing asset tool sessions (assumption; see Open Questions).
4. **Shape: static page served by the existing server, no backend change.** `tools/server.py` already serves any file under `tools/static/` via its `/static/*` route, so a new `tools/static/level-preview.html` is live with zero server edits. Fallback serve command is `python -m http.server` from the repo root.
5. **Tests: stdlib unittest following repo convention.** `tools/test_asset_tool.py` runs via `python -m unittest tools.test_asset_tool -v` (no pytest in `.venv`). The sprite-prep step gets one focused unittest in the same layout; the rendered grid itself is verified by manual visual comparison against the reference (a pixels-exact assertion would be brittle against placeholder art).

## Steps

1. **Transcribe the reference grid — `levels/chip1.json` (new file).**
   Encode the 9x9 grid from `docs/chip-challenge.jpg` as rows of single characters plus a `legend` object mapping each character to a sprite role (floor, wall, portal, gate, info, player, chip, key-blue, key-red, lock-green, lock-blue, lock-red, lock-yellow). Data flow: this JSON is the only file an iteration edits; the page loads it with `fetch`. Review the transcription against the reference image cell by cell before building on it.
2. **Sprite prep — `tools/prep_level_sprites.sh` (new), `.gitignore` (one entry), `tools/test_level_sprites.py` (new unittest).**
   The script reads `assets/published/*.png` (never modifies them) and writes derived RGBA sprites to a gitignored build directory served alongside the page (e.g. `tools/static/level-sprites/`, added to `.gitignore`): ffmpeg `colorkey` for the green backgrounds (jolly, key, orb) and the white background (gate), straight copies for the four full-bleed tiles, and `hue`-rotated placeholder variants for the four key and four lock colors. The unittest asserts each output exists, is 512x512 RGBA, has transparent corners where keyed, and that every sprite id referenced by `levels/chip1.json` resolves to a file.
3. **Preview page — `tools/static/level-preview.html` (new, single file) + vendored PixiJS build.**
   Loads the level JSON, renders a floor layer plus an object layer scaled 512px tiles down to 64px display tiles (576px grid plus chrome), draws a coordinate overlay and tile inspector readout, and offers tint toggles for placeholder key/lock colors. Any sprite id missing from the build directory renders as a labeled magenta rect so gaps are loud, never silent.
4. **Serve, review, document.**
   Serve via the existing `python tools/server.py` and review the render against `docs/chip-challenge.jpg`; fix transcription or keying artifacts found. Add a short section to `README.md` (or `docs/`) with the serve command, the page URL, and how to add a level JSON. Non-goals for this build: player movement or rules, an in-browser level editor (JSON hand-edit only), and generating real color-variant art.

## Validation Plan

- Step 1: `python3 -c` JSON parse check plus a cell-by-cell eyeball of the JSON rows against `docs/chip-challenge.jpg`; expected evidence is a 9-row file whose portal/gate/player/key/lock positions match the reference.
- Step 2: `bash tools/prep_level_sprites.sh` then `source .venv/bin/activate && python -m unittest tools.test_level_sprites -v`; expected evidence is all tests passing and RGBA outputs with transparent corners. Regression: `python -m unittest tools.test_asset_tool -v` still passes.
- Step 3: `source .venv/bin/activate && python tools/server.py`, open `/static/level-preview.html`; expected evidence is the full 9x9 grid with transparency, all four key/lock colors present, no magenta fallback rects, and coordinate overlay working.
- Highest-risk check is the Step 3 visual review: gate white-key fringing and hue-placeholder believability can only be judged by eye against the reference, and may send work back to Step 2 parameters.

## Risks / Open Questions

- **Gate key quality:** if the near-white border is a gradient or the sprite touches the edge, `colorkey` may fringe or eat edges; fallback is flood-fill-from-corner removal or a hand mask, decided at the visual review.
- **Placeholder acceptance:** hue-rotated keys/locks may look wrong next to generated art; they are explicitly labeled placeholders and the tint toggle exists to explore alternatives.
- **Transcription drift:** the JSON is hand-transcribed from a JPEG; the Step 1 cell-by-cell review is the mitigation.
- **PixiJS API drift:** pin and vendor one tested PixiJS version; do not float on a CDN latest tag.
- Open question: confirm hue-placeholder colors are acceptable for this build, versus generating the real red/blue/green/yellow key and lock variants now through the existing asset tool (real spend, roughly per-image cost noted in the README). Assumption: placeholders now, real variants later.

## Sources

- https://github.com/pixijs/pixijs
- https://docs.phaser.io/phaser/getting-started/what-is-phaser
- https://docs.phaser.io/phaser/getting-started/installation
