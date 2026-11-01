---
name: Colours Beyond the Screen
goal: |
  teach the player that keys only open their own colour,
  and that a level can be bigger than the screen.
status: candidate
---

## Lessons Learned
- a red key only opens a red lock, a blue key only opens a blue lock
  - pressing a lock with the wrong colour does nothing
  - the wrong key is not consumed
- the player can hold more than one key at a time
  - each key takes its own inventory slot
- a level can be bigger than the screen
- when the player walks, the camera follows
  - tiles and the player stay the same size
  - only how much of the level is visible changes
- orbs can be off-screen, the orbs-left counter says how many are left to find
- collecting orbs still opens the gate to the warp tile
- the warp tile still sends the player to the next level

## Level Concept

A long level, about two screens wide, the first one
that doesn't fit in view. The player collects six orbs,
one red key and one blue key.

The start fits on the first screen. Both keys sit in the
open near the start, so the player picks them both up
first. A red lock blocks the way out where the player
can see it, so colour matching is taught in view first:
use the red key, keep the blue key for later.

Past the red lock the path runs one way in a gentle
snake, so the player keeps walking and the level
scrolls with them. Orbs are spread along the path, a
few only coming into view as the player gets close.

Near the end a blue lock blocks the gate chamber, so
the player uses the blue key they have been carrying
beyond the first screen. The last orbs in that chamber
open the gate to the warp tile.

There is no branching, so the player cannot get lost,
and a wrong press does nothing, so they cannot get
stuck, only learn that colours have to match.

The timer stays generous, since this level is about
looking and matching, not rushing.
