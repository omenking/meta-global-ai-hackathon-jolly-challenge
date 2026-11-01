## Goal

Give every mechanic in the `mechanic-sanity-checks` epic (73 features, 219 tasks, currently 0 recorded sessions) a testing bar that proves the mechanic works, not just that code passes. An agent must execute the game, record play sessions, and pass an automated replay check before a feature can be reviewed. A human reviewer must be able to play back the agent's success session from the feature page without re-running anything.

## Why now — what went wrong on the base game

Evidence from `plans/simple-game-engine/pm.yml`, `sessions/`, and `plans/simple-game-engine/agent-workflow.md`:

- Sessions were recorded but prove little: e.g. `sessions/features/keys-and-locks/*.jsonl` headers carry `feature: null, task: null, branch: null, commit: null`, and most base-game sessions end `quit`, not `won`. Nothing links a session to the acceptance rule it supposedly proves.
- The workflow only says "once the engine supports it, record an agent-labelled play session" (step 5). Recording is optional in practice, and no step verifies that a recorded session replays to the same end state. Mechanic specs already promise "replay digest match" in Acceptance Criteria, but no gate enforces it.
- Human review caught what tests missed: the game menu opened the full `chip1` level instead of the 7x6 test room, and timer/sprite faults were found by playing, after unit suites were green. Unit tests drive `GameCore` under Node with scripted inputs (`tools/test_keys_and_locks.py` pattern); they never exercise the recorded-session → replay path a reviewer actually uses.
- The machinery to do better already exists and is tested: JSONL sessions (`tools/game_sessions.py`), deterministic `initialState/step/replay/stateDigest` (`tools/static/game-core.js`), time-based replay and forks (`tools/static/game-replay.js`, `tools/test_session_replay.py`), deep links `?replay=<session-id>&t=<seconds>`, and the Sessions menu in the game page. The gap is criteria and enforcement, not tooling.

## What we borrowed from skills.sh — and what we deliberately did not

Two skills were installed/previewed and read in full during planning (`playableintelligence/game-creator@game-qa`, 1.1K installs; `mengto/skills@test-playable-web-games`, 1.4K installs). Verdicts, each checked against our stack (pure deterministic `GameCore`, JSONL sessions, Node-driven unittests, `tools/capture_level.sh`):

| Borrowed idea | Source | How it lands here |
|---|---|---|
| Design-intent thresholds: assert spec magnitudes, not `> 0`; never let a no-input run pass as a win | game-qa invariant 5 | T2 gains a scripted empty-log check (must not reach `won`) and the T3 verifier asserts mechanic-specific `readout` values at annotated steps (e.g. ice: final position is the braking wall, orb count collected), not just final digest + `won` |
| Entity interaction audit: flag visible entities that interact with one side but not the other; informational, for human review | game-qa invariant 6 | A symmetry checklist in the sanity-check comment: the new tile/entity × existing mechanics (walls, orbs, locks, switches, enemies, water…). Asymmetries are flagged, not auto-failed — with 73 mechanics, unconsidered interactions are the predictable bug class |
| AI-readable state assertion (`render_game_to_text`) | game-qa invariant 4 | Already ours: `core.readout(state)`. The verifier uses it for the step assertions above; no new API |
| Test matrix + separate regressions from baseline; report expected-vs-actual with shortest useful proof | test-playable-web-games | The per-mechanic session matrix below (success / naive-failure / edge / restart) replaces a full journey matrix; the verifier report prints expected vs actual digest/readout per failing rule and splits new failures from known base-game gaps |

Rejected, with reasons: Playwright itself, screenshot pixel-diffing, Clock API, FPS/load-time tests, touch variants, axe and mute checks. Our game is a turn-based keyboard grid with no RNG, no audio, and no frame loop: time already advances only through recorded `t_ms` (stronger than Playwright Clock mocking), state equality via `stateDigest` is exact where pixel diffs are flaky against sprite art changes, and human-judged screenshots via `capture_level.sh` already exist. Importing a second test stack to re-prove determinism we already have would add flakes, not evidence.

## Success Criteria

- No mechanic feature can enter `in_review` without: (a) a passing automated replay verification, (b) at least one agent-recorded success session ending `won`, and (c) screenshot evidence, all linked on the feature.
- Every Player-Facing Behavior rule in a mechanic spec is covered by at least one named check: a unit test, a scripted session assertion, or a recorded session segment. Uncovered rules block review.
- A reviewer opening a feature page can click through to a playable replay of the success session and scrub it (`?replay=<id>&t=<seconds>`), with any level/engine/commit mismatch shown as a warning, never a silent divergence.
- The 10 completed base-game features can be retro-checked with the same verifier; known gaps (unlinked headers, `quit` endings) are reported as baseline, not conflated with new regressions.

## Approach — four evidence tiers, one hard gate

Keep the existing test style; add the missing session tier and make it blocking.

| Tier | Proves | Mechanism (existing unless noted) |
|---|---|---|
| T1 Unit | Rule logic in isolation | Node-driven `GameCore` tests per mechanic (`tools/test_<mech>.py`), incl. edge cases and purity (initial state untouched) |
| T2 Level | Teaching room is valid, reachable, and winnable — and only winnable by playing | `game_levels` checks: room loads **from the game menu path** (the base-game chip1/test-room mix-up was a menu bug, so file-loads alone do not count), mechanic tiles placed, a scripted winning log reaches `won`, and a scripted empty log does **not** |
| T3 Session replay | The recorded play actually happened, is deterministic, and shows the mechanic at spec strength | **New verifier**: replays each linked session through `GameCore.replay`; compares final `stateDigest` and the recorded `end` line; asserts `readout` values at annotated steps against spec magnitudes |
| T4 Human playback | Reviewer sees the proof | Feature page links each session with its replay deep link; reviewer plays/scrubs/forks in the game page |

The hard gate sits between implementation and review: the verifier (T3) plus a coverage check (every spec rule mapped to T1/T2/T3 evidence) must pass before the agent posts the roll-up comment and moves the feature to `in_review`. This amends step 5–6 of `plans/simple-game-engine/agent-workflow.md`; unit tests alone never satisfy the gate.

### Required sessions per mechanic (the testing criteria)

Each mechanic feature records, at minimum, these agent sessions in its teaching room (`test_level`, e.g. `mech-1-ice-tile-room`):

1. **Success session** — ends `won`; exercises every Player-Facing Behavior rule at least once; annotated at the steps where each rule fires so the verifier can assert `readout` there. This is the primary review evidence.
2. **Naive-failure session** — performs the teaching moment's naive first action and shows it failing as the spec describes (blocked, slid past the orb, deadlock, or restart), proving the room teaches and the rule has teeth. Ends `quit` or `lost` with an annotation naming the rule.
3. **Edge sessions** — one per Edge Cases & Rules bullet that is playable (boundary, blocked move, restart restores mechanic state). Small rooms may fold edges into the success session if each is annotated with `step` + label; otherwise separate sessions.
4. **Determinism is checked, not claimed** — the verifier replays 1–3 and requires digest equality. A session that does not replay identically fails the gate regardless of screenshots.

Session header requirements (fixing the base-game gap): `created_by: "agent"`, `feature`, `task`, `branch`, and `commit` all populated; `level_source.hash` and `engine_version` present (already emitted by the recorder). Sessions are preserved under `sessions/features/<feature-id>/` before any worktree removal, per the existing workflow rule.

### Coverage mapping and interaction audit

Each feature's sanity-check task carries two tables in its completion comment. First, rule → evidence: rule text (from Player-Facing Behavior / Edge Cases), tier, test name or session id + step range. The reviewer checks the table, not raw files. Second, the interaction audit: new mechanic × each existing mechanic family it can meet in a room, marked `interacts / blocked-by / passes-through / n-a`, with any asymmetry flagged for the human (informational; only a spec contradiction blocks). The template in `plans/simple-game-engine/template.md` (Testing section) gains both tables so future mechanics are born with them.

## Steps

1. **Verifier script** — add `tools/verify_mechanic_qa.py` (plus `tools/test_verify_mechanic_qa.py`): given a feature id, load its linked sessions from `pm.yml` via the API/store read path, replay each through Node `GameCore`, assert digest + `end`-line agreement, assert `readout` at annotated steps matches the spec magnitudes declared in the sanity-check task, assert header linkage (`feature`/`task`/`commit` set, `created_by=agent`), assert ≥1 `won` session, ≥1 naive-failure session, and the T2 empty-log check for the teaching room. Print a per-rule report with expected vs actual on failure, split into new failures vs known baseline gaps; exit non-zero on any new failure. Reuse `game_sessions.parse_session`, `version_warnings`, and the Node harness pattern from `tools/test_session_replay.py`.
2. **Recorder linkage fix** — ensure sessions started from a feature context carry `feature`/`task`/`branch`/`commit` (game page already accepts creator/feature context; wire the worktree playtest launch to pass them, and backfill nothing — old sessions stay as-is and the verifier reports them as unlinked baseline).
3. **Workflow amendment** — update `plans/simple-game-engine/agent-workflow.md` step 5–6: recording the three session classes is mandatory for playable changes; the roll-up comment must include the verifier output, the rule → evidence table, and the interaction audit; `in_review` requires a green verifier run. Add both tables to the Testing section of `plans/simple-game-engine/template.md` and to the three task acceptances pattern used by mechanic features (`test-level`, `implement-mechanic`, `sanity-check` — sanity-check cannot complete without verifier green).
4. **Review playback surface** — on the PM feature page, render each linked session with result, creator, duration, and a Replay link (`/static/game.html?replay=<id>`) using the existing deep-link support; surface `version_warnings` (level/engine/commit mismatch) on the replay view so stale proof is visible. No new player: reuse `game-replay.js` scrub/speed/fork.
5. **Retro-check base game** — run the verifier over the 10 completed `base-game` features; file the report (expected findings: unlinked headers, `quit`-only sessions for `game-shell`/`game-engine-refactor`/`fixed-world-scale`) as a comment on each feature, marked baseline. Do not re-open completed features; the report seeds any follow-up fixes as new tasks.
6. **Pilot on one mechanic** — run the full criteria on `mech-1-ice-tile` end to end (teaching room, three session classes, verifier green incl. readout step-assertions for slide-to-wall and orb collection, interaction audit vs walls/orbs/restarts, human playback) before applying the gate to the remaining 72.

## Validation Plan

- `python3 -m unittest tools.test_verify_mechanic_qa -v` — verifier passes a known-good session fixture and fails on: tampered input log (digest mismatch), `quit`-only session set, missing header linkage, level-hash mismatch, a weakened mechanic fixture (slide stops one tile short — digest still matches itself, so only the readout step-assertion can catch it), and a teaching room whose empty log reaches `won`.
- `python3 tools/verify_mechanic_qa.py mech-1-ice-tile` — exit 0; report shows success session replay digest match, naive-failure session present, readout assertions green, every spec rule mapped.
- Full suite: `python3 -m unittest discover -s tools` — no regressions beyond the 2 known pre-existing `test_pm_review_ui` failures (confirm they fail identically on untouched `main`).
- Manual playback check: open the pilot feature page on `http://127.0.0.1:8321`, follow the Replay link, scrub to a mid-session `t`, fork and finish the room by hand; confirm the fork records a new human session and the original is untouched.
- Negative check: deliberately break one pilot session's input log on a scratch copy and confirm the verifier fails and the feature cannot be presented as ready (report shows the failing rule with expected vs actual).

## Risks / Open Questions

- Recorder header linkage (step 2) needs the game page launch to know feature/task/commit; if the worktree game URL cannot carry them, fall back to linking at upload time via `POST /api/pm/features/<fid>/sessions` with the commit filled in there — verifier reads the store, not only the JSONL header. Decide in step 2; either satisfies the gate.
- Readout step-assertions need spec magnitudes written as checkable values (positions, counts) in each sanity-check task. Most mechanic specs already state them in prose ("stops at the wall", "orbs on the line are collected"); the pilot on `mech-1-ice-tile` sets the pattern for phrasing them. If a rule cannot be made checkable, it stays human-playback-only and is marked so in the table — never silently dropped.
- 73 mechanics × 3+ sessions is a lot of stored JSONL; sessions are small (one line per input), so keep all of them — they are the review evidence. Revisit only if `sessions/` growth becomes a problem.
- Non-goals: synergy rooms (explicitly deferred in the epic), CI hosting (verifier runs locally exactly like the current unittest suites), re-recording base-game sessions (retro-check reports only), and any Playwright/browser-automation stack (see borrowed/rejected table).
- Highest-risk step: step 1's digest comparison — it must compare the same state projection the browser shows (`readout`/digest from `game-core.js`), or green verifiers will still diverge on playback. Mitigate by reusing the exact Node harness from `tools/test_session_replay.py`, which already asserts recorded-vs-live digest equality.
