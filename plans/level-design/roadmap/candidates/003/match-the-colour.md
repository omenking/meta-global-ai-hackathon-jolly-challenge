---
name: Match the Colour
goal: |
  teach the player that keys only open their own colour,
  carry more than one key, and pick the right one.
status: rejected
human_review: I think we can roll up both beyond-the-screen and match-the-colours into a single candidate
rolled_into: colours-beyond-the-screen
---

## Lessons Learned
- a red key only opens a red lock, a blue key only opens a blue lock
  - pressing a lock with the wrong colour does nothing
  - the wrong key is not consumed
- the player can hold more than one key at a time
  - each key takes its own inventory slot
- collecting orbs still opens the gate to the warp tile
- the warp tile still sends the player to the next level

## Level Concept

A small level, about the same size as Keys Open Doors.
The player collects five orbs, one red key and one blue key.

Both keys sit in the open near the start, so the player
picks them both up first. Two locks block the way on,
a red lock and a blue lock in sequence, so the player
has to use each key on its matching lock to get through.

Colour is the puzzle. There is no wrong key to waste,
since a wrong press does nothing, so the player cannot
get stuck, only learn that colours have to match.

The whole level is in view, as we still aren't
introducing camera movement yet.

The level adds choice to Keys Open Doors rather than
a new movement idea, and still only asks the player
to learn one new thing.
