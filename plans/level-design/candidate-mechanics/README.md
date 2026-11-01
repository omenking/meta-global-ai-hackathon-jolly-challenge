## Candidate Mechanics

- needs to clearly describe its mechanics under its `mechanics` property
- needs to propose `syngeries` under that property with others to help figure out possible additional test rooms or a final level idea.

## Properties

- `mechanics`: a list, one rule per item, saying exactly what the mechanic does, including which tiles it can and cannot interact with.
- `synergies`: combinations that create new gameplay when combined. The two mechanics must interact to produce an effect or decision neither gives on its own, for example an ice block pushed onto ice becoming a movable braking wall. Merely appearing in the same room, being an alternative to each other, or being compared do not count.
- `demos`: comparisons used for teaching. A demo puts two mechanics side by side, before and after, or in a contrast room so the player learns how they differ, for example a push block that cannot bridge next to a dirt block that can. A demo creates no new combined mechanic, it only teaches. Use `demos` only where a comparison helps a test room teach.
- `teaching_moment`: the designed first encounter with a mechanic, written as a single scenario. It states how the room is set up, what a player who has not yet understood the mechanic is likely to do, how that action fails, and how the player recovers, because the recovery is what turns the failure into the lesson.

## Teaching moments

A teaching moment differs from a demo in the way the player receives the information. A demo shows the player a comparison and allows the difference to be observed, whereas a teaching moment allows the player to act on an incomplete understanding and discover the rule through the consequence, so the first room for a mechanic should arrange for the obvious action to fail in a way that makes the missing rule visible. In Chip's Challenge, for example, a first dirt block room of this kind gives the player enough blocks to cross only if they are placed in the right order, which means that a player who pushes the nearest block into the water without thinking will spend it in the wrong place, will be unable to finish the crossing, and will have to restart a small room in order to try the other order.

Because the purpose of the failure is instruction rather than punishment, the failure has to satisfy several conditions at once. It should happen soon after the mechanic is introduced, it should be attributable to the one rule the room is teaching rather than to unrelated pressure, and it should cost a restart of a small room or a return to a checkpoint rather than the loss of a long attempt, since a player who has to replay a large amount of known content in order to retry a single decision will usually learn to resent the room instead of learning the rule. The room should also be arranged so that the correct action succeeds immediately once the player has understood the failure, because the contrast between the failed first attempt and the successful second attempt is the evidence the player uses to confirm what the mechanic actually does.
