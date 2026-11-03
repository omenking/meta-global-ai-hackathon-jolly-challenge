# Jolly’s Challenge: technical challenges and workflow discoveries

Prepared from the repository, project notes, implementation, tests, and Git history on November 3, 2026. This is a retrospective assessment, not a fresh test run. Some QA and project-manager improvements are currently uncommitted; their presence is not evidence that the full planned workflow has been validated.

## The central experiment

Jolly’s Challenge asks a more interesting question than whether AI can write a game: **can an agent design enjoyable puzzle levels, with good pacing and creative judgment?** Previous projects required substantial manual playtesting and adjustment. A small tile-based puzzle game creates a manageable setting for investigating that uncertainty.

The research into Sokoban and Chip’s Challenge sharpened the target: logical challenges and new mechanics should reward the player without exhausting them or making restarts tedious. That makes “the level is solvable” necessary, but insufficient, evidence of success.

The repository demonstrates substantial progress on the infrastructure needed to investigate that question. It does not yet establish that AI independently produces fun levels or good pacing.

Evidence: [original uncertainty](../docs/technical-uncertainty.md), [playtesting research](../docs/game-testing-research.md).

## 1. Making AI gameplay reproducible and inspectable

**Challenge:** A screenshot can show a plausible game board without proving how it got there, whether the rules worked, or whether a reported bug can be reproduced.

**Solution:** The game exposes a deterministic state interface through `initialState`, `step`, `replay`, `readout`, and `stateDigest`. Recorded JSONL sessions preserve inputs and timestamps alongside level and development metadata. The replay tools support playback, stepping, scrubbing, annotations, and forks from a selected point.

This makes gameplay an artifact that a human and an agent can both inspect. A reviewer can revisit a particular decision, examine the state, and branch into another attempt. Fork records preserve their source session and step, making alternate attempts traceable.

**Why this stands out:** The project built a debugging and review workflow around playable evidence. The same deterministic core can run in the browser and under Node for automated checks.

Evidence: [core interface](../tools/static/game-core.js), [session storage and forks](../tools/game_sessions.py), [replay implementation](../tools/static/game-replay.js), [replay tests](../tools/test_session_replay.py).

## 2. Discovering why passing tests were not enough

**Challenge:** The QA planning notes identify sessions with missing feature/commit linkage, recordings ending in `quit`, and a menu opening the full level instead of the intended test room. Unit tests could pass while the actual review path still failed.

**Response:** The mechanic QA framework separates four kinds of evidence: isolated rule tests, teaching-room checks, recorded-session verification, and human playback. The current verifier checks linked recordings, replay results, annotated state expectations, and whether an empty input log incorrectly wins the room. It also looks for screenshot evidence and a rule-to-evidence mapping.

The particularly useful insight is that **replay consistency does not prove the mechanic is correct**. A broken mechanic can reproduce its own wrong result perfectly. Assertions about intended positions, counts, and outcomes are needed alongside digest equality.

**Status:** A framework plan, verifier implementation, tests, and workflow amendments exist. Some are uncommitted. Treat universal coverage and enforcement across every mechanic as work to verify, rather than a completed result.

Evidence: [QA rationale and plan](../plans/qa-framework/PLAN.md), [verifier](../tools/verify_mechanic_qa.py), [verifier tests](../tools/test_verify_mechanic_qa.py).

## 3. Refactoring the engine while preserving observable behavior

**Challenge:** Initial feature development produced large files. Adding many novel mechanics risked making each subsequent change harder for the agent to understand and easier to break.

**Solution:** The engine was reorganized into a generic kernel, a registry, and mechanic packs. A compatibility facade preserves the established public interface while the internal state uses separate terrain, objects, and actors. Packs own mechanic rules and declare their assets through manifests.

The refactor introduced a regression corpus that compares per-step observable readouts against a saved baseline. This is a useful distinction: internal state representations can change during a refactor, so cross-version compatibility is checked through observable behavior; repeatability within the current implementation is checked through digest sequences. A separate script checks for selected mechanic-specific patterns leaking into kernel files.

**Why this stands out:** The project created explicit checks around an AI-assisted architectural change. The purity script is a targeted guard, not a general proof of architectural separation.

The notes also record that attempting several proposed packs together did not work correctly. The later workflow emphasizes one feature session per worktree. There is no measured evidence yet that the architecture reduced token spend or feature cost.

Evidence: [refactor findings](../docs/game-engine-refactor.md), [kernel](../tools/static/engine/kernel.js), [pack contract](../tools/static/packs/README.md), [regression tests](../tools/test_refactor_regression.py), [purity check](../tools/check_kernel_purity.sh).

## 4. Turning human review into a development workflow

**Challenge:** An agent completing individual coding tasks does not automatically give the human a coherent, playable feature to review.

**Solution:** The custom project manager treats the feature as the review unit. Tasks sit underneath a specification, with comments, screenshots, linked sessions, and an isolated feature worktree. The human reviews and approves; the agent performs the merge and close-out checks. Completion follows a verified merge rather than the agent declaring implementation finished.

The workflow also addresses a subtle evidence-loss problem: recordings must be preserved in the main checkout before the feature worktree is removed. Board state is owned by the main server and written through the API, reducing conflicting updates across feature branches.

**Lesson:** The notes candidly describe the overhead. Moving between the board, editor, and interactive Muse Code session discouraged discussion in the PM tool. Development was largely sequential, so the anticipated need for parallel task coordination did not materialize. A simpler board may suit this project better.

The current implementation uses YAML-backed PM state; an earlier project note describes a SQLite approach.

Evidence: [workflow contract](../plans/simple-game-engine/agent-workflow.md), [PM implementation](../tools/pm_store.py), [workflow reflections](../docs/pm-and-simple-game-engine.md).

## 5. Treating generated art as an iterative engineering process

**Challenge:** Attractive individual images are not automatically usable game assets. Tiles need consistent style, seamless edges, readable states at game scale, and reliable linkage to the renderer. GUI pieces introduce additional slicing and layout problems.

**Solution:** The asset tool records versions, prompts, references, generated outputs, judgments, and preferred candidates. Batch generation supports comparing alternatives. Session-based iteration carries prior image references so the next instruction can describe a change instead of restating the entire asset brief. Publishing appends a version rather than overwriting the previous one.

The asset driver adds concrete constraints: fill the square frame, avoid borders and rounded corners, match adjoining edges, and remain readable at 64 pixels. Actual floor and wall sprites supply visual grounding. Generation bookkeeping includes cost recording and structured reports captured during the iteration loop.

**Lesson:** Consistency depends on reference images, explicit acceptance criteria, and retained feedback. The project notes still report cumbersome interactions and manual Illustrator/Photoshop work for GUI assets; full automation was not achieved.

Evidence: [asset workflow documentation](../README.md), [asset store](../tools/asset_store.py), [asset driver](../tools/asset_driver.py), [documented GUI difficulties](../docs/pm-and-simple-game-engine.md).

## 6. A concrete example: the crumbling-tile mechanic

**Challenge:** “A tile crumbles after you cross it” sounds simple, but leaves important rules ambiguous: when damage stages advance, when the tile disappears, what happens over a void, and whether terminal states stop further updates.

**What the history shows:** The feature progressed through a dedicated test room and implementation, then repeated review fixes addressing collapse timing, a bridge soft-lock, void hazards, visible damage stages, and timer/state freezing after death or victory. Later fixes packaged the assets and regenerated art with grounding references. The feature was merged in commit `6c42d2c`.

**Why this stands out:** Human review exposed problems across rules, presentation, and state transitions. The repeated fixes provide a stronger account of the engineering difficulty than simply saying that the mechanic was implemented.

Evidence: [mechanic pack](../tools/static/packs/crumbling/main.js), [test room](../levels/mech-5-crumbling-tile-room.json), [tests](../tools/test_mech_5_crumbling_tile.py), [preserved recordings](../sessions/features/mech-5-crumbling-tile/). Relevant history includes `06c8714` (collapse timing/soft-lock), `0f18096` (void hazard), `606ebee` (stages on leaving), and `871a1e4` (terminal-state freeze).

## 7. Keeping larger levels readable and development environments manageable

Two smaller solutions are worth highlighting:

- **Fixed world scale and camera movement:** Larger maps initially raised questions about fitting the whole board into the viewport. The implementation establishes a fixed 64-pixel tile scale and moves the camera instead. Tests check scale across level sizes. This preserves the visual scale of mechanics as maps grow. See [world scale](../tools/static/engine/world-scale.js), [camera](../tools/static/engine/camera.js), and [tests](../tools/test_world_scale.py).
- **Worktree server management:** Feature isolation created multiple running servers and confusing ports. A management tool discovers worktrees and servers, reuses an existing live server, and can launch a registered worktree on an available local port. This addresses an operational cost introduced by the development workflow itself. See [manager](../tools/worktree_mgr.py) and [tests](../tools/test_worktrees.py).

## 8. Separating mechanic invention from level design

The project moved from designing each level and inventing mechanics along the way to generating a catalog of 100 candidate mechanics. The author manually reviewed candidates and enriched them with synergies, demonstrations, and teaching moments. The QA plan scopes a smaller set of 73 mechanic sanity-check features; neither count represents completed, validated mechanics.

This creates a useful experimental progression: first demonstrate an individual rule in a small teaching room, then investigate interactions and combinations, then evaluate full levels for pacing and enjoyment. It helps separate implementation failure from design failure.

**Still open:** Isolated mechanic correctness does not establish that combinations are understandable, that a level teaches effectively, or that progression stays enjoyable. Those remain the next meaningful tests of the original hypothesis.

Evidence: [planning reflections](../docs/level-and-mechanics-planning.md), [candidate catalog](../plans/level-design/candidate-mechanics/), [QA scope](../plans/qa-framework/PLAN.md).

## Suggested hackathon narrative

> I set out to test whether AI could design enjoyable puzzle levels. To make that experiment reviewable, I built a deterministic game engine, recorded and forkable play sessions, isolated mechanic rooms, and a human-reviewed feature workflow. Along the way, I found that passing unit tests and reproducible gameplay were not enough: the evidence also had to demonstrate the intended behavior. The project now provides a foundation for testing AI level design, while creative quality and pacing remain open questions.
