---
name: Keys Open Doors
goal: |
  teach the player the second basic mechanic,
  pick up a coloured key to dissolve its matching lock.
status: accepted
human_feedback: 
  - fixed-level-name: |
     with the exception for the first level, levels should be named based on what they do. So this level teaches key use, and the level name be "Keys Open Doors" not "Second Level". We don't need to put the word level in our name.
---

## Lessons Learned
- picking up a key puts it in an inventory slot
- pressing against a lock with the matching key dissolves the lock
  - the key is consumed
  - the lock tile becomes walkable floor
- pressing against a lock without the matching key does nothing
- collecting orbs still opens the gate to the warp tile
- the warp tile still sends the player to the next level

## Level Concept

A small level, only slightly larger than the first.
The player collects four orbs and one red key.

The direct path to the gate is blocked by a red lock.
The red key sits in a short side alcove off the main
path, so the player has to detour to fetch it, come
back, and dissolve the lock to get through.

One lock and one key only. No other colours yet, so
there is no wrong-colour choice to get wrong.

The whole level is in view, as we still aren't
introducing camera movement yet.

The level is still simple. It builds on the first
level rather than replacing it, and only adds the
one new idea of keys and locks.
