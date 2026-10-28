---
date: 2026-10-27
---
## Goal

Build a small local UI tool for iterative game-asset design, replacing hand-editing of `assets/manifest.yml` and `assets/judgements.yml`. The tool lets the user add assets (e.g. `floor_default`), create versioned prompts that inherit from a parent version (parent prompt text, parent output image, parent judgement), tweak and run a single generation via the existing `scripts/gen-image` (Muse Image 1.0), visually compare outputs, and record free-text human judgement per output so prompt iterations are captured and reproducible. All image spend must be tracked in Meta Cost Center so the $150 project alert and key kill-switch actually see UI-driven usage.

## Success Criteria

- User can add a new asset with name, width, and height (default 512x512) from the UI; the backend writes it to `assets/manifest.yml`. Users do not hand-edit YAML; the backend generates and manages both YAML files.
- User can create a new prompt version for an asset, optionally picking a parent version; the parent prompt text, parent output image, and parent judgement are carried forward and shown, and the parent prompt preloads the editor for tweaking.
- User can run one single generation from the UI per action; it invokes `scripts/gen-image` once (n=1) with the version's prompt, dimensions, and reference images (including parent output when selected) and stores the output under `assets/outputs/` with the existing naming convention (`<asset>-<slug>-<timestamp>`). There is no batch/manifest-sweep runner and no confirm dialog before Run.
- Every successful generation is tracked in Meta Cost Center: `scripts/gen-image` runs `meta-cost record` exactly once per successful API call with `--model`, `--images` (returned count), explicit `--project`, `--tool gen-image`, a fresh `--id`, and `--key` when the key came from Keyguard. The UI surfaces the per-run estimated cost and any recording warning; a recording failure never fails the generation.
- User can view the generated image next to its prompt and parent image, and record/edit a free-text human judgement that persists to `assets/judgements.yml` keyed by output name. No rating schema and no A/B compare in v1.
- Version run status (`completed`, `failed`) is visible per version/output, so it is clear what generated vs. failed.
- Local single-user use only; no auth, no multi-user support.
- No regression: existing `scripts/gen-image` CLI flags (`--prompt-file`, `--width/--height`, `-o`, `-i` reference) keep working; existing `floor_default` entry and `scratchpad/testgenimage/floor.md` flow still generate.

## Approach

Build a minimal local-only single-user web app with no build step: a small Python backend plus vanilla HTML/JS frontend. The backend is the sole writer for `assets/manifest.yml` and `assets/judgements.yml` (source of truth, backend-managed, never hand-edited) and shells out to `scripts/gen-image` as a subprocess for single runs. No database, no framework-heavy frontend.

- Backend: Python, using only stdlib plus the YAML library already implied by the manifest workflow (use `pyyaml` if present, else add it as the single dependency) and a minimal HTTP layer. Prefer stdlib `http.server` to avoid new deps; use Flask only if stdlib becomes awkward. Endpoints: list/get assets, create asset, create version (with `parent` pointer), trigger a single generation run, save judgement, serve output images statically.
- Frontend: one static page with three panes: asset list, version chain (prompt + judgement + thumbnail per version), and editor (prompt textarea prefilled from parent, dims, reference-image picker, run button, judgement box). Vanilla JS `fetch`, no bundler. No confirm dialog on Run; Run button shows progress state and error on failure.
- Data model: `assets/manifest.yml` holds `assets: {name: {width, height, versions: [{slug, desc, prompt, parent, status, outputs[]}]}}`, migrating the current single-mapping `versions:` for `floor_default/init` into this list on first tool-run. No `queue` field and no batch states (`ready`/`ignore`) since runs are single UI-driven actions. Judgements stay keyed by output name (`<asset>-<slug>-<hash>`) as `assets/judgements.yml` already sketches; judgement value is free text. Additionally store per-run cost (`estimated_usd`, possibly null when unpriced) alongside the output record for display.
- Generation wiring: backend writes the version prompt to a temp prompt-file and calls `scripts/gen-image --prompt-file <tmp> --width <w> --height <h> [-i <parent-output>...] -o assets/outputs/<asset>-<slug>-<timestamp>.png` with n=1, captures exit code/stdout, marks the version `completed` or `failed`, appends the output path to the version record.
- Cost-center integration (do first, inside `scripts/gen-image` per `INTEGRATING-SCRIPTS.md`): add the stdlib-only `record_usage` helper, `META_COST_COMMAND` env override, and a `--no-record` skip flag. Record only after a successful call, with `--images len(response.data)`, explicit `--project` (repo folder name), `--tool gen-image`, new `--id` per call, and `--key jolly-challenge` only when the key came from Keyguard. Recording warns on stderr on missing binary/failure/timeout (30s) and never changes the exit result. Never pass prompts or responses. The backend must use the normal Keyguard key path (never `--api-key`, which loses the key label that revoke-alerts match on) and must not record a second time itself, so each call is counted exactly once. Surface the `estimated_api_equivalent_usd` and any recording warning in the run log.
- Non-goals: unified single-image tileset packing (engine decision comes later per `docs/minimal-graphical-assets.md`); auto-scoring, rating schema, and A/B compare; batch generation from the manifest; auth/multi-user.

## Steps

1. Cost-center integration in `scripts/gen-image`.
   - Copy the `record_usage` helper (stdlib only), wire `META_COST_COMMAND`, add `--no-record`, keep the Keyguard label alongside the loaded key and pass `--key` only for Keyguard keys.
   - Verify with a throwaway DB wrapper before touching real data (see Validation Plan). No changes to image output paths or CLI defaults.
2. Data-model migration and I/O helpers.
   - Define version record: `slug, desc, prompt, parent (slug|null), status (completed|failed), width/height override (optional), outputs[]` where each output carries `path` and `estimated_usd`. No queue field.
   - Write backend-owned load/save helpers for `assets/manifest.yml` and `assets/judgements.yml` with atomic writes (temp file + rename), preserving the existing `floor_default/init` entry. No hand-edit path.
   - Surfaces: new module (e.g. `tools/asset_store.py` next to `scripts/`), plus the `gen-image` edit from step 1.
3. Backend API + static serving.
   - Routes: `GET /api/assets`, `POST /api/assets`, `GET /api/assets/<name>`, `POST /api/assets/<name>/versions`, `POST /api/runs` (single run), `GET /api/runs/<id>`, `PUT /api/judgements/<output-key>`, static `GET /` and `/outputs/*`.
   - Single-run execution with a simple lock (one run at a time) to avoid concurrent keyguard/API races; capture gen-image stdout/stderr, parse the recorded cost, and store the run log per version. Surface key-revoked/limit errors distinctly from generic generation failures.
4. Frontend: asset list + version chain view.
   - Left: asset list with new-asset form (name, width, height). Center/right: version chain showing each version's prompt, status badge, thumbnail, per-run cost, and judgement snippet; click to select parent.
5. Frontend: version editor + single run.
   - New-version form: parent selector (defaults to latest), prefilled prompt textarea, desc field, dims (default from asset), reference-image checkboxes (parent output preselected), Run button with progress state, cost line and error display on failure. No confirm dialog.
6. Frontend: judgement capture.
   - Per-output free-text judgement textarea with save; shows parent judgement alongside for comparison during review. Persists to `assets/judgements.yml`. No ratings, no A/B view.
7. Polish and docs.
   - Empty states, status-badge display, run log view with cost line and a pointer to `meta-cost show`, short README section: how to start (`python tools/server.py`), port, file layout, and how spend is tracked. Seed view from existing `floor_default/init` so first launch is non-empty.

## Validation Plan

- Cost-center integration (highest-risk step): point at a throwaway DB via a `META_COST_COMMAND` wrapper adding `--db /tmp/cost-test.sqlite3`; run one generation; `meta-cost export --period today --project meta-global-ai-hackathon-jolly-challenge` shows one row with the right `model`, `images`, `key_label`, `billing_mode` payg, and `estimated_api_equivalent_usd`. `--no-record` produces no row. Missing `meta-cost` binary still saves the image with exit 0 plus a stderr warning.
- Schema round-trip: load `assets/manifest.yml`, save untouched copy, `diff` shows only the intended `versions:` list migration; existing prompt text from `scratchpad/testgenimage/floor.md` / `floor_default` survives byte-identical.
- Unit check on store helpers: create asset, add child version with parent, set status, write free-text judgement and a cost value; re-load and assert linkage. Run with `python -m py_compile` plus the repo's own test path if one exists for the touched area.
- Manual E2E: start server, add asset `test_tile`, create `v2` from parent `init` with one-word prompt tweak, run single generation, confirm one new PNG appears in `assets/outputs/` and version flips to `completed` with a cost line; write a judgement, restart server, confirm asset/version/judgement/cost persist.
- Regression: `scripts/gen-image --prompt-file scratchpad/testgenimage/floor.md --width 512 --height 512 -o /tmp/smoke.png` still succeeds (or fails only on missing key/network, not on tool changes).
- Edge cases: empty prompt blocked with message; missing parent output (deleted file) warns but still generates from text; failed API call records nothing and marks version `failed` with stderr surfaced; concurrent Run clicks serialized by the lock; retry of `record` with the same `--id` records nothing (no double-count).

## Risks / Open Questions

- Risk: without `meta-cost record`, UI-driven image spend is invisible to Cost Center and does not count toward the $150 monthly alert in `docs/community-tools-to-track-usage.md`, so Keyguard cannot revoke keys at the limit (Keyguard hands out keys but does not observe usage). Mitigated by step 1 plus the export check above; backend must never bypass via `--api-key`.
- Risk: `meta-keyguard` / API key availability and per-image cost (~$0.01/image noted in `scripts/gen-image`) — mitigate with one-at-a-time single runs and a visible run log with cost line.
- Open questions: None.

## Sources

- [INTEGRATING-SCRIPTS.md](https://github.com/omenking/meta-costcenter/blob/main/docs/INTEGRATING-SCRIPTS.md)
