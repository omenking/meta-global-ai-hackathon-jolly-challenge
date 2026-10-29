# Meta-Global-AI-Hackathon Jolly's Challenge

- [Technical Uncertainty](./docs/technical-uncertainty.md)
- [Technical Limitations](.docs/technical-limitations.md)
- [Game Environment](./docs/game-env.md)
- [Game Testing Research](./docs/game-testing-research.md)
- [Game Lore and Mechanics](./docs/game-lore-and-mechanics.md)
- [Community Tools to Track Usage](./docs/community-tools-to-track-usage.md)
- [Mininal Graphical Assets](./docs/minimal-graphical-assets.md)
- [Project Manager and Simple Game Engine](./docs/pm-and-simple-game-engine.md)

## Asset Design Tool

Iterate on generated tile art from a local UI instead of hand-editing YAML.
The backend owns `assets/manifest.yml` and `assets/judgements.yml`; every
run goes through `scripts/gen-image` once and is reported to Meta Cost Center
(needs a `meta-cost` with the `record` command; otherwise you get a warning
and the image still saves).

```sh
source .venv/bin/activate
python tools/server.py
```

Then open http://127.0.0.1:8321/ in a browser for the tools homepage,
or http://127.0.0.1:8321/assets for this tool directly. See
[plans/iterative-asset-design-tool.md](./plans/iterative-asset-design-tool.md).

### Lottery runs (1–10 images)

On the Run page choose N (default 4). One action makes one Meta Image 1.0
call producing N images (~$0.01/image); the run log shows the total and each
image shows its share. There is no parent picker: on the version itself
(New/Edit version form) tick up to 10 specific images from any prior run —
nothing is pre-ticked. Each chosen image shows its judgement with a "bring
judgement" toggle plus a per-image note field; "Build prompt from selected
images" composes notes and judgement constraints into the prompt (repeat
builds replace their own previous output, hand edits are kept). A live
edit-vs-text-only mode line confirms what will run. The Run page just
confirms the version's stored selection and N, then runs. N=1 behaves
exactly as before.

After a batch, the Judge view shows a clickable grid; judge each, then
"Save + create next version" marks the winner preferred and opens a new
version with that winner pre-ticked.

### Sessions (multi-turn iteration)

Each version run starts a fresh image call, which forces the prompt to
carry the entire description every time. Sessions remove that burden by
keeping the iteration history server-side: on an asset page, "New session"
opens a workspace organized as a thread of turns, where each turn needs only
a short delta instruction ("remove the cracks, keep the stone color")
because the prior turns supply the rest of the context.

- Context auto-carries, so a turn with nothing ticked sends prior session
  outputs newest-first (preferred images first, up to 10) as reference
  images. Ticking boxes overrides this with specific images, while "Fresh
  text-only" sends none. Because every turn records the exact prompt and
  references sent, runs stay reproducible.
- The context tray in the left pane holds uploaded reference images
  alongside the asset's published outputs, since both are valid starting
  points for a turn. Uploads accept png/jpg/webp up to 8 MB, and every entry
  has "Copy name" so the filename can be pasted into the prompt box.
- Turns keep the lottery behavior (1–10 images, default 1 for turns), and
  each image is judged inline with free text plus a preferred flag.
  Publishing appends the winner as a new version of the target asset, which
  means an existing name gains a new version while a new name creates the
  asset; the published version reuses the output file so judgements carry
  over, and publish never overwrites.

Because iteration state lives in a third backend-owned file,
`assets/sessions.yml` (same atomic-write pattern as the other files),
`assets/manifest.yml` changes only via publish.

## Project Manager Tool

Board for the simple game engine's work: a **Feature** (player-facing
capability, specified with `plans/simple-game-engine/template.md`) breaks
down into **Tasks**, the small units that get picked up, dragged across
the board, and commented on. The feature — rolled up in the UI with its
tasks, comments, screenshots and linked play sessions — is the review
unit (our "PR"; there are no GitHub PRs). The human approves a feature,
playtests it and reviews it on the feature page (there is no separate
review page), then clicks **Approve for merge**;
Muse Code performs the merge and only then does the feature become
`completed`.

```sh
source .venv/bin/activate
python tools/server.py
```

Then open http://127.0.0.1:8321/ in a browser and choose Project
Manager (the board also lives at `/pm` in the tools app, with feature
pages at `/pm/features/<id>`; the old `/static/project-manager.html` URL
redirects there). The frontend is a
React + HeroUI (v3) + Tailwind v4 app built with Vite from `tools/web/`
into `tools/static/app/`; after editing it, rebuild with
`npm --prefix tools/web install` (first time only) and
`npm --prefix tools/web run build`. If the build output is missing, `/`
falls back to a static tools homepage.
The store is `plans/simple-game-engine/pm.yml` (backend-owned; written
only through the API), markdown exports land in
`plans/simple-game-engine/features/`, and screenshot evidence lives in
`screenshots/features/<feature-id>/`.

To drive Muse Code: prompt it interactively, e.g. "work on
`keys-and-locks`" or "merge approved features". The project skill
(`.claude/skills/work-on-feature/`) loads the canonical contract in
`plans/simple-game-engine/agent-workflow.md` — the 8-step pickup,
worktree (`.worktrees/<feature-id>` on `feat/<feature-id>`), evidence,
review and agent-merge workflow. See
`plans/simple-game-engine/project-manager-tool-plan.md`.

## Level Preview Tool

Renders level layouts from `levels/*.json` in the browser (PixiJS) using
keyed sprites derived from `assets/published`. Key/lock colors are currently
hue-rotated placeholders; real variants come later through the asset tool.

```sh
bash tools/prep_level_sprites.sh   # derive sprites + stage level JSON
source .venv/bin/activate
python tools/server.py
```

Then open http://127.0.0.1:8321/static/level-preview.html in a browser
(`?level=chip1` selects the level file). Edit the grid in
`levels/chip1.json` (rows plus legend) and re-run the prep script to
restage it. See [plans/level-preview-tool/plan.md](./plans/level-preview-tool/plan.md).

### Screenshots

Capture the rendered page headlessly into `screenshots/` (needs
`google-chrome` and a Python with Playwright; the wrapper picks one):

```sh
bash tools/capture_level.sh chip1            # timestamped + -latest.png
bash tools/capture_level.sh --compare chip1  # also side-by-side vs reference
```

The page also has an "Export board PNG" button for downloading the board
canvas directly. See
[plans/level-preview-tool/screenshot-export.md](./plans/level-preview-tool/screenshot-export.md).