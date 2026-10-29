# Agent Workflow — working features through the project manager

This file is the canonical contract for Muse Code working on the
simple game engine through the project-manager tool. The project skill
(`work-on-feature`) only triggers and loads this file; if the two ever
disagree, this file wins. There is no driver script: a human prompts you
interactively and you use your normal tools (files, shell, git) plus the
project-manager HTTP API.

Finding on skill discovery (Step 4): the repo previously had no project
skill directory. The skill lives at `.claude/skills/work-on-feature/SKILL.md`,
following the `SKILL.md` convention (YAML frontmatter with `name` and
`description`, body loaded on trigger) used by the skills installed for
this project. If your Muse Code build discovers project skills in a
different directory, move that one folder; this contract file does not move.

## Board facts

- The store is `plans/simple-game-engine/pm.yml`, owned by `tools/server.py`.
  Never hand-edit it, and never commit it (or `features/*.md` exports, or
  `screenshots/`) on a feature branch. Read and write board state only
  through the API.
- One feature = one branch `feat/<feature-id>` = one worktree at
  `.worktrees/<feature-id>` (gitignored), reused for all its tasks.
- One task = one commit on the feature branch. The feature, rolled up in
  the web UI, is the review unit (our "PR"). There are no GitHub PRs.
- Feature lifecycle: `proposed` → (human approves) → `approved` → (you
  claim the first task) → `in_progress` → (all tasks evidenced) →
  `in_review` → human **Approve for merge** or **Request changes** →
  you merge promptly → `completed`. Task lifecycle: `proposed` →
  `approved` → `in_progress` → `completed`; `blocked` / `abandoned`
  are side states. Tasks have no `in_review` stage: they are
  agent-managed, so when you report a task done it is `completed`
  (posting `in_review` is stored as `completed`). The human inspects
  task-level code and commits directly; only the feature sits in
  `in_review`. Review happens on the feature page
  (`/pm/features/<feature-id>`) — there is no separate review page.
- Deep links into a replay are time-based: `?replay=<session-id>&t=<seconds>`
  (the step index is derived from the recorded `t_ms`).

## Server start / check

Board writes go through the single server on the main checkout
(`127.0.0.1:8321` by default). Before any API call:

```sh
curl -s http://127.0.0.1:8321/api/pm/features >/dev/null || \
  (cd <main-checkout> && source .venv/bin/activate && \
   nohup python tools/server.py >/tmp/pm-server.log 2>&1 &)
curl -s http://127.0.0.1:8321/api/pm/features   # must answer JSON
```

If the server still does not answer, stop and report that; do not
improvise by editing `pm.yml` directly.

## API quick reference (base `http://127.0.0.1:8321`)

```sh
B=http://127.0.0.1:8321/api/pm
curl -s $B/features/<feature-id>                       # feature + tasks + progress
curl -s $B/features/<feature-id>/rollup                # review roll-up
curl -s -X POST $B/features/<fid>/tasks/<tid>/claim -H 'Content-Type: application/json' \
  -d '{"author":"agent","body":"Starting: <plan>. Verify: <how>."}'
curl -s -X POST $B/features/<fid>/tasks/<tid>/move -H 'Content-Type: application/json' \
  -d '{"status":"completed"}'
curl -s -X POST $B/features/<fid>/tasks/<tid>/comments -H 'Content-Type: application/json' \
  -d '{"author":"agent","body":"...","attachments":["screenshots/features/<fid>/x.png"],"session_refs":[{"id":"s1","path":"sessions/...","level":"chip1","created_by":"agent","result":"won"}]}'
curl -s -X POST $B/features/<fid>/comments -H 'Content-Type: application/json' \
  -d '{"author":"agent","body":"..."}'
curl -s -X POST $B/features/<fid>/evidence -H 'Content-Type: application/json' \
  -d '{"filename":"shot.png","data_b64":"<base64>"}'   # returns the stored path
curl -s -X POST $B/features/<fid>/sessions -H 'Content-Type: application/json' \
  -d '{"id":"s1","path":"sessions/...","level":"chip1","created_by":"agent","result":"won"}'
curl -s -X POST $B/seed                                 # idempotent seeding
curl -s -X POST $B/export                               # regenerate features/*.md
```

Authorship: your comments use `"author":"agent"`. Agent comments are
read-only in the UI; never try to edit or delete them.

## The 8 steps

1. **Point and pick up.** The human prompts e.g. "work on `keys-and-locks`".
   Fetch the feature (`GET /api/pm/features/<id>`). Check it is
   human-`approved` — an AI-created feature sits at `proposed` until a
   human approves it; if it is not approved, do not start: offer to flesh
   out the spec instead. Check `requires` features are `completed`;
   unmet requires warn but never block — surface the warning in chat and
   in your claim comment. Select the first open task in `order` unless
   one was named.
2. **Claim.** `POST .../claim` (sets `in_progress` and, with `body`,
   posts your agent comment stating what you will do and how you will
   verify it). Already `in_progress` means another session owns it:
   stop and tell the human. Never work an already-claimed task.
3. **Isolate.** Create the feature worktree once, reuse it for every task:

   ```sh
   git worktree add .worktrees/<feature-id> -b feat/<feature-id> main
   # later tasks: cd .worktrees/<feature-id> (it already exists)
   ```

   Branch from committed `main` only. All code work happens inside the
   worktree. Never commit `pm.yml`, `features/*.md`, or `screenshots/`
   on the feature branch.
4. **Implement and verify one task at a time.** Read the feature spec and
   the task `acceptance`. Make the smallest change. Run verification:
   unit tests (`python -m unittest discover`-style repo suites as named
   in the task), and for playable changes run the game from the worktree
   on a spare port and play the flow, including the feature's Test Level
   / mechanics playground where the task calls for one. Existing repo
   tests must still pass. Every mechanic must preserve determinism:
   state advances only through the pure step function, inputs carry
   `t_ms`, and no mechanic may read unrecorded wall-clock time.
5. **Evidence and commit.** For any visual or playable change, capture
   screenshots of the worktree build (see below) and, once the engine
   supports it, record an agent-labelled play session of the Test Level.
   Upload screenshots (`POST .../evidence`), then post the completion
   comment with the returned paths in `attachments` and the session in
   `session_refs`. One commit per task on the feature branch:

   ```sh
   git -C .worktrees/<feature-id> add -A
   git -C .worktrees/<feature-id> commit -m "<feature-id>/<task-id>: <summary>"
   ```

   Then `POST .../move` to `completed` (or include the status in your
   completion update) with a comment: what changed, the commit hash,
   exact test evidence, attached proof. If blocked instead: move to
   `blocked`, comment what is needed, tell the human in chat, and leave
   the worktree in place.
6. **Roll up for review.** When all of a feature's tasks are `completed`,
   set the feature `in_review` (`PUT /api/pm/features/<id>`) and post a
   feature-level agent comment using the template below. Starting the
   Test Level itself happens in the game's own menu; your comment only
   identifies `test_level` and links the worktree build's game URL.
7. **Changes requested → review-fixes.** The human's **Request changes**
   records `review.decision = changes_requested` (comment required). Find
   it via `GET /api/pm/features/<id>` — you do not need the human to
   re-prompt with details. Create a distinct task `review-fixes-1`
   (then `-2`, …) with `"kind":"review-fixes"` holding the requested
   changes as description/acceptance, work it through steps 2–5 in the
   same worktree, and return the feature to `in_review`. Never rewrite
   the original tasks' history.
8. **Approve, merge, close out.** The human playtests and clicks
   **Approve for merge** (`review.decision = approved_for_merge`). On
   their merge prompt (or upon seeing that decision), merge promptly —
   see the merge checklist. Only after the merge verifies on `main` do
   you record it (`POST /api/pm/features/<id>/merge` with the merge
   commit), which sets feature and tasks `completed`. Never mark a
   feature `completed` yourself by any other route, and never approve
   your own feature.

## Feature roll-up comment template (step 6)

```markdown
Ready for review: <feature title> (<n>/<m> tasks completed)

Tasks:
- <feature>/<task>: <title> — <status>, commit `<hash>` — <one-line result>

Evidence:
- Screenshots: <attached; gallery on the feature page>
- Sessions: <id> (<level>, <created_by>, <result>) — replay: <game-url>?replay=<id>&t=<seconds>

Playtest:
- Worktree: `.worktrees/<feature-id>`
- Start: `cd .worktrees/<feature-id> && source .venv/bin/activate && python tools/server.py --port <spare-port>` — use `<spare-port>`, board server stays on 8321
- Game: http://127.0.0.1:<spare-port>/static/game.html — open the Test Level `<test_level>` from the game menu; linked sessions replay from the Sessions menu.
```

## Screenshot procedure

```sh
# Preview page (existing behaviour):
bash tools/capture_level.sh chip1
# Game page from a worktree build on its spare port, filed as evidence:
bash tools/capture_level.sh --page game --feature <feature-id> \
  --url http://127.0.0.1:<spare-port> <test-level>
```

Captures land in `screenshots/features/<feature-id>/` with `--feature`.
Upload the file (`POST .../evidence`, base64) and reference the returned
`screenshots/features/<feature-id>/...` path in your comment's
`attachments`. Screenshot evidence is kept after close-out. Before
removing a worktree, copy linked session files into the main checkout's
`sessions/features/<feature-id>/` and post the surviving paths — sessions
recorded only inside a deleted worktree are lost.

## Merge and close-out checklist (step 8)

Run from the **main checkout**, promptly, one feature at a time:

1. Confirm `review.decision` is `approved_for_merge` via the API.
2. `git merge --no-ff feat/<feature-id>` into `main` (merge commit,
   preserving per-task commits).
3. Resolve conflicts yourself. If a conflict cannot be resolved safely,
   stop, report exactly what conflicts and why, and leave branch and
   worktree intact. Never guess through an unsafe conflict.
4. Run the repo test suites and a game smoke check on merged `main`.
   If anything fails, stop and report; do not record the merge.
5. Preserve evidence: linked sessions copied to
   `sessions/features/<feature-id>/` (screenshots already live on main).
6. Record the merge: `POST /api/pm/features/<id>/merge {"commit":"<merge-hash>"}`
   (sets feature + tasks `completed`), post closing comments, and
   `POST /api/pm/export`.
7. Clean up: `git worktree remove .worktrees/<feature-id>` and
   `git branch -d feat/<feature-id>`.

The human never runs git merges. If the merge conflicts or tests fail
on `main`, stop, report, and leave the branch/worktree intact.

## Hard rules

- Never hand-edit `pm.yml`; board state only through the API, only from
  the main-checkout server.
- Never commit `pm.yml`, `features/*.md`, or `screenshots/` on a
  feature branch.
- Never start an unapproved (`proposed`) feature.
- Never work an already-`in_progress` task.
- Never mark a feature `completed`; only a verified merge does that,
  via `POST .../merge`. Never approve your own feature.
- Stop and report on unsafe merge conflicts or failing tests on `main`.
- One Muse Code session per feature worktree; never two sessions
  in one worktree or branch.
- Preserve linked session files on `main` before removing a worktree.

## Example human prompts

- "work on `keys-and-locks`"
- "work on `keys-and-locks` / `key-pickup`"
- "feature `keys-and-locks` is ready for review" (finish roll-up, step 6)
- "merge approved features" (step 8 for each `approved_for_merge`)
- "close out `keys-and-locks`" (merge + cleanup, step 8)
