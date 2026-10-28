---
date: 2026-10-27
---

## Fix Gen Image Script

## Goal

Fix `scripts/gen-image` so a requested `--width/--height` (e.g. 512x512) produces a
game-ready file at exactly that size, while preserving the raw generator output,
and carry both files through the Iterative Asset Design Tool (`tools/server.py` +
`tools/asset_store.py`). Clarify what Muse Image 1.0 `size` actually controls so
the `--width/--height` vs `--ratio` flexibility is explicit.

## Context (verified this session)

- Reported symptom (Claude): PNG is 1600x1600 although `--width 512 --height 512`
  was requested and the summary line says `size=512x512`. Reproduced locally:
  `scratchpad/testgenimage/default.png` is `1600 x 1600, 8-bit/color RGB` (`file`
  + PIL both agree).
- Root cause is API semantics, **not** a pass-through bug. `scripts/gen-image`
  correctly builds `args.size = "512x512"` (`parse_args`, `size` precedence:
  `--size` > `--width/--height` > `--ratio` > default `1024x1024`) and passes
  `size=args.size` to both `client.images.generate` and `client.images.edit`.
- Authoritative docs confirm: `size` is a `"WxH"` string "that sets the aspect
  ratio, not the exact pixel size: the image is produced at the generator's own
  resolution" — so `512x512`, `1024x1024`, and `--ratio square` all mean "square",
  and the raw file can come back at 1600x1600. Omit/`auto` = default aspect.
  Aspect ratios beyond 16:1 return `400 (param: size)`.
- Full argument surface of `scripts/gen-image` today: positional prompt /
  `--prompt` / `--prompt-file`, `-o/--output`, `--size`, `--width` + `--height`
  (paired), `--ratio` (keys in `RATIO_TO_SIZE`: `1:1, square, 16:9, wide, 9:16,
  tall, 3:2, 2:3, 4:3, 3:4`), `-i/--image/--reference` (repeatable edit refs),
  `--model` (default `muse-image-1.0`), `-n/--num` 1-10, `--output-format`
  (png/jpeg/webp), `--key-label`, `--api-key`, `--base-url`, `--no-record`.
  API-side per call: `model, prompt, size, n, response_format=b64_json,
  output_format, image (edit only)`. `moderation` must stay omitted on
  `muse-image-1.0` (any value returns 400). Billing is per image, so raw size
  does not change cost.
- Toolchain available with zero new pip deps: `ffmpeg` 4.4.2 at `/usr/bin/ffmpeg`;
  `requirements.txt` pins only `openai==3.40.0` + `pyyaml==6.0.3` (Pillow 12.3.0
  happens to be installed but is **not** a declared dep).
- Downstream contract: `tools/server.py::_run_generation` shells out to
  `scripts/gen-image --prompt-file <tmp> --width <w> --height <h> -o
  assets/outputs/<asset>-<slug>-<timestamp>.png` (n=1) and `asset_store.record_output`
  stores one record `{key, path, estimated_usd}` per output; judgement is keyed by
  output key. Any two-file scheme must extend this record compatibly.

## Success Criteria

- `scripts/gen-image --width 512 --height 512 --prompt-file
  scratchpad/testgenimage/floor.md -o <out>.png` leaves `<out>.png` at exactly
  512x512 (all three `--output-format` values) **and** preserves the raw
  generator bytes alongside it (default: `<stem>-orig<suffix>`, e.g.
  `default-orig.png`; never overwrites an existing file — index if needed).
- Summary line tells the truth: requested size, actual raw dimensions, final
  resized dimensions (e.g. `size requested=512x512, raw=1600x1600, saved=512x512`).
- Existing CLI flags keep working; `--width` without `--height` (and vice versa)
  still errors; `--size` precedence note unchanged; cost-center `record_usage`
  behavior untouched (records once per successful call, warns-only on failure).
- Server flow stores and serves **both** files: manifest output record gains
  `original_path` (plus `requested_width/height`, `raw_width/height`) while old
  `{key, path, estimated_usd}` records still load; UI shows the game-size image
  by default with the original reachable (link/toggle); judgement keying by output
  key is unchanged.
- Docs: `--help` + plan state that `size`/`--ratio` are aspect carriers and
  `--width/--height` is the exact post-resize game size.

## Approach

Do the resize **inside `scripts/gen-image`** (not in the server), so the CLI
scratchpad flow and the UI flow are fixed by one change. Use `ffmpeg` via
subprocess (already on PATH, no new pip dep) with a `--no-resize` escape hatch
and a `--keep-original` / naming override. Keep the resize exact (`scale=W:H`)
since game tiles need exact dims; log a stderr warning when the raw aspect
differs from the requested aspect beyond ~2% so stretched non-standard sizes are
visible, but still write the exact size (documented policy).

- Naming: requested `-o out.png` → game-ready `out.png` + raw `out-orig.png`
  (same dir, same suffix; `-n/--num > 1` applies per indexed file:
  `<stem>-<N>.png` + `<stem>-<N>-orig.png`). Add `--keep-original PATH|off`:
  default = alongside-output `-orig` file; `off` (or `--no-keep-original`) skips
  preservation for throwaway runs. Never clobber: if the `-orig` name exists,
  append `-2`, `-3`, ….
- Resizing placement: after `save_images` writes raw bytes, probe raw dims
  (`ffprobe` if present, else parse PNG/JPEG/WEBP header in stdlib — no Pillow
  dep), copy raw → `-orig` path, then `ffmpeg -y -i orig -vf "scale=W:H:lanczos"`
  → final path. On any resize failure: keep the raw at the requested `-o` path,
  warn on stderr, exit 0 (image is saved; resize is best-effort, never a
  generation failure). `--output-format` flows into both files.
- Honest logging: replace/augment the `done (...)` line with
  `requested=WxH, raw=WxH, saved=WxH (+ original <path>)`. Keep the existing
  `saved <path>` per-file lines, plus one `saved original <path>` line.
- Server/store: extend `record_output` output dict with `original_path`,
  `requested_width/height`, `raw_width/height` (all optional/None-tolerant);
  `_run_generation` derives the `-orig` name from the same rule (or parses it
  from gen-image stdout) and serves `/outputs/*` unchanged (static handler
  already serves any file under `assets/outputs/`). Frontend: thumbnail/src =
  game-size `path`; add "original (1600x1600)" link per output. Migration: old
  records without the new keys render with original link hidden.

## Steps

1. `scripts/gen-image`: add `--no-resize` and `--keep-original` args; implement
   `probe_dims()` (ffprobe → stdlib header fallback) + `resize_to()` (ffmpeg
   lanczos scale) + `-orig` naming helper with no-clobber indexing.
   Wire into `main` after `save_images`, before `record_usage`; update summary
   line and `--help`/docstring (`size` = aspect carrier, `--width/--height` =
   exact final size). Keep surfaces: backend team owns `tools/` changes.
2. `tools/asset_store.py`: extend `record_output` + `_normalize_version` to
   carry `original_path`, `requested_width/height`, `raw_width/height`
   (default None); old records load unchanged.
3. `tools/server.py`: capture both paths from the gen-image run, pass to
   `record_output`, include in `RUNS` record + `_asset_view`; no change to the
   single-run lock, timeout, cost regex, or judgement endpoints.
4. Frontend (`tools/static/index.html`): show game-size image; add per-output
   original link with dims label; show `requested / raw / saved` line in run log.
5. Docs: one README/plan paragraph — Meta `size` = aspect only; `--ratio` table
   stays as aspect shortcuts; arbitrary `--width/--height` honored exactly via
   local resize; billing per image regardless of pixels.

## Validation Plan

- CLI single: `scripts/gen-image --width 512 --height 512 --prompt-file
  scratchpad/testgenimage/floor.md -o /tmp/fix-check.png` → `/tmp/fix-check.png`
  is 512x512, `/tmp/fix-check-orig.png` is raw (1600x1600), summary line shows
  `requested=512x512, raw=1600x1600, saved=512x512`. Repeat with
  `--output-format jpeg` and `--ratio 16:9` (+ matching `--width/--height`
  aspect) to check carriers + formats. `--no-resize` leaves raw at `-o` with no
  `-orig`; `--keep-original off` same.
- Regression: existing flags (`--prompt-file`, `-o`, `-i`, `-n 2` indexed +
  double `-orig` files, `--width` without `--height` errors, `--size` precedence
  note) behave as before; `meta-cost` recording unchanged (one row per success,
  `--no-record` writes none, missing binary warns with exit 0).
- Store round-trip: old `floor_default/init` record (no new keys) loads; new
  record with both paths + dims saves/loads byte-stable; judgement keyed by
  output key still resolves.
- E2E (server): create version, run once, confirm two PNGs in `assets/outputs/`,
  version `completed` with cost line, thumbnail = 512px file, original link
  serves raw; restart server, both persist.

## Risks / Open Questions

- Risk: non-standard aspect requests get exact-stretched (documented) — game-tile
  exactness wins over photographic purity; the aspect-mismatch warning makes it
  visible. Alternative (letterbox/crop) rejected: adds game-engine ambiguity.
- Risk: `ffmpeg` missing on a dev box → fallback is warn + leave raw at `-o`
  (same policy as resize failure); `ffprobe` missing → stdlib header probe covers
  PNG/JPEG/WebP.
We'll just install our ourselves, we just need to make note of it.
- Risk: 16:1+ aspect requests still 400 from the API — surface stderr unchanged,
  mark version `failed`, record nothing (existing contract).
- Open questions: None — Pillow intentionally not added (undeclared dep); ffmpeg
  keeps `requirements.txt` untouched.
We should now have ffmpeg isntalled I installed it, requirement.txt should be updated.

## Sources

- [Image generation with Muse Image](https://dev.meta.ai/docs/image-generation)
