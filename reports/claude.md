# Jolly's Challenge: Challenges, Technical Uncertainty and Workflows

This report gathers the problems this project ran into, how each was solved, and the workflows that came out of the work. It draws on `docs/`, `plans/`, the project-manager board (`plans/simple-game-engine/pm.yml`), the asset driver run reports, and the git history from 26 October to 2 November 2026.

## At a glance

| Measure | Value |
|---|---|
| Commits on `main` | 113 |
| Features on the board | 84 (10 base-game features completed, 73 mechanic sanity checks in review, 1 proposed) |
| Tasks on the board | 302 |
| Python test cases in `tools/test_*.py` | about 270 |
| Feature worktrees created | 75 |
| Candidate mechanics designed | 100, across 10 YAML family files |
| Typical cost per base-game feature | $5 to $10 |
| Cost of a grounded AI-driven asset run | $0.04 per tile (four images, one turn) |

## The core technical uncertainty

The question the project set out to answer is stated in `docs/technical-uncertainty.md`: **can an agent design fun and creative levels?** Earlier games all stalled on level design and pacing, which depend on creative judgement and a large amount of manual playtesting. The hypothesis was that a game small enough in scope would make it possible to run a controlled experiment on where an AI model's level design ability ends.

Answering that question required infrastructure that did not exist at the start. An agent cannot be judged as a level designer unless the game is deterministic, every playthrough can be recorded and replayed, each mechanic can be tested in isolation, and a human can review the agent's evidence without rerunning it. Most of the work described below is that infrastructure.

### Self-imposed constraints

The project deliberately reproduced the limits other hackathon participants faced (`docs/technical-limitations.md`):

- a Meta Model API budget of $150;
- art generated only by Muse Image 1.0 or newer;
- Muse Spark 1.3 or newer, and only Muse Code as the coding agent.

The plan was to branch off cleanly if the budget ran out. The constraint on models was relaxed during the project once Muse Wonder turned out to be available through the API (see [Model selection](#model-selection-spark-versus-wonder)).

## Choosing a game that fits the experiment

Wolfenstein 3D was the first idea but was too large for a ten-day hackathon and the budget. Sokoban was the next candidate, but playtesting it (`docs/game-testing-research.md`) showed it relies on punishingly hard logic that exhausts players. Chip's Challenge, which is Sokoban-like but leans on a steady stream of new mechanics and a time limit, gave a better design target. The playtests produced four design rules: the game should not mentally exhaust the player, a dead end should not make replaying a level tedious, progression should keep feeling novel, and the mechanics should tell a story. The game is built around Meta's Jolly character, with orbs as Jolly's primary resource and a gated elevator as the exit.

## Challenges and how they were solved

### 1. Enforcing a hard spending limit

**Problem.** A $150 budget means nothing unless something stops spending when it is reached, and Muse Code does not by default separate subscription usage from pay-as-you-go API usage.

**Solution.** Two community tools were built before the hackathon started and published separately: `meta-costcenter`, which records usage, and `meta-keyguard`, which issues short-lived API keys. They are linked so that the cost centre can revoke the project key when a billing alert fires:

```sh
meta-keyguard create jolly-challenge --ttl 10d
meta-keyguard cost-center on
meta-cost hook install
meta-cost alert set --monthly-usd 150 --project meta-global-ai-hackathon-jolly-challenge --revoke-keys 'jolly-challenge'
```

The Muse hook makes Muse Code's own spend visible to the cost centre, and every image generation call reports to it as well. The result is a kill switch rather than a dashboard.

### 2. Generating images when the coding agent has no image access

**Problem.** Muse Code had no direct access to Muse Image 1.0.

**Solution.** `scripts/gen-image` wraps the Muse Model API through the OpenAI SDK, since the API is OpenAI-compatible and has no SDK of its own. It loads the key through `meta-keyguard get` so that usage is attributed, and it accepts a prompt file, dimensions, an output path and reference images.

**An uncertainty resolved along the way.** A request for 512x512 produced a 1600x1600 PNG while the script's summary line reported `size=512x512`. The investigation (`plans/gen-image/fix-gen-image-script.md`) established that this was not a pass-through bug: for Muse Image the `size` parameter sets only the aspect ratio, and the image is produced at the generator's native resolution. The script now resizes to the requested dimensions with ffmpeg and keeps the raw output as an `-orig` file. Billing is per image, so the native size has no cost effect. The discrepancy was caught by a second model reviewing the work outside the Meta budget, which shows the value of an independent reviewer.

### 3. Image iterations that were not actually iterating

**Problem.** The first version of the asset design tool produced no improvement across versions of the floor tile. Cracks and rounded corners kept returning.

**Root cause** (`plans/asset-design-tool/investigate-gen-flow.md`). Three faults combined:

1. every version sent a byte-identical prompt to the model (all three shared the SHA-256 prefix `376088fbd992`);
2. the human's complaints were written into the version description and the judgements, which the model never saw;
3. a new version's first run never sent the parent image, so each "iteration" was a fresh text-only draw.

Each version was therefore an independent lottery from the same prompt, and the differences were sampling noise.

**Solution.** The tool was redesigned around how modern image models work rather than around single-shot prompting:

- **Lottery runs** generate 1 to 10 images per call at about $0.01 each, so it is cheap to generate many and choose.
- **Prompt building** composes selected images, their judgements and per-image notes into the prompt itself.
- **Sessions** keep a server-side thread of turns, so each turn only needs a short change instruction ("remove the cracks, keep the stone colour") while prior outputs are carried forward as reference images, preferred images first. Each turn records the exact prompt and references, so runs are reproducible.

A related finding is that Muse Image 1.0 is very literal, so prompts are best written by Spark or by Wonder at low effort rather than by hand. With good prompts, the image quality was comparable to or better than GPT Image 2.5, although style consistency across assets remained difficult.

### 4. AI-judged art that passed its own review and was still wrong

**Problem.** The asset driver (`plans/ai-asset-driver/PLAN.md`) lets Muse run the whole art loop: write the brief, generate through the Muse image tool, judge each output, feed winners back, and publish. Its first run on the crumbling tile produced plausible stone that passed its own judging, but it was not this game's stone, and its realistic hairline cracks were nearly invisible at the size the game renders.

**Solution.** `plans/ai-asset-driver/GROUNDING.md` sets two rules that every run must follow:

1. **Generate from the game's real sprites, not from a description.** Floor-family assets pass `floor_default.png` as an actual reference image, and staged damage is produced by editing that sprite, so stage zero is the game's floor by construction. A phrase such as "light grey stone matching the floor" does not count as grounding.
2. **Judge at camera scale.** Tiles render at 64px, where one pixel is eight pixels of the 512px source, so a 2 to 3px crack disappears. Cracks must be bold (8 to 12px at 512px), and every candidate is judged downscaled to 64px beside the real floor and its neighbouring stages, with an in-room screenshot as the final check.

The grounded reruns are captured as YAML run reports in `plans/ai-asset-driver/reports/`, which record the references, every generated file, a verdict with a visual reason for each output, the winner and the spend. The grounded intact crumbling tile took a single turn of four images at $0.04, with verdicts such as "bad: chunky black fissures already read as major damage". Style consistency across the four stages is built in rather than hoped for, because each stage's winner becomes a reference for the next.

### 5. A deterministic engine with replay and forks

**Problem.** Agent playtesting is only evidence if a reviewer can replay it exactly.

**Solution.** The game shell was built on a pure step function from the first feature (`tools/static/game-core.js`: `initialState`, `step`, `replay`, `stateDigest`). Every input carries a recorded `t_ms`, and no mechanic may read unrecorded wall-clock time. Sessions are JSONL files with a header (level source hash, engine version, creator, feature, task, branch, commit, fork lineage) followed by one line per input. On top of that the project built a sessions menu, a time-based replay player with step markers, forking from any point of a replay, append-only annotations, deep links of the form `?replay=<session-id>&t=<seconds>`, and warnings when a session's level, engine or commit differs from the running build.

Two reliability fixes came out of human review. Sessions now start on the first move instead of on page load, which had created many empty sessions, and any finished run (won or lost) now freezes its clock, step count and HUD, after a playtest showed the timer still ticking after death.

### 6. Feature-driven development with a human review gate

**Problem.** The goal was for the human to stay at the level of features while the agent handled tasks, with every feature tested by a human before it reached `main`.

**Solution.** A purpose-built project manager (`tools/server.py`, `tools/pm_store.py`, a React and HeroUI front end) and a written contract for the agent, `plans/simple-game-engine/agent-workflow.md`, loaded by the project skill `.claude/skills/work-on-feature/`. The main rules are:

- One feature is one branch (`feat/<id>`) and one worktree (`.worktrees/<id>`); one task is one commit. The feature page is the review unit and replaces a pull request.
- The agent works an eight-step loop: pick up an approved feature, claim the task, isolate in the worktree, implement and verify one task, attach screenshots and recorded sessions, roll up for review, turn a "Request changes" decision into a numbered `review-fixes-N` task, and merge only after "Approve for merge".
- Hard rules prevent the agent from starting an unapproved feature, approving its own work, editing the board store by hand, or marking a feature complete by any route other than a verified merge.
- Every mechanic has its own small Test Level so it can be exercised in isolation.

All ten base-game features shipped through this loop: game shell, player movement, session logs and replay, level timer, keys and locks, orbs and gate, warp and level progression, the HUD, the engine refactor and fixed world scale.

**What was learned.** Because the agent was driven from interactive Muse Code, comments rarely went through the PM tool, and features were executed one task at a time with no blockers. The planned parallel subagent execution never happened. Sequential execution turned out to suit the human review gate, but the tool was more elaborate than the workflow needed.

### 7. Building usable operator UIs

**Problem.** The agent struggled to produce usable interfaces. The session replay feature alone went through ten numbered review-fix rounds plus three more fixes: a side panel ran off the page, overlays covered board tiles, the loaded session was unclear, the canvas stretched on resize, the timeline was step-based instead of time-based, and play did not toggle to pause. A HeroUI overlay and then a Leva parameter panel were both tried and abandoned.

**Solution.** Installing skills from skills.sh (`find-skills`, then interface design and usability skills) and giving the agent a task-focused brief changed the outcome. The brief described the tool as an operator tool rather than a dashboard, listed the primary workflows (select, replay, scrub, inspect, annotate, fork), required an unobstructed viewport and a single timeline, and asked the agent to propose the information architecture and critique real screenshots before finishing. The result was the operator layout that the game page still uses.

Graphical UI assets such as HUD frames remained hard because they have to be sliced at precise boundaries. Those were generated partly in Muse Playground and finished by hand in Illustrator and Photoshop.

### 8. Refactoring a monolith into a kernel and mechanic packs

**Problem.** After the base game shipped, the code was a few large monolithic files with mechanic-specific checks spread through the core. With 100 mechanics planned, each new mechanic would have had to read and edit the same files, which costs tokens and causes regressions.

**Solution.** The agent was asked to audit the codebase and write a plan before changing any code (`plans/game-engine-refactor/`). The plan defined a layered kernel with a registry, moved mechanics into "packs" in the manner of a mod system, and pressure-tested the design against hypothetical mechanics (water that kills unless an item is carried, a button linked to a trap, a monster, and ice or force floors) to check that none of them would require kernel changes. The migration was phased so that the game stayed playable after every phase, with two guards:

- **A regression corpus** (`tools/refactor_corpus.js`, `tools/refactor_golden.json`) records the state readout after every step of known playthroughs before the refactor, and each phase must reproduce it exactly.
- **A kernel purity gate** (`tools/check_kernel_purity.sh`) counts mechanic-specific identifiers such as `isOrb`, `gate_open` and `KEY_COLORS` in kernel files. The baseline was 30 and the target was zero.

Keys and locks were extracted first to prove the design, followed by the core orbs pack, water, ice and force floors, buttons and traps, and a patrolling monster. Packs later became folders containing `main.js`, a manifest and their own assets.

**What was learned.** When Muse attempted four pack proposals at once, none of them worked correctly. Feature development needs to happen one feature per session.

### 9. A fixed world scale and camera

All early levels were scaled to fit the viewport, but Chip's Challenge levels are larger than the screen. The fixed-world-scale feature pinned every tile at 64px and introduced a camera that translates without scaling and keeps Jolly in frame. That decision later set the 64px judging scale used for asset grounding in challenge 4.

### 10. Sessions that were recorded but proved nothing

**Problem.** An audit of the base game (`plans/qa-framework/PLAN.md`) found that recorded sessions carried `feature: null, task: null, branch: null, commit: null`, that most ended in `quit` rather than `won`, and that nothing checked whether a session replayed to the same end state. Human playtesting caught bugs that green unit tests had missed, such as the game menu loading the full `chip1` level instead of the test room.

**Solution.** A four-tier evidence model with one hard gate before review:

| Tier | Proves |
|---|---|
| T1 Unit | rule logic in isolation |
| T2 Level | the test room loads through the real game menu, a scripted winning log reaches `won`, and an empty input log does not |
| T3 Session replay | `tools/verify_mechanic_qa.py` replays each linked session, compares the digest and the recorded end state, and checks readout values at annotated steps against the spec |
| T4 Human playback | the reviewer replays and scrubs the agent's success session from the feature page |

Each mechanic must record a success session, a **naive-failure session** that performs the obvious wrong action and shows it fail as the spec describes, and edge sessions. One validation case shows why readout assertions are needed: a weakened mechanic in which ice stops one tile short still matches its own digest, so only a step-level assertion catches it.

Two skills from skills.sh were read in full during planning, and the plan records which ideas were borrowed (design-intent thresholds, an entity interaction audit, test matrices) and which were rejected with reasons. Playwright, pixel diffing and clock mocking were rejected because the game is a deterministic turn-based grid where recorded `t_ms` already gives stronger guarantees than a browser clock mock.

### 11. Catching soft-locks through adversarial play

The crumbling tile is a useful case study. A human playtest found that crossing a bridge and then stepping back onto its middle tile left the player stranded between voids with no legal move and no way to lose or reset. Further review found that the void had been implemented as a wall, so falling could never happen, and the staging was redesigned twice before settling on tiles that degrade by one stage each time the player leaves them.

This led to a project-wide rule now written into the agent contract: **a reachable state with no legal move and no lose or reset is a failure, however well the solution path plays.** Every mechanic's test cases must include an adversarial case (backtracking, hesitation, or the naive action the teaching moment warns about) as well as boundary and restart cases.

### 12. Designing 100 mechanics without designing 100 levels by hand

**Problem.** Designing each level and adding mechanics one at a time was too labour-intensive.

**Solution.** Muse generated 100 candidate mechanics, which were reviewed and annotated by hand and then enriched into a structured YAML format (`plans/level-design/candidate-mechanics/`). Each entry carries:

- `definitions` of every term its rules use, with cross-references to the mechanic that owns a borrowed behaviour; an undefined term blocks the ticket;
- `mechanics`, one rule per line;
- `assets` the pack must bundle, written before the pack is built;
- `test_cases`: solution path, adversarial, boundary, and restart and replay;
- `synergies`, which must produce an effect neither mechanic gives alone, kept separate from `demos`, which only compare;
- a `teaching_moment`, the designed first encounter in which the obvious action fails in a way that reveals the missing rule and costs only a restart of a small room.

These became 73 sanity-check features on the board, each with its own test room, which is the groundwork for the original question. A roadmap log (`plans/level-design/roadmap/`) records how levels are chosen. Level 001 was written by a human as a template, level 002 was authored by the AI and accepted after a rename, and for level 003 two AI candidates were merged by the human into "colours beyond the screen".

### 13. Managing dozens of worktrees and stray servers

With one worktree per feature and a playtest server per worktree, ports piled up. A `/worktrees` page backed by `tools/worktree_mgr.py` now lists registered worktrees and their running servers, links to each one, and starts or stops their servers. It never removes worktrees, branches or files.

## Model selection: Spark versus Wonder

Muse Spark at extra-high effort struggled with UI fixes. Muse Wonder at low and medium effort was tested outside the original rules and proved both cost-effective and better at that work, so feature development moved to Wonder at medium to extra-high effort. Muse Wonder had in fact been available through the API from the start, and using it earlier would have avoided much of the UI churn. Whether Spark or Wonder should drive feature and task work remains an open question.

## Reusable workflows

- **Plan before code.** Large changes (refactor, QA framework, asset driver, gen-image fix) began with the agent writing a plan file, which was reviewed and annotated inline by the human before any implementation.
- **Feature as pull request.** Worktree per feature, commit per task, evidence on the feature page, human approval, then an agent-run merge.
- **Evidence over assertion.** Screenshots captured headlessly from the worktree build, recorded sessions, and a verifier that replays them.
- **Test Levels per mechanic.** Small isolated rooms in which a teaching moment can fail cheaply.
- **Find a skill when the agent stalls.** skills.sh skills fixed the UI problem and informed the QA design.
- **Ground generated art in shipped art.** Use real sprites as references, judge at display size, and keep a YAML audit trail of every verdict.
- **Independent second reviewer.** A model outside the budget caught the image size discrepancy.

## Open questions and next steps

- **Can the agent design fun levels?** The infrastructure is now in place, with 73 mechanics specified and in review and the first AI-authored levels on the roadmap. The answer depends on the synergy rooms and full levels that come next.
- **Code organisation and cost.** Isolating mechanics into packs should reduce how many files an agent reads per feature, but this has not been measured.
- **PM tool complexity.** A simpler tool, or a platform with comment hooks such as GitHub, may fit the sequential single-agent workflow better.
- **Art consistency.** One idea is to generate a full reference level screenshot (Chip's Challenge layout with Jolly) and extract tiles from it. An early test was consistent except for walls.
- **Engine.** Porting to a different engine, or to 3D, may give better visuals, but PixiJS remains the practical choice for now.
