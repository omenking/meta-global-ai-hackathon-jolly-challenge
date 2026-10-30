You are auditing an existing PixiJS + plain JavaScript codebase. This is a Chip's Challenge clone.

DO NOT WRITE OR MODIFY GAME CODE YET. Your only output is a high-level refactoring plan saved as REFACTOR.md.

Current situation:
- The game works, but logic lives in large monolithic files with loose functions.
- Existing mechanics: timer, orb collection, gate that opens when all orbs are collected, warp.
- Keys and locks were added on top later and are likely coupled into the core code.
- Goal: make it easy to add novel mechanics as additive "packs" (like a mod system). I don't need true external mod support/security, just a clean internal extension structure.

Your task - inspect the codebase first, then produce REFACTOR.md with:

1. CURRENT ARCHITECTURE MAP
   - Entry point, main loop, where game state lives, where movement/collision/pickup/warp/gate/timer/rendering/HUD/input are handled.
   - List the large files and what responsibilities are mixed in each.
   - Identify every place the core code hardcodes a specific tile/mechanic (e.g. checks for "orb", "door", specific key colors, specific warp logic).

2. CORE VS PACK BOUNDARY PROPOSAL
   - Define what belongs in a minimal "engine kernel" (grid, turn/step pipeline, level loading, rendering sync — should know nothing about specific tiles).
   - Timer, orbs, and gate are core to this game's identity. Decide and justify: do they stay in the kernel, or become a "core pack" built using the same registration system other packs will use?
   - Warp: identify the general primitive it needs (e.g. linked tiles) that future mechanics (buttons/traps, teleport pairs, clone machines) could reuse.

3. TARGET ARCHITECTURE (high level only, no implementation)
   - How tiles/entities/items will be defined and registered by namespaced ID.
   - A layered grid model (terrain vs object vs actor) vs. the current tile model — and migration impact.
   - Generic state primitives packs will need, so we stop adding mechanic-specific fields (e.g. generic inventory instead of redKey/blueKey fields, generic per-tile metadata for links).
   - The order of the step/tick pipeline (input → move → push → terrain effects → pickups → monster/forced movement → win/lose/timer).
   - How the Pixi renderer and HUD stay dumb and just read state/definitions.

4. PRESSURE TEST
   Validate your proposed design against these hypothetical future mechanics WITHOUT implementing them:
   a) Water that kills you unless you carry a specific item
   b) A button linked to a trap on another tile
   c) A monster with its own movement rules
   d) Ice/force floors that move the player after they step
   For each: would it require touching engine code? If yes, revise the design.

5. PHASED MIGRATION PLAN
   Break the refactor into small phases, each leaving the game fully playable.
   For each phase: goal, files created/moved/deleted, behavior changes (should be "none" for early phases), risk level, and how to verify it worked.
   Keys/locks should be extracted as the first example "pack" to prove the architecture.
   No big-bang rewrites. No new build tools, frameworks, TypeScript, or ECS unless you strongly justify it in the plan.

6. RISKS, NON-GOALS, AND OPEN QUESTIONS FOR ME

End your response by summarizing REFACTOR.md and stopping. Wait for my approval before coding Phase 1.