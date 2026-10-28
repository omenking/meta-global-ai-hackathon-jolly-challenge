---
date: 2026-10-27
status: enriched implementation plan (issues verified against coded app)
source-issues: plans/asset-design-tool/inital-ui-issues-after.md (this file)
app-reviewed:
  - tools/static/index.html
  - tools/server.py
  - tools/asset_store.py
  - assets/manifest.yml
---

## Goal

Fix the three UI issue groups from the first Asset Design Tool build: (1) New-asset form is inline instead of a header popup, (2) version images have no working preview, (3) the version editor is cramped, inline-only, and has no New/Edit entry points. All fixes are frontend in `tools/static/index.html` plus one small backend edit endpoint; no changes to `scripts/gen-image`, cost-center recording, or the stored data shape.

## Verification (each reported issue confirmed, with root cause)

| # | Reported issue | Verdict | Evidence / root cause |
|---|---|---|---|
| 1 | New-asset form is inline; want a "New asset" button right-aligned in main header opening a popup that does not close on offclick | CONFIRMED | `tools/static/index.html:55-58` header has title + summary only, no button. `tools/static/index.html:60-70` renders the form inline in the Assets pane (`new-name`, `new-w`, `new-h`, `add-asset`). |
| 2 | Versions show no image preview; original link visible but broken; resized image not visible; want auto preview best-fit to version box | CONFIRMED, root cause is deeper than reported: both URLs 404 | `tools/static/index.html:179-188` renders `<img src="/assets/outputs/...">` and `<a href="/assets/outputs/...">` by prefixing stored paths with `/`. Stored paths are `assets/outputs/<key>.png` (`assets/manifest.yml:28-30`, written by `tools/server.py:178-183`). `tools/server.py:236-251` only serves images under `/outputs/*`; `/assets/outputs/*` falls through to 404 JSON. So the resized `<img>` is a broken image and the original link is a broken link. Secondary: `.thumb` (`tools/static/index.html:30`) has `max-width:100%` only, no best-fit height/object-fit rule; run-result block (`tools/static/index.html:304-335`) shows saved-path text only, no thumbnail. Real files exist: `assets/outputs/floor_default-init-20261027-151142.png` (212 KB resized) and `...-orig.png` (2 MB raw). |
| 3a | Description cramped; want it on its own line as textarea | CONFIRMED | `tools/static/index.html:82-85` puts slug + description side-by-side in one `.row`, description is `<input type=text id="ed-desc">`. |
| 3b | Judgement box strange; want it on its own line | CONFIRMED | `tools/static/index.html:98-105` uses a 2-column `.judge-grid` (`tools/static/index.html:51`) with parent judgement and the textarea squeezed side-by-side. |
| 3c | Want version editing in popup, not inline; no Edit button; no New button | CONFIRMED | Editor is always inline in the third pane (`tools/static/index.html:75-108`). Clicking a version card only selects it as parent (`tools/static/index.html:195-197`); `ed-parent.onchange` overwrites the prompt (`tools/static/index.html:263-268`). Only action is `Save new version` (`tools/static/index.html:283-302`); no New/Edit buttons exist. Backend has `POST /api/assets/<name>/versions` (`tools/server.py:284-295`) backed by `add_version` (`tools/asset_store.py:189-217`) but no update endpoint, so true editing currently has no API. |

## Success Criteria

- Header has a right-aligned "New asset" button; clicking opens a modal that closes only via explicit Cancel/X/Create (backdrop offclick does nothing and ESC does not close — see Key Decisions); creating an asset through it behaves exactly like the current inline form (same POST, same validation messages).
- Each version card with outputs shows the resized image automatically (no click needed), contained to the card width with a capped height so tall/wide images best-fit without stretching or breaking layout; the raw original remains a small working link (opens in new tab) with its dimensions label.
- Version create/edit happens in a modal, not the inline third pane: description is a full-width textarea on its own line; parent judgement (readonly) and this-output judgement (editable) are stacked full-width on their own lines; Versions pane has a "New version" button and each card has an "Edit" button (card-body click still selects parent; button clicks do not bubble).
- Editing a version updates desc/prompt/dims via a new PUT endpoint and survives server restart (round-trips through `assets/manifest.yml`); slug and parent are immutable in edit mode.
- No regression: asset list, parent selector preload, reference picker, single-run lock, cost line, judgement save, and `floor_default/init` seed view all keep working.

## Approach

Single static page stays vanilla HTML/JS with no build step; add two CSS-only-dependency modals (new-asset, version editor) in `tools/static/index.html`. Fix images with a frontend-only URL helper (no manifest migration: map stored `assets/outputs/<f>` to served `/outputs/<f>`) plus a best-fit `.thumb` rule. Add one backend endpoint `PUT /api/assets/<name>/versions/<slug>` plus `update_version()` in `tools/asset_store.py` reusing `add_version` validation. Keep modal dismissal strict per the request (explicit buttons only).

## Key Decisions

- URL fix on the frontend, not via manifest migration or a new `/assets/outputs/*` route: stored `assets/outputs/...` values stay as-is (backend-owned files), a `toServedUrl()` helper strips the prefix; keeps the diff to one file and old + new records work. Rejected alternative (server alias route) only to avoid touching the backend static handler for a display bug.
- One version modal for both New and Edit (title + slug-disabled state differ) instead of two modals: less duplicated markup, one set of field-stacking CSS.
- Slug and parent immutable when editing: slug keys outputs/judgements (`assets/judgements.yml` keyed by output key; version slug in output key prefix), so renaming would orphan records. Desc, prompt, width/height overrides are editable.
- Run and Judgement blocks move inside the version modal and stack vertically (Run, then Judgement), preserving existing element IDs and handlers so `renderRunBlock`/`renderJudgeBlock` logic is reused; the inline third pane becomes a read-only hint/selection summary plus `#status`.
- Both modals share the strict-dismiss rule (no backdrop-offclick close; explicit Cancel/X/Create/Save only). ESC behavior: assume ESC does not close either (consistent with "should not close on offclick" intent); state it in the modal hint text. If the user wants ESC-to-close later, it is a one-line change.

## Steps

1. New-asset modal in header.
   - Surface: `tools/static/index.html:55-58` header (flex row, button right), remove inline form `tools/static/index.html:63-69`, add `<div class="modal-backdrop">` + dialog with name/width/height inputs reusing IDs or rewired `add-asset` handler (`tools/static/index.html:270-281`).
   - Behavior: open on button; close only on Cancel/X/Create-success; backdrop click is ignored (do not attach a close handler; stop propagation); focus name field on open; Enter submits; error text stays inside modal, success closes + `refresh(true)`.
2. Fix version image preview + best-fit sizing.
   - Surface: `tools/static/index.html:168-201` `renderVersions()`, `tools/static/index.html:30` `.thumb`, `tools/static/index.html:304-335` run-result.
   - Add `toServedUrl(stored)` mapping `assets/outputs/f` → `/outputs/f` (passthrough for already-correct `/outputs/...`); use for both `<img src>` and original `<a href>` (add `target="_blank" rel="noopener"`).
   - CSS: `.ver .thumb { width:100%; max-height:240px; object-fit:contain; background:#f0f0f0; display:block; }` so the preview best-fits the card without distortion; keep original link + cost + judgement lines below the image in current order.
   - Add a thumbnail to the run-result success block using the returned `rec.path` through the same helper.
3. Version editor modal (New + Edit) with stacked fields.
   - Surface: `tools/static/index.html:71-108` editor pane; add "New version" button above `#versions` and per-card "Edit" button (with `stopPropagation`).
   - Modal fields, each full-width on its own line: parent select (disabled in Edit), slug (disabled in Edit), description `<textarea rows=2>`, prompt `<textarea>` (existing `ed-prompt`), width/height override row (keep side-by-side; only genuine row), then Run block, then parent-judgement readonly block, then this-output judgement textarea — each on its own line (delete `.judge-grid` two-column use here).
   - Wire: New clears slug/desc/prompt (or preloads prompt from selected parent), Edit preloads the card's values; both reuse `make-version` POST for New.
4. Backend edit endpoint + store helper.
   - Surface: `tools/asset_store.py` (new `update_version(assets, asset_name, slug, desc, prompt, width, height)` reusing the prompt non-empty and positive-int override checks from `add_version`), `tools/server.py` `do_PUT` (new `PUT /api/assets/<name>/versions/<slug>`, 404 on unknown asset/version, 400 via `StoreError` like siblings).
   - Frontend Edit save calls PUT, then `refresh(true)`; status line confirms.
5. Cleanup + empty states.
   - Third pane becomes selection summary (selected asset/version slugs) + `#status`; remove dead inline-editor markup/IDs only after modal reuse is confirmed; keep `floor_default/init` rendering unchanged.

## Validation Plan

- Static: `python3 -m py_compile tools/server.py tools/asset_store.py`; hard-refresh page, no console errors.
- URL regression (no image spend): `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8321/outputs/floor_default-init-20261027-151142.png` → 200; `curl -s http://127.0.0.1:8321/assets/outputs/floor_default-init-20261027-151142.png` → 404 (proves old prefix was the bug); after fix, version card shows the floor tile without clicking and the original link downloads the 1600×1600 raw.
- New-asset modal: open via header button, backdrop click does nothing, Cancel/X close without creating, valid submit creates asset and closes; invalid name surfaces backend message in-modal.
- Version modal: "New version" opens cleared/prefilled form; card "Edit" opens prefilled with slug disabled; description textarea and stacked judgement boxes render full-width; PUT edit persists across `refresh`/server restart (`grep <slug> assets/manifest.yml`); card click (not on Edit) still selects parent.
- Highest-risk check: image-URL helper — every stored `path`/`original_path` in `assets/manifest.yml` resolves after mapping; no record requires migration.
- Existing flows untouched: parent prompt preload, reference checkboxes, single-run lock (`POST /api/runs` 409 while running), cost line, judgement save to `assets/judgements.yml`.

## Risks / Open Questions

- Risk: very large raw originals (2 MB, 1600×1600) if ever previewed inline — mitigated by previewing only the resized output; original stays a link.
Yes should the resize and have a link to original, open in a new tab in browser to review.

- Risk: `PUT` validation drift from `POST` — mitigated by sharing checks in one helper.
No idea what this issue is.
- Assumption (reversible): ESC does not close modals, matching the no-offclick rule; one-line change if the user prefers ESC-to-close.
Dont need to pres ECS, this is not fancy app. I just want a close button in the top right concern.
- Assumption: 240 px preview cap is a starting value; adjust if version cards feel too tall/short.
Sure maybe 300px please.
- Open questions: None — all three reported groups were verifiable locally without user input.
No idea idea what this means.