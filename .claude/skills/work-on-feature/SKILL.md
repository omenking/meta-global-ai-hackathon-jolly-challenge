---
name: work-on-feature
description: Work on, review, or merge a simple-game-engine feature through the project-manager board. Trigger on prompts like "work on <feature-id>", "feature <id> is ready for review", "merge approved features", or "close out <feature-id>".
---

# Work on a feature (project manager)

Immediately read `plans/simple-game-engine/agent-workflow.md` in full and
follow it exactly. That file is the canonical contract: the 8-step
pickup → claim → worktree → implement → evidence → roll-up →
review-fixes → merge workflow, the API calls, the commit format
(`<feature-id>/<task-id>: <summary>`), the screenshot procedure, and the
hard rules (never hand-edit `pm.yml`, never start an unapproved feature,
never work an already-`in_progress` task, never mark a feature
`completed` — only a verified agent-performed merge does).

Do not improvise a different workflow. If the board server does not
answer after the start/check procedure in that file, stop and report.
