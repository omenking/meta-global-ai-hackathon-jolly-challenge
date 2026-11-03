# Jolly's Challenge — TL;DR Summary

Aggregated from [Claude report](./claude.md), [Codex report](./codex.md), and [Wonder report](./wonder.md) (26 Oct – 3 Nov 2026). Read the linked reports for evidence, file paths, and commit history.

## TL;DR

Jolly's Challenge set out to test whether an AI agent can design fun, well-paced puzzle levels, using a small Chip's Challenge-style tile game (guide Jolly, collect orbs, open the gate, reach the portal before the timer ends) built in 10 days under a self-imposed $150 Meta API budget, Muse Image 1.0-only art, and Muse Code-only development. The project shipped a complete base game and, more significantly, the measurement infrastructure needed to judge AI level design at all: a deterministic engine, replayable play sessions, isolated test rooms per mechanic, a human-gated feature workflow, and grounded AI art generation. All three reports agree on the verdict: mechanic correctness is now provable, but fun and pacing at full-level scale remain unproven — the apparatus to answer the original question exists, the level-scale experiment itself comes next.

## At a glance

| Measure | Value |
|---|---|
| Commits on `main` | 113 |
| Base-game features completed | 10 (shell, movement, replay, timer, keys/locks, orbs/gate, warp, HUD, refactor, fixed scale) |
| Candidate mechanics designed | 100 across 10 YAML families → 73 sanity-check features (219 tasks) on the board |
| Board totals | 84 exported feature specs, ~302 tasks, ~75 feature worktrees |
| Automated tests | ~270 Python cases in `tools/test_*.py` |
| Cost | ~$5–10 per base-game feature; ~$0.01/image; $0.04 for a grounded 4-image tile run |

Small count differences between reports reflect scope, not disagreement: 219 tasks counts only the sanity-check programme, 302 counts the whole board.

## What was built

- **Game:** Deterministic tile engine (pure `step` from recorded `t_ms`, never wall-clock) with JSONL session recording, time-based replay with scrub/annotate/fork and deep links, fixed 64px world scale with a translating camera, and a kernel + registry + mechanic-packs architecture.
- **Tools (one server, `tools/server.py`):** Project manager board (React/HeroUI + Vite), iterative asset design tool, level preview with headless screenshot compare, game page, and worktree manager.
- **Pipelines:** `scripts/gen-image` (Muse Image via OpenAI SDK), `meta-costcenter` + `meta-keyguard` budget kill-switch, asset driver, and `verify_mechanic_qa.py` review gate.

## Top challenges solved (consensus across all three reports)

1. **Hard budget enforcement.** Cost Center + Keyguard with a Muse hook and per-call image reporting revoke the project key at $150 — a kill-switch, not a dashboard. Key labels matter: unlabelled spend is counted but not stoppable.
2. **Image generation without agent image access.** `gen-image` wraps the API behind one tested script. Key discovery: `size` sets aspect ratio only (512 request → 1600px output), fixed by local ffmpeg resize keeping the `-orig` file. Caught by an independent second-model review.
3. **Fake iteration in art.** Three floor-tile versions sent byte-identical prompts (complaints lived in descriptions/judgements the model never saw; parent image never sent). Fixed with verbatim-prompt display, identical-prompt guard, checklist-driven prompt builder, 1–10 image "lottery" runs, and multi-turn sessions that emulate provider context via carried reference images.
4. **AI art that passed its own judging.** Ungrounded stone + hairline cracks invisible at 64px. Fixed by two grounding rules: always pass real floor/wall sprites as references (edit the floor itself for staged damage), and judge downscaled at 64px with bold 8–12px marks, final check in-room. Every verdict is kept in YAML run reports.
5. **Reproducible play as evidence.** Determinism + JSONL sessions (header with level hash/engine/feature/commit, one line per input) make replay a recomputation. Review fixes that mattered: sessions start on first move, finished runs freeze timer/state.
6. **Passing tests ≠ working mechanic.** Base-game sessions had null linkage, mostly ended `quit`, and never verified replay; humans caught menu/timer bugs green suites missed. New 4-tier model (unit → level-through-menu → session replay with digest + step readout assertions → human playback) with a hard verifier gate. Core insight (stressed by Codex): a broken mechanic replays its own wrong result perfectly — digest equality alone proves nothing.
7. **Monolith → kernel + packs.** Audit-first, pressure-tested (water, button/trap, monster, ice) before coding; phased, always-playable migration guarded by a golden regression corpus (observable readouts) and a kernel-purity gate (30 → 0 mechanic literals). Keys/locks extracted first as proof; packs are folders (`main.js` + manifest + assets).
8. **Soft-locks found only by adversarial play.** Crumbling tile (7 review-fix rounds) is the worked example: fall-on-leaving, void-as-hazard, stage timing, terminal freeze. Project rule that followed: a reachable state with no legal move and no lose/reset is a failure however well the solution path plays — every mechanic needs solution + adversarial + boundary + restart/replay cases.

## Workflows worth reusing

- **Plan before code:** agent writes a plan file, human annotates inline, then implement (refactor, QA, asset driver).
- **Feature as the PR:** 1 feature = 1 branch = 1 worktree, 1 task = 1 commit, 8-step contract in `agent-workflow.md`; human approves, agent merges only after verification; agent never self-approves or hand-edits board state; preserve sessions before deleting worktrees.
- **Evidence over assertion:** headless screenshots from the worktree build + linked replayable sessions + verifier report + rule→evidence table + interaction audit on every mechanic.
- **Test room + teaching moment per mechanic:** small room where the obvious first action fails cheaply and recovery teaches the rule; naive-failure session is required evidence.
- **Find a skill when stuck:** interface/usability skills fixed the replay UI after HeroUI-overlay and Leva attempts failed; game-QA skills informed the QA tiers (with explicit rejections — no Playwright/pixel-diff/clock-mock needed for a deterministic grid).
- **Write the lesson into the contract:** workflow file, feature template, mechanic schema (definitions/synergies vs demos/teaching moment/test cases), grounding doc, pack convention — so the next session cannot repeat the failure.
- **One feature per session:** parallel pack attempts (4 at once) all failed; sequential + human review won. Worktree sprawl then needed its own manager (list/start/stop servers, never delete).

## Where the reports differ (read with care)

- **Confidence level:** Claude and Wonder describe the QA gate and workflows as operating practice; Codex is more cautious, noting it is a retrospective (not a fresh test run), that some QA/PM improvements are uncommitted, and that universal enforcement across all 73 mechanics and any token-cost saving from packs are not yet measured. Treat "gate exists and is piloted" as proven, "gate enforced everywhere" as to-verify.
- **Emphasis:** Claude is the most complete challenge-by-challenge catalogue (13 challenges, costs, hashes). Codex is the shortest and most evaluative — best hackathon narrative and caveats. Wonder is the longest and most architectural — best on contracts, session emulation detail, and cross-cutting workflow analysis.
- **Model finding (agreed, differently framed):** Spark xhigh struggled with UI; Wonder low/medium was cheaper and better for that class of work and for writing image prompts (Muse Image 1.0 is very literal; with good prompts, quality rivalled GPT Image 2.5, but cross-tile style consistency stayed hard). Whether Spark or Wonder should drive feature work, and at what effort, is explicitly left open.

## What remains open

- **The original question:** can the agent sequence verified mechanics into fun, well-paced levels? Early roadmap evidence is mixed and human-assisted (L1 human template, L2 AI-authored after rename, L3 two AI candidates merged by human). Synergy rooms and composed levels under session-based scrutiny are next.
- **Art consistency & GUI:** reference-screenshot-then-extract and unified tileset ideas untested at budget; precisely-sliced HUD art still needed manual Illustrator/Photoshop finishing. Jolly animation remains exploratory.
- **Process fit:** PM tool likely over-built for the sequential workflow that actually happened (board comments lost to chat; consider simpler board or GitHub hooks); pack cost benefit unmeasured; engine port / 3D deferred — PixiJS stays for now.

**One-line narrative (after Codex):** To test whether AI can design enjoyable levels, the project built a deterministic engine, forkable recorded play, isolated mechanic rooms, and a human-reviewed feature workflow — and learned that reproducible, test-passing play is not enough: evidence must demonstrate intended behaviour. Creative quality is now measurable; it is not yet demonstrated.
