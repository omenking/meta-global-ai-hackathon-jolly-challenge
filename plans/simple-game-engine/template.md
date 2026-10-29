---
title: <short name>
summary: <one-line summary: what does the player (or level author) get?>
status: proposed # proposed | approved | in_progress | in_review | completed | blocked | abandoned
priority: medium # low | medium | high | urgent
requires: # other feature ids this needs
  - player-movement
unblocks: # derived as the reverse of `requires`; never stored or typed by hand
---

# Feature: <short name>

<!--
Frontmatter here mirrors the board store (plans/simple-game-engine/pm.yml),
which is the source of truth; this file is a generated export/view. The body
below is the human-readable spec. Keep the H1 title in sync with `title`
above so the file reads well in viewers that hide frontmatter.

Lifecycle: proposed → (human approves) → approved → (agent works) →
in_progress → (agent: evidence posted) → in_review → (human: Approve for
merge) → agent merges → completed. `blocked` and `abandoned` are side
states. `completed` is set only by the agent after a verified merge.
-->

## Goal

<2-4 sentences. Why does this feature exist? What player problem or game need
does it solve? Link back to `../init-plan.md` where relevant.>

## User Story

**As a** <player / level author / ...>
**I want** <capability>
**So that** <benefit / fun / progress>

## High-Level Use Case

<Describe the feature the way you'd explain it to a player, not an engineer.
Walk through the typical flow step by step.>

Example flow:

1. Player enters a level containing <thing>.
2. Player <does action> (e.g. walks onto a tile, presses against a wall).
3. Game <responds> (e.g. picks up the item, opens a path, updates the counter).
4. Player sees <feedback> and can continue toward the level goal.

## Player-Facing Behavior

<Concrete, observable rules. Each bullet should be verifiable by playing.>

- Given <situation>, when <player action>, then <game response>.
- ...

## Edge Cases & Rules

<List the "what ifs" that define correct behavior.>

- What happens at boundaries (timer at 0, inventory full, last orb, etc.)?
- What is blocked vs allowed (e.g. can't walk through walls, locked gates)?
- Restart / reset behavior (R key, restart button)?

## UI / Feedback

<What does the player see or hear? Counters, inventory slots, messages,
animations, sounds. Reference `scratchpad/full-level-ui.png` if applicable.>

- Counter / HUD element: ...
- Tile / sprite change: ...
- Sound / message: ...

## Assets & Level Data Needed

- Sprites: <e.g. `assets/published/key.png`, new color variants, ...>
- Level JSON: <new tile character / legend entry, if any>
- Sounds: <if any>

## Acceptance Criteria

<Checklist for "done". Must be testable by playing or by script.>

- [ ] <e.g. Walking onto a key tile picks it up into the first free inventory slot.>
- [ ] <e.g. Pressing against a matching lock consumes one key and clears the tile.>
- [ ] <e.g. Behavior matches the Edge Cases section above.>

## Testing

<The human reviews this declaration with the spec. Delete what does not apply.>

- Mechanics playground: <new: name the Test Level to build / reuse: name the
  existing Test Level / none: say why no playground is needed>
- What to check there: <the exact play flow that proves the mechanic>
- Record play sessions for replay: <yes — sessions are the review evidence /
  no — screenshots only, and why>

## Tasks

<!--
Implementation units, managed on the board (Feature → Task). This section is
rendered from the store on export; do not hand-edit it here. Each task is
small enough to finish and verify in one sitting and lands as one commit.
-->

- [ ] <task-id> — <title> (`proposed`)

## Out of Scope

<What this feature explicitly does NOT cover. Keeps each file small and
prevents scope creep.>

- ...

## Open Questions

<Anything undecided. Resolve before or during implementation.>

- ...
