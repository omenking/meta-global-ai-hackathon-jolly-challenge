---
date: 2026-10-27
status: enriched implementation plan (issues verified against coded app)
source-notes: plans/asset-design-tool/second-fixes.md (this file)
app-reviewed:
  - tools/static/index.html
  - tools/server.py
  - tools/asset_store.py
---

## Goal

Second UI pass over the Asset Design Tool: (1) reclaim horizontal space — version cards become horizontal flex rows with the image right of the info, and the low-value Selection column goes away; (2) make images visible where decisions happen — parent preview inside the version modal and thumbnails in the reference picker — and replace the New-asset popup with a full-size form backed by real routing; (3) show newest versions first in a compact list with small thumbnails, hover-to-zoom, and click-through to the original. No changes to `scripts/gen-image`, cost-center recording, or the stored data shape.

## Verification (each reported problem confirmed, with root cause)

| # | Reported problem | Verdict | Evidence / root cause |
|---|---|---|---|
| 1 | Selection column useless; version cards should be horizontal flex with image right of info | CONFIRMED | Third pane is a `sel-summary` readout (`tools/static/index.html:102`, `tools/static/index.html:279`) that only echoes asset/version names — no action lives there. `.ver` cards stack vertically with a full-width 240px preview (`tools/static/index.html:33`, `tools/static/index.html:234`), so the list is tall and the middle column crowds the info. |
| 2a | No previous preview visible while editing/judging; referencing a previous version shows no preview | CONFIRMED | Edit modal shows the parent judgement as text only (`tools/static/index.html:156`, `tools/static/index.html:387`) with no parent image. The reference picker renders one checkbox per output key with text labels only (`tools/static/index.html:362`), so picking references is blind. |
| 2b | Asset form should be full-size with routing, not a popup | CONFIRMED (and it supersedes the previous plan) | New-asset is a modal (`tools/static/index.html:106-128`); there is no router at all — no `location.hash` or `#/` handling anywhere in the page. This deliberately reverses the first-pass "popup, never closes on offclick" decision: the modal goes away in favor of a routed page. |
| 3 | Newest version should list first; want compact small thumbs with hover zoom + click-through to original | CONFIRMED | `renderVersions` iterates `curAsset.versions` in stored (oldest-first, append-only) order with no sort (`tools/static/index.html:234`). Thumbs are large full-width previews; there is no hover zoom and the image itself is not clickable (only the small original link is). |

## Success Criteria

- Version cards are horizontal: info on the left, a fixed small thumbnail on the right; the Selection pane is gone and the three-column grid becomes a layout that gives the version list the freed width; `#status` still has a visible home in every view.
- Editing or judging a version shows the relevant images: the version modal displays the parent's latest output image above the parent judgement (and the current version's latest output nearby), and each reference-picker row shows a small thumbnail next to its checkbox.
- Creating an asset happens on a full-size `/assets/new` page, not a modal; pushState routes `/` (asset list), `/assets/new` (new asset), `/assets/:name` (asset workspace, assets sidebar left + versions right) all render, survive reload, and honor back/forward; unknown asset names show a not-found state with a link home.
- Version lists (cards and parent dropdown) run newest-first; cards stay compact; hovering a thumbnail shows a larger preview without navigation; clicking the thumbnail opens the raw original in a new tab without selecting the card.
- No regression: version New/Edit modal, single-run lock, cost line, judgement save, and `floor_default/init` seed view keep working.

## Approach

Stay with vanilla HTML/JS, no build step, no new dependencies. Add a tiny pushState router in `tools/static/index.html` plus a server fallback in `tools/server.py` (`do_GET` serves `index.html` for non-`/api` paths so deep links and reloads work; API 404s stay JSON). The version editor is an inline form section under the versions list, not a modal. Reuse `toServedUrl()` for every new image.

## Key Decisions

- pushState routing (`/...`), not hash routes: real URLs with a minimal server fallback (one branch in `do_GET`), reload-safe, back/forward free via `popstate`; in-app links are intercepted, while `/outputs/*` file links bypass the router. Hash routing was rejected per review.
- Remove the New-asset modal markup entirely rather than keeping both paths: the user explicitly revoked the popup decision, and two creation paths would double validation/error handling. The strict-dismiss work is intentionally discarded.
- Newest-first means reversed stored order (append-only `versions[]`), not timestamp parsing: stable, no migration, no date logic. Apply the same ordering to the parent-version dropdown for consistency.
- Hover zoom is CSS-only (a larger absolutely-positioned copy using the same cached URL, no JS, no extra fetch); on touch devices tap falls through to the original link, which is acceptable.
- `#status` moves to a slim fixed footer bar so it survives the Selection pane's removal and is visible from every route.
- The version editor is an inline full-width form section under the versions list (same stacked fields as the old modal, plus Cancel to collapse): no popups anywhere in the app per review.

## Steps

1. Delete Selection pane, add footer status + router shell.
   - Surface: `tools/static/index.html:81-104` main grid, `tools/static/index.html:102` summary, `tools/static/index.html:279` renderer.
   - Replace the three-pane `main` with routed views (`#/`: asset list; `#/assets/new`: full-size asset form reusing `new-name`/`new-w`/`new-h` IDs and the `add-asset` POST logic; `#/assets/:name`: versions workspace). Move `#status` into a fixed footer. Delete `sel-summary` and its renderer; route render targets the workspace header instead.
2. Horizontal compact version cards, newest-first, hover zoom.
   - Surface: `tools/static/index.html:33` thumb rule, `tools/static/index.html:234` loop.
   - Card becomes `display:flex`: info block left, 112px thumb right wrapped in `<a>` to the original (with `stopPropagation` so image clicks don't reselect). Render a reversed copy of `versions[]`. CSS-only `:hover` zoom overlay (~320px, same `toServedUrl`, cached). Keep the Edit button on the info side.
3. Previews where decisions happen.
   - Surface: version modal (`tools/static/index.html:131-171`), `renderJudgeBlock` (`tools/static/index.html:387`), reference picker (`tools/static/index.html:362`).
   - Edit mode: parent's latest output thumb above parent judgement; current version's latest thumb labeled "This output" above its judgement box. New mode: selected parent's latest thumb refreshes live on parent-select change. Reference rows gain a 48px thumb beside each checkbox via `toServedUrl`.
4. Parent dropdown ordering + not-found route.
   - `fillParentSelect` lists newest-first to match cards. `#/assets/:unknown` renders inline not-found with a home link (backend 404 contract unchanged).

## Validation Plan

- Static: `node --check` on the extracted inline script; hard-refresh, no console errors.
- Routing (no image spend): load `#/`, `#/assets/new`, `#/assets/floor_default`, `#/assets/nope` directly; reload on each; back/forward walk the history; create-form error (duplicate `floor_default`) renders inline on the page, not in a modal.
- Cards: `floor_default/init` plus a second test version confirm newest-first order in cards and dropdown; hover shows zoom; image click opens `/outputs/...-orig.png` in a new tab; card click still selects.
- Modal previews: Edit shows parent + current thumbs; New with a parent shows that parent's thumb; reference rows show thumbs; unrun versions show the existing "no outputs yet" text.
- Highest-risk check: deleting the asset modal leaves no dangling references — `grep` for `asset-modal`, `m-cancel`, `m-x`, `sel-summary` returns nothing and every former caller has a routed equivalent.
- Existing flows untouched: POST version, single-run lock (409 while running), cost line, judgement PUT, seed view.

## Risks / Open Questions

- Risk: removing the asset modal throws away first-pass strict-dismiss work — intentional per the new direction, recorded here so it isn't "rediscovered" later.
- Risk: hover zoom near viewport edges can clip — mitigated with a max-width and right-aligned overlay; adjust after seeing real cards.
- Assumption (reversible): asset workspace keeps the versions New/Edit modal rather than going full-page too; promoting it later is additive.
- Open questions: None — all three problem groups were verifiable locally without user input.
