## Lottery Image Design

## Image Output
Meta Image 1.0 api allows us to specify n from 1 to 10 generated output
This allows us to have more images generated out like a lottery.
And then you choose the image you prefer.

### Image Input
Meta Image 1.0 allows us to supply up to 10 images for reference.

### Goal
We want to have better image generation, and so we want to be able 
for a new version provide previous references of images along with prompt information.

We want to have the option of setting how many images generated during an output version.
We can then judge the outputs.

This way we are selective brining one or many images from prior image version runs.
We are having better changes for choosing the best one to promote.

## Challenge

The key thing is how does a good prompt get built while the user has to do the least amount of cobboling together the prompt, the flow should just make it happen.

---

## Plan — Lottery Image Design (n-draw runs + reference picker + auto prompt draft)

## Goal

Extend the asset design tool so one version run can generate 1–10 images in a single Meta Image 1.0 call (a "lottery"), accept up to 10 reference images pulled selectively from prior version runs, and let the user judge the batch and promote the winner — while the tool assembles the prompt draft so the user edits rather than cobbles it together.

## Success Criteria

- User can choose N (1–10, default 4) on the Run page; one action produces N outputs under the same version, each viewable, each judgable, at ~$0.01/image cost visibility.
- User can select 0–10 reference images from prior runs (parent latest pre-ticked for a new version's first run, plus own outputs and preferred outputs from the same asset); >10 is blocked client- and server-side with a clear message.
- New-version flow auto-drafts the prompt from parent prompt + parent judgement/checklist failures, so the common case is review-and-tweak, not retyping; what the Run page shows as "exact prompt that will be sent" is byte-for-byte what `scripts/gen-image` receives.
- After a lottery run, the user lands on a batch-judge view (grid of N), can set per-image checklist + free text, mark exactly one preferred, and one-click "Create next version from winner" with winner image + judgement carried forward.
- No regression: N=1 behaves exactly as today; existing CLI flags, single-run lock, Cost Center recording-once-per-call, and `floor_default` history keep working.

## Approach

Reuse what already supports lottery and add the smallest missing pieces. `scripts/gen-image` already implements `--num 1-10`, repeatable `-i`, edit-vs-generate branching, multi-file `resolve_outputs`, and per-call `record_usage` with `--images len(data)`; the backend (`tools/server.py` `_run_generation`) currently hard-codes n=1 and a single `record_output`, and the frontend (`tools/static/index.html` `renderRun`) already pre-ticks the parent output and shows the exact prompt — extend these rather than inventing a new pipeline. Keep `version.prompt` as the single source of truth (no silent server-side prompt merging); all "smart" assembly happens as an editable draft at version-creation time. Keep the single `RUN_LOCK`, atomic YAML writes via `tools/asset_store.py`, and judgement keying by output key.

## Steps

1. Backend: multi-output run plumbing (`tools/server.py`, `tools/asset_store.py`).
   - Accept `num` (int 1–10, default 4) and `references` (0–10) on `POST /api/runs`; validate range, validate each ref resolves inside `assets/outputs/` and exists (reuse current path checks).
   - Pass `--num <N>` through to `scripts/gen-image`; expect N files back using the existing `-1..-N` suffix convention. Generate keys as `<asset>-<slug>-<stamp>-<i>` so keys stay unique and judgement-keyed.
   - Record all N outputs via `record_output` (loop) under one run id; store per-output `estimated_usd` as total/N (2-decimal string, null when unpriced) and keep the run total + warning in the `RUNS[run_id]` log entry. `mark_failed` behaviour unchanged on non-zero exit / timeout.
   - Extend `validate_run_not_noop` handling: identical-prompt block still applies only to first-run text-only (no refs), regardless of N — N>1 with an identical prompt is still a re-roll lottery and allowed only as an explicit re-run, not a new version's first run.

2. Reference picker: up to 10 from history (frontend + server cap).
   - Frontend `renderRun`: group picker as parent-latest (pre-ticked when version has no outputs), then this-version outputs (newest first), then preferred outputs from other versions of the same asset; show live count `k/10`, disable further ticks at 10, keep mode line ("image edit (k references)" vs "text-only generation").
   - Server: reject `len(references) > 10` with 400; pass through as repeated `-i` in order selected (order = picker order, parent first).

3. Least-cobbling prompt draft (the Challenge fix).
   - Add a small pure helper (co-located with `asset_store.py` or inline in `index.html`): `draft_from_parent(parent.prompt, parent.judgement, checklist)` → parent prompt + `\n\nConstraints from parent judgement: …` block built from failed checklist items via a fixed map (e.g. `covers_frame=false` → "texture must fill the entire frame edge to edge with no margin/border"; `square_corners=false` → "sharp square 90-degree corners, no rounding/bevel"; `no_cracks=false` → "no cracks/joints/grout/flagstones"; `no_weathering=false` → "no moss/weathering/stains"; `seamless_3x3=false` → "opposite edges must match so 3×3 tiling shows no seams") plus the raw parent free-text judgement quoted underneath.
   - Wire into New Version page: when a parent with judgement is chosen, auto-insert the draft into the prompt textarea (fully editable, with existing word-diff + "identical to parent" warning still live); keep the existing "Insert parent judgement as constraints" button as re-apply. Run page remains display-only verbatim prompt — no hidden merge at run time.

4. Lottery judge + promote (frontend + `PUT /api/judgements/<key>` reuse).
   - After a run returns N keys, route straight to Judge showing an N-grid (thumbnail + key + cost share); per-image checklist (existing five boxes) + free-text + preferred radio (existing single-preferred-per-version invariant already enforced server-side).
   - Add "Create next version from this winner" per image: creates child version with `parent=<current slug>`, prompt prefilled via step-3 draft from the winner's judgement, and winner image pre-ticked on the next Run. Reuse existing tiling 3×3 preview per selected image for floor acceptance.

5. Tests, polish, docs.
   - Extend `tools/test_asset_tool.py`: N bounds (0/11 rejected, 1/10 accepted), >10 refs rejected, multi-key naming uniqueness, cost-split rounding, draft-builder mapping for each checklist flag, noop-guard still blocks identical-prompt text-only first run even when N>1.
   - Frontend guards: N as number input 1–10 with server as authority; run button progress state across the longer multi-image call (keep 600s timeout, surface stderr distinctly for key-revoked vs generation failure).
   - Docs: short README section (default N=4 cost note, how to pick refs, how prompt draft works, how to promote a winner); seed view unchanged from `floor_default`.

## Validation Plan

- Unit: `python -m unittest tools.test_asset_tool -v` — new bounds/naming/draft tests plus existing judgement + noop-guard tests green.
- Store round-trip: create asset → child version via draft helper → simulate 4-output record → preferred + judgements → reload `assets/manifest.yml` / `assets/judgements.yml`; `diff` shows only intended additions, existing `floor_default` entries byte-identical.
- Mock multi-run (no API spend): stub `scripts/gen-image` via a temp executable on PATH (or `META_COST_COMMAND` wrapper pattern from the prior cost-center plan) that writes N PNGs and prints the Cost Center line; `POST /api/runs` with `num=3` yields 3 keys, 3 files in `assets/outputs/`, per-output cost = total/3, single run-log entry with total.
- Manual E2E: start `python tools/server.py`, new version from `refined-background` (auto-draft visible), N=3 with 1 parent ref → 3 thumbnails → judge each → mark preferred → "next version from winner" carries image + constraints; restart server, confirm persistence.
- Regression: N=1 run unchanged (single file, no `-i` suffix change); `scripts/gen-image --prompt-file scratchpad/testgenimage/floor.md --width 512 --height 512 -o /tmp/smoke.png` still works; missing `meta-cost` still saves images with exit 0 + stderr warning.
- Edge cases: N=0/11 and 11 refs both 400 with message; deleted ref file warns/400 before spend; API returning fewer than N fails the run loudly (no silent short batch); concurrent Run clicks still 409 via `RUN_LOCK`.

## Risks / Open Questions

- Risk: cost and latency scale with N (10 images ≈ 10× spend per click, longer `/api/runs` wait) — mitigated by default N=4, visible per-run total + per-image share, and keeping the single-run lock.
- Risk: edit mode with many diverse refs can anchor defects instead of fixing them — mitigated by defaulting to parent-latest only (not all history) and keeping fresh text-only generation one untick away, plus the imperative-edit hint line.
This shouldn't be an issues sinc we be exactly choosing which ones to carry forward, we would never simply default one.
- Risk: manifest growth (10 outputs/version × judgements) — acceptable for local single-user use; no pagination in v1, newest-first ordering.
Non issue right now.
- Open questions: None — defaults assumed reversible: N default 4, per-output cost = total/N, draft auto-inserts but stays fully editable.
Default to 1.