# Push block

Draft for mech-81-push-block. The live PM spec is unchanged.

## Goal

Try the push block in a teaching room before using it in real levels. It lets the player hold a switch down or block an enemy’s path. Unlike dirt and ice blocks, it cannot fill or cover hazards.

## User Story

I can move a block into a useful position, but I need to plan my pushes because I cannot pull it back.

## High-Level Use Case

The room has one block near a wall and a switch across the room. The obvious first push traps the block against the wall, leaving no way to reach the switch.

After restarting, the player takes a different route and pushes the block onto the switch. The lesson is to think about where a block will end up before moving it.

## Player-Facing Behavior

Walk toward the block from any side to push it one tile. It moves only when the destination is empty floor or a floor or weight switch. Pushing must never pick it up.

A block on a switch holds it down until moved away. Enemies cannot pass through the block.

## Edge Cases & Rules

Walls, locks, closed gates, other blocks and enemies prevent a push. Water, deep water, void, fire and lava do too. When a push is blocked, both the player and block stay in place.

The block cannot be pulled. Restart restores the room to its initial state, including the block’s position. Recorded input must replay to the same end state.

## UI / Feedback

The block should visibly fill its tile and remain on the map when pushed. Its position should make it clear when it is holding a switch down.

If the player traps it, Restart must remain available.

## Assets & Level Data Needed

Use the test map mech-81-push-block-room. Reuse existing tiles where possible and confirm any new sprite or tile definition before implementation.

The source is mechanic #81 in plans/level-design/candidate-mechanics/blocks.yml.

## Acceptance Criteria

The room is ready for review when the correct route is completable, the obvious first push demonstrates the trap, and every movement and blocking rule above has been verified.

Pushes work from all four sides without picking the block up. The artwork fills its tile. Restart restores the initial setup.

Attach a room screenshot and link recorded agent play sessions as evidence.

## Out of Scope

Additional synergy rooms, comparison rooms with other block types, and use in production levels are deferred. This trial does not add hazard filling.

## Open Questions

The original spec requires floor and weight switch support but also defers floor-switch synergy testing. Is the intended boundary to include the teaching-room switch interaction and defer additional rooms?

It also mentions both manual Restart and automatic return to a checkpoint after failure. Should trapping the block require a manual restart, or trigger an automatic one?

Does this mechanic need any new tile definitions or HUD feedback beyond the visible block and switch?

## Testing

Play the teaching room through the game. Record agent sessions for a successful solution, the trapped-block attempt, and edge cases. Check each rule above, including pushes from every side, blocked destinations and restarting.

Verify that replay reaches the same end state. Core tests support this evidence but do not replace recorded play sessions.
