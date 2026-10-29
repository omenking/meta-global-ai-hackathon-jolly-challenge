# Multi-turn Improved UI

## Spike outcome (2026-10-28, step 1 — decided before implementation)

No provider session exists: the OpenAI-compatible images API used by
`scripts/gen-image` (`client.images.generate` / `client.images.edit`, plus
the hand-rolled `edit_images_indexed` POST to `/images/edits`) exposes no
session/conversation/continuation parameter, and `scripts/gen-image` takes
no `--session-id` flag. Implemented the emulation branch: every turn is one
`scripts/gen-image` call, continuity = ordered `-i` references auto-carried
from prior turns of the same session (preferred first, newest first, max
10), recorded verbatim per turn. Turn records keep a `provider_session`
field (always null) so a future provider session id slots in without
changing the UI or publish path.

## Goal

Reorient the Asset Design Tool around multi-turn image sessions instead of single-shot versions. Today every version is a fresh `scripts/gen-image` call: the user overloads one prompt, runs, then hand-builds the next version from the parent prompt plus judgement text (`tools/asset_store.py:build_prompt_draft`, carried by `POST /api/assets/<name>/versions`). New image models (Muse Image 1.0) improve through iteration with context images in a session, so the tool should work the same way: a session holds an ordered thread of turns, each turn keeps provider context, and only the winner is published to the official asset list (same asset name = new published version).

## Success Criteria

- User can create a session for an asset intent (e.g. `default_floor`) and run multiple turns inside it; turn N visibly builds on turns 1..N-1 (same provider session or explicit carried context), not a fresh session per turn.
- Turn composer is a single prompt box for a short delta instruction ("remove the cracks, keep the stone color"), not an overloaded full prompt; the UI shows what context each turn carries (prior turns + selected images).
- Each turn can still output multiple images (lottery N=1..10, default 1 per the lottery-plan follow-up) and each image is viewable, judgable, and publishable.
- Side tray holds uploadable context assets plus existing outputs; every entry has a copy-name button that copies the filename to the clipboard for pasting into the prompt.
- Any generated image can be published with one action into the official asset list; publishing to an existing asset name creates a new published version of that asset, publishing to a new name creates the asset. Published records survive restart and reuse the current `assets/manifest.yml` / `assets/judgements.yml` shapes.
- No regression: existing published versions (`floor_default/init` and children), `GET /api/assets`, single-run lock, Cost Center once-per-call recording, and `scripts/gen-image` CLI flags keep working. Old versions remain viewable read-only.

## Approach

Keep the current stack (stdlib `tools/server.py` + `tools/asset_store.py` + vanilla `tools/static/index.html`, backend-owned YAML, subprocess to `scripts/gen-image`) and add sessions as the primary loop while demoting versions to the publish record.

- Sessions are new backend-owned state, not a manifest migration: new file `assets/sessions.yml` (same atomic temp-file + rename + header-preservation pattern as `tools/asset_store.py:_save_yaml`), keyed by session id, each with `asset_name`, `created`, `turns[]`. Each turn stores `seq`, `prompt` (user delta, verbatim), `full_prompt_sent` (byte-for-byte string passed to `scripts/gen-image`), `references` (ordered list), `num`, `provider_session` (opaque id when the API supports it, else null), `outputs[]` (same output shape as version outputs today), `status`, `cost`.
- `scripts/gen-image` gains optional session plumbing (`--session-id` in/out or equivalent, decided by the spike); when the provider has no session concept, the backend emulates continuity by auto-carrying session context as ordered `-i` references (prior turn winner + explicitly ticked images, capped at 10) and records that emulation in `full_prompt_sent` + `references` so runs stay reproducible.
- Publish is a thin mapping, not a new storage system: `POST /api/sessions/<id>/publish {output_key, asset_name}` calls existing `create_asset` / `add_version` in `tools/asset_store.py` (prompt = turn's full prompt, references = `[output_key]`, parent = latest published version of that asset for a linear published history) and copies the judgement via existing `save_judgement`. Versions are thereafter only created by publish; the New Version form leaves the main flow (kept for back-compat, hidden or read-only).
- Frontend gets a session workspace view alongside the existing asset/version panes: session list per asset, center turn thread (oldest at top, newest at bottom), bottom composer, side context tray. Publish buttons live on each image; published assets render exactly as today.

## Key Decisions

- Sessions in a new `assets/sessions.yml`, not nested into `assets/manifest.yml`: avoids migrating every existing version record and keeps the publish path (which writes `manifest.yml`) independent from the iteration path (which writes `sessions.yml`). Rejected alternative (sessions nested under `assets[name]`) because it bloats the published file with ephemeral turns and complicates the "publish = new version" mapping.
- Versions become publish-only output, not deleted: existing `floor_default` history and `tools/test_asset_tool.py` expectations keep passing; the UI stops offering version-first creation as the main loop but still renders published versions. Rejected alternative (delete versions outright) because it orphans judgements keyed by output key and breaks the seed view.
- True provider session when available, ordered-reference emulation otherwise: the spike (step 1) decides which `scripts/gen-image` implements, but both write identical turn records so the UI and publish path do not branch. The run path never silently merges prompts server-side; the composer text plus carried context is the full record.
- Uploads via base64 JSON (`POST /api/uploads {filename, data_b64}`), not multipart: `tools/server.py` currently only parses JSON bodies (`_read_json`), so base64 stays in the existing handler; files land under `assets/outputs/uploads-<stamp>-<name>` (or `assets/context/` if step 2 prefers separation) and are referenceable exactly like generated outputs. Size cap (~8 MB) and image-type check enforced server-side.
- Same-name publish = new version, never overwrite: publish to an existing asset appends a version with `parent` = latest published slug (slug derived from session/turn, e.g. `s<session>-t<seq>`); there is no in-place replacement of a published image. Copy button uses `navigator.clipboard.writeText` with a textarea fallback.

## Steps

1. Spike: determine the Muse Image 1.0 session mechanism (half day, no UI).
   - Inspect `scripts/gen-image` generate vs `edit_images_indexed` paths and the provider's images API for a session/conversation/continuation parameter; record the exact parameter name, lifetime, and whether reference images are still required alongside it.
   - Outcome is a 10-line note at the top of this plan: either "provider session id X, passed as flag Y, survives N turns" or "no provider session; emulate with ordered refs". Steps 3-4 implement whichever won; turn record shape covers both.
2. Session store + upload plumbing (`tools/asset_store.py`, new session helpers, `assets/sessions.yml`).
   - Helpers mirroring existing style: `create_session(sessions, asset_name)`, `add_turn(...)`, `record_turn_outputs(...)`, `get_session(...)`, plus `save_sessions`/`load_sessions` with atomic writes. Validation reuses `NAME_RE`, `validate_references` (10-cap), `lottery_keys` naming.
   - Upload helper: validate extension/MIME/size, write file, return servable name. Surfaces: `tools/asset_store.py`, new `assets/sessions.yml`.
3. Generation path with session context (`scripts/gen-image`, `tools/server.py:_run_generation` sibling `_run_turn`).
   - `scripts/gen-image`: add session in/out flags per spike outcome; print the session id to stdout in a parseable `session=<id>` line (same pattern as existing `saved original ...` / `requested=...` lines the server already parses); keep all existing flags and `--num 1-10` behavior.
   - Server: `POST /api/sessions`, `GET /api/sessions?asset=<name>`, `GET /api/sessions/<id>`, `POST /api/sessions/<id>/turns` (body: `prompt`, `num`, `references` override or null = auto-carry session context). Reuse `RUN_LOCK`, timeout, cost-parse (`COST_RE`), per-output cost split, `mark_failed` semantics. Auto-carry rule: explicit list (possibly empty) wins; null carries winner/preferred + prior turn outputs newest-first up to 10.
4. Publish endpoint (small, reuses store).
   - `POST /api/sessions/<id>/publish {output_key, asset_name}`: look up output across turns + uploads, `create_asset` when missing else `add_version` with parent = latest published slug, `record_output`-equivalent link (or move reference to the published version's outputs), carry judgement. 404 on unknown session/output, 400 via `StoreError` like siblings. Surfaces: `tools/server.py` `do_POST`, `tools/asset_store.py` reuse.
5. Frontend: session workspace (`tools/static/index.html` only).
   - Session list per selected asset + "New session" button; center thread rendering each turn (delta prompt, context chips, N-grid thumbnails via existing `toServedUrl` helper, cost line, judgement boxes reusing `PUT /api/judgements/<key>`); bottom composer (prompt textarea, N input, ref picker grouped as session-winner / this-session outputs / uploads with live `k/10` count, Run button with progress state).
   - Side tray: uploads (file input + POST) and published-asset outputs, each with copy-name button and thumbnail; published versions pane kept read-only below or behind a tab.
   - Per-image Publish button (asset-name defaults to session target, editable inline) calling step 4, then `refresh`; session view persists selection across refresh.
6. Tests, migration safety, docs.
   - Extend `tools/test_asset_tool.py`: session create/add-turn/publish mapping, auto-carry cap, same-name publish appends version, upload validation, noop-guard equivalent for empty-delta first turn (allowed: first turn is text-only by definition).
   - Round-trip: existing `assets/manifest.yml` untouched except via publish; `diff` after session-only activity shows no manifest change. Docs: short README section (sessions vs published assets, auto-carry rule, copy-button flow, publish semantics).

## Validation Plan

- Spike note reviewed before steps 3-5 begin (highest-risk decision); if provider sessions do not exist, steps 3-5 proceed on the emulation branch with no plan rewrite.
- Unit: `python -m unittest tools.test_asset_tool -v` — new session/publish/carry tests plus existing judgement + noop-guard tests green; `python3 -m py_compile tools/server.py tools/asset_store.py`.
- Mock multi-turn (no API spend): stub `scripts/gen-image` with a temp executable printing `session=<fixed>` and writing N PNGs; `POST /api/sessions/<id>/turns` twice yields turn 1 + turn 2 with identical `provider_session`, N files each, per-output cost = total/N, single lock respected (concurrent turns 409).
- Manual E2E: start `python tools/server.py`, new session for `default_floor`, turn 1 text-only N=2, judge, turn 2 with winner auto-carried + short delta prompt, publish winner to `default_floor` → new published version appears, restart server, session thread + published version persist; copy button pastes a filename into the composer.
- Regression: `GET /api/assets` still returns `floor_default/init` chain; N=1 turn matches today's single-run output naming (no `-i` suffix change); `scripts/gen-image --prompt-file scratchpad/testgenimage/floor.md --width 512 --height 512 -o /tmp/smoke.png` still works.
- Edge cases: empty turn prompt blocked with message; >10 refs 400 both client- and server-side; deleted ref 400 before spend; publish of unknown output key 404; oversized/non-image upload rejected with message.

## Risks / Open Questions

- Risk: provider may not offer true sessions (search shows no session handling in `scripts/` or `tools/` today) — mitigated by the spike-first order and the emulation branch, which still delivers the user-visible improvement (short delta prompts + auto-carried context + publish flow).
Anwser: It uses the Responses API, it can defiently hadnle conitous context.
- Risk: turn history growth (10 outputs/turn x many turns) bloats `assets/sessions.yml` and the thread view — acceptable for local single-user use; mitigation is newest-first thumbnails plus no pagination in v1, same call made for lottery outputs before.
Don't care.
- Risk: publish slug collisions across sessions (`s<session>-t<seq>`) — mitigated by deriving uniqueness from timestamp/key like `lottery_keys` does today.
sure
- Risk: uploads abused as large-file drop — mitigated by server-side size cap and image-type check.
sure, or you simply use ffmpeg and downsize to reasonable size. This is only ever running locally so we shouldn't be super concerned.
- Open questions: None — defaults assumed reversible: N default 1 for turns (lottery follow-up set it), auto-carry = winner + newest-first up to 10, same-name publish always appends a version.
