---
name: Beyond the Screen
goal: |
  teach the player that a level can be bigger than the screen,
  the camera follows, and orbs can wait off-screen.
status: rejected
human_review: I think we can roll up both beyond-the-screen and match-the-colours into a single candidate
rolled_into: colours-beyond-the-screen
---

## Lessons Learned
- a level can be bigger than the screen
- when the player walks, the camera follows
  - tiles and the player stay the same size
  - only how much of the level is visible changes
- orbs can be off-screen, the orbs-left counter says how many are left to find
- collecting orbs still opens the gate to the warp tile
- the warp tile still sends the player to the next level

## Level Concept

A long level, about two screens wide, the first one
that doesn't fit in view. The player collects six orbs
and one red key.

The path runs one way in a gentle snake, so the player
keeps walking and the level scrolls with them. Orbs are
spread along the path, a few only coming into view as
the player gets close. One red lock blocks the path
near the end, and its red key sits just before it, so
keys work the same as in Keys Open Doors.

There is no colour choice and no branching, so the
player cannot get lost. The only new thing to learn
is to keep exploring past the edge of the screen.

The timer stays generous, since this level is about
looking, not rushing.
