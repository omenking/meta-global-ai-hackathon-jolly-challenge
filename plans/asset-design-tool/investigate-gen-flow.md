## Investigate Gen Flow

Problem:
We have generated the floor_default, and each iteration we are not getting improvement.
- We aren't getting rid of cracks
- we still have rounded corners even in the no-round-corners
- I'm not sure how we can best do iterations through UI tool ,is our tool flawed.

---

## Investigation (2026-10-27, verified against generated outputs)

### Short answer

Yes — the tool's iteration flow is flawed, and that is the main reason you are
not seeing improvement. It is not primarily that Muse Image 1.0 is ignoring
you, and re-running alone will not fix it.

Three facts, checked directly in the repo, explain all three runs:

1. **Every version sent the exact same prompt to the model.**
2. **Your complaints were written where the model never sees them** —
   in `desc` and in human judgements, not in the prompt.
3. **On a new version's first run, the parent image is never sent at all**,
   so those runs were fresh text-only generations, not edits of the previous
   image.

So each "iteration" was an independent lottery draw from the same prompt.
The outputs differ only by sampling randomness, not by your feedback. That is
why cracks and rounded corners keep coming back.

### Evidence

Versions in `assets/manifest.yml` (checked programmatically — all three
prompts are byte-identical, SHA-256 prefix `376088fbd992`):

| Version | Parent | Prompt sent | What you actually asked for, and where |
|---|---|---|---|
| `init` | — | `Top-down 2D puzzle-game floor tile, light gray stone, flat clean game-art style, single square tile filling the frame, no text` | (baseline) |
| `clean-stone` | `init` | *identical* | "stone has break patterns… border around the tile will mess things up" — written in `desc` only |
| `no-round-corners` | `clean-stone` | *identical* | "Prior run had corners, lets hope we get rid of those" — written in `desc` only; the run's own `desc` even notes "we aren't bringing the previous judgements" |

Judgements in `assets/judgements.yml` say the right things — `init`: "must
cover the entire image, can't [have] a white background… stone should have
no cracks, and no moss or weathering"; `clean-stone`: "the rounder corners
with the white background will show up in tiling so they should not be
rounded". None of those words are in any prompt. `no-round-corners` has no
judgement yet.

What the three generated images actually show (viewed directly, plus a
corner-pixel check):

| Output | Cracks | Outer shape | Edge behaviour |
|---|---|---|---|
| `floor_default-init-20261027-151142.png` | Large dark cracks, moss/weathering | Rounded-corner slab on a **white background** (all 4 corner pixels are white, ~255,255,255) | Texture does not reach the edges at all |
| `floor_default-clean-stone-20261027-161114.png` | Still large cracks | Rounded slab with a grey border/frame, white corners outside it | A framed object, not a fill |
| `floor_default-no-round-corners-20261027-161327.png` | Still cracks — now as cracked flagstone joints across the whole image | Grey frame; internal stones still rounded | Left-vs-right edge mismatch is the worst of the three (~25 RGB units vs ~3–5), so it would seam badly when tiled |

In other words: zero of your three requirements (no cracks, square corners,
edge-to-edge fill) have ever been present in a prompt the model received.

### Root causes, in order of importance

**1. The tool does not carry feedback forward (the tool flaw you suspected).**

- `tools/server.py` `_run_generation()` writes only `version.prompt` to the
  temp prompt file and passes that to `scripts/gen-image`. `desc` and
  judgements are display-only; nothing ever merges them into a prompt.
- The New Version page (`renderVersionNew()` in `tools/static/index.html`)
  shows only a parent dropdown and preloads the parent's *prompt text*.
  It shows no parent image and no parent judgement at the moment you are
  deciding what to change. (The Edit page does show them; New does not.)
  Changing the parent dropdown only swaps the prompt text — nothing else.
- There is no prompt diff and no warning when the new prompt is identical
  to the parent's. The tool happily saved and ran two no-op iterations.
  Your complaints went into the `desc` field, which reads like "describe
  your goal for this version" but is never sent anywhere.

**2. The parent image is not fed in on a new version's first run.**

- `scripts/gen-image` has two modes: with `-i` references it calls
  `images.edit` (edit this image); without, it calls `images.generate`
  (fresh image from text). These behave very differently.
- The Run page's reference picker (`renderRun()`) lists **the current
  version's own outputs**, not the parent's. A brand-new version has no
  outputs, so it shows "no outputs yet — text-only run" and there is no
  parent image to tick. The parent output only becomes selectable if you
  re-run a version that already has an output — and then you are editing
  your own latest output, not building on the parent.
- Net effect: `clean-stone` and `no-round-corners` were almost certainly
  text-only `generate` calls (they also could not have been edits, since
  their prompts contain no edit instruction). Your instinct in the
  `no-round-corners` desc — "if we can always feed the last image you
  think it would be editing from there" — is exactly what is *not*
  happening.

**3. The prompt itself invites the defects, even before iteration.**

- "**stone**" is the biggest problem word. For this model family, a light
  grey stone surface strongly implies cracked, weathered flagstone with
  moss. Asking that prompt for no cracks is fighting the noun; the current
  prompt does not even try — it contains no "no cracks" wording at all.
- "**single square tile**" reads as *a picture of a tile object*, which is
  why you get a rounded slab with a bevel, border and drop shadow sitting
  on white. "Filling the frame" was not enough to override that. You want
  a *texture that fills the frame*, which is a different instruction.
- Negative-only fixes ("no cracks, no rounded corners" appended to the
  same prompt) are weak against a strong prior, especially in a fresh
  generation. The reliable pattern is: remove the trigger word, describe
  the desired surface positively and concretely, and state the negatives
  as a separate explicit list.
- Nothing in the prompt asks for tileability: no "edge-to-edge", no
  "sharp 90-degree corners", no "opposite edges match / seamless when
  repeated". The single-image view in the tool cannot reveal this either —
  seams only appear when the tile is repeated, and the tool has no tiling
  preview.

**4. One sample per run, no comparison, makes iteration a lottery.**

Each version has exactly one output. With `n=1` and no seed control, a
single draw cannot tell you whether a prompt change helped or you just got
a lucky/unlucky sample. The tool also splits the loop across four separate
screens (New version → back to list → Run → Judge), so the cheap path is
to save-and-run without editing the prompt — which is what happened twice.

Not a cause: the 1600×1600 → 512×512 local resize in `scripts/gen-image`.
It preserves geometry; it does not create cracks, white corners or frames.

## How to get the result you want

Do these in order. Step 1 costs one generation and tests whether a correct
prompt alone fixes it; do not spend more runs through the current flow
until you have done it. Steps 2–3 fix the tool so the loop works for every
future asset, not just this floor.

### Step 1 — One fresh generation with a rewritten prompt (do this next)

Create a new version (suggested slug: `smooth-seamless`) and **replace the
whole prompt** — do not append to the old one, and do not just add
"no cracks". Use text-only generation for this attempt: **do not tick any
reference image, even if the tool offers one.** Editing the cracked
`no-round-corners` output would anchor its flagstone structure; the defect
is structural, so start clean.

Suggested prompt (note: "stone" is gone — that is deliberate):

```text
Full-frame seamless ground texture for a top-down 2D puzzle game, viewed
directly from above. A flat, matte, pale light-grey smooth concrete
surface with only very subtle fine speckle, like smooth polished cement.
The texture fills the entire square image edge to edge and corner to
corner, continuing right up to all four edges. Sharp square 90-degree
corners. Flat even lighting, no shadows, clean flat game-art style.
No cracks, no crack lines, no fractures, no joints, no seams, no grout
lines, no flagstones, no paving slabs, no individual stones, no tile
border, no frame, no bevel, no rounded corners, no white background,
no margin, no drop shadow, no moss, no plants, no weathering, no stains,
no objects, no characters, no text.
```

Then judge it against an explicit checklist before iterating — write the
judgement even if it passes:

- [ ] Surface reaches all four edges and all four corners (no white, no frame)
- [ ] Corners are sharp 90°, not rounded or bevelled
- [ ] No cracks, joints, grout lines or separate slabs anywhere
- [ ] No moss, weathering or stains
- [ ] Repeated 3×3 (see Step 3), no obvious seams, grid lines or repeating crack pattern

If cracks still appear, the next change is to weaken the surface idea
further — drop "concrete/cement" for "plain flat pale-grey plaster, almost
solid colour with extremely faint noise" — rather than adding more "no"
words. Change one thing per version, and say in `desc` what you changed
and why, so the chain stays readable. Expect possibly 2–4 prompt versions
to converge; that is normal for `n=1` sampling, and each one is ~$0.01.

Optional variant, only if the fresh attempt is close but not clean: use
the tool's edit mode deliberately — re-run that version with its own
latest output ticked as reference and an *imperative edit* prompt, e.g.
"Edit this image: remove every crack and joint line and fill them with the
same smooth pale-grey surface; extend the surface to all four edges and
corners; make the corners sharp and square; keep the flat colour and
lighting; do not add any pattern, border or objects." Never send the
descriptive prompt above as an edit prompt — edit mode needs instructions
about what to change, not a re-description.

### Step 2 — Fix the iteration loop in the tool (highest value first)

These are the changes that make the UI do what you originally expected it
to do ("a version carries forward the image and judgement"). All are in
`tools/static/index.html` except 2b, which may also touch
`tools/server.py`:

- **2a. Parent reference by default on the Run page.** In `renderRun()`,
  list the *parent version's* latest output first, pre-ticked, labelled
  "parent: \<slug\>", ahead of the version's own outputs. Also show a
  plain-language mode line before running: "Mode: image edit (1 reference)"
  or "Mode: text-only generation". Today the user cannot tell which mode
  will run, and the default is silently the wrong one for iterating.
- **2b. Show what will actually be sent.** On the Run page, display the
  exact prompt text that `_run_generation()` will write to the prompt
  file, and (cheap server-side guard) warn or block when a child version's
  prompt is identical to its parent's and no reference image is selected —
  that combination is a guaranteed no-op iteration. A prompt diff against
  the parent (even a simple word-level highlight) serves the same purpose.
- **2c. Bring the parent into the New Version page.** Show the parent's
  latest image and its judgement next to the prompt textarea
  (the Edit page already does this — reuse it), plus a "judgement of
  parent" box the user edits *before* the prompt. Add a button such as
  "Insert parent judgement as constraints" that appends a
  `Keep: … / Avoid: …` block to the prompt draft, so turning feedback
  into prompt wording is one click instead of retyping from memory.
  Keep free-text judgement as the source of truth; this is a drafting
  aid, not a schema.
- **2d. Close the loop on one screen.** After a run completes, take the
  user straight to judging that output (image large, checklist + free
  text), and from the judgement screen offer "Create next version from
  this" which pre-fills slug, parent and prompt. The current
  four-screen round trip is how two iterations shipped with unchanged
  prompts.

### Step 3 — Make judgement able to see tiling (small, high value)

- **3a. Tiling preview.** Wherever an output is shown for judging, add a
  3×3 repeated view (nine copies via CSS background-repeat or a canvas).
  For floor/wall tiles this is the actual acceptance test: white corners,
  frames, rounded slabs and edge mismatches are instantly obvious tiled
  and easy to miss single. This one view would have failed all three
  current outputs on sight.
- **3b. A short per-asset checklist** stored with the judgement (the five
  boxes in Step 1 for floors). Free text stays; the checklist just stops
  a known requirement being forgotten between versions.
- **3c. Allow judging multiple outputs per version.** Re-running a version
  already appends outputs; make sure the Judge page lets you pick the
  best of them and mark it preferred, so "run the same prompt twice,
  keep the better draw" is a legitimate cheap strategy instead of
  spawning a new version per sample.

### What not to do

- Do not re-run `no-round-corners` (or any version) with its current
  prompt hoping for a better draw — same prompt, same defect distribution,
  ~$0.01 per ticket.
- Do not feed a cracked image as the reference and describe the *target*
  texture; if you use a reference, write an imperative edit instruction,
  and prefer a fresh generation when the defect is in the basic structure
  (cracks, slab layout, framing) rather than in details.
- Do not put requirements only in `desc` or judgements and expect them to
  affect generation — until Step 2 lands, the prompt textarea is the only
  thing the model ever sees. If it is not in the prompt, it did not happen.
- Do not judge floor tiles from the single image alone once Step 3 is
  possible; a tile that looks fine singly can still seam badly.

### Bottom line

Your iteration process is broken in the tool, not in your judgement: the
feedback was written down correctly and then never reached the model, the
parent image is unreachable on a new version's first run, and the one
prompt that does run invites cracked stone slabs on a white background.
One fresh generation with the rewritten prompt in Step 1 is the cheapest
test of the fix; Steps 2–3 then make the tool carry image, judgement and
prompt forward the way the original design intended, so future assets
iterate instead of re-rolling.
