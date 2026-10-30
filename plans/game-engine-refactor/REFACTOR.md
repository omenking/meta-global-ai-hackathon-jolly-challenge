# Game Engine Refactor Plan — Jolly's Challenge (Chip's Challenge clone)

> Synthesis of `plans/game-engine-refactor/PLAN.md` (audit brief §§1–6) and
> `docs/pm-and-simple-game-engine.md` § Next Steps (items 1–3). No game code
> changes in this plan. `go` approves Phase 0 only; each later phase is its
> own reviewable feature on the PM board, game playable after every phase.

## Goal

Turn the working but monolithic PixiJS + plain-JS game into a small
deterministic **kernel + internal pack (mod-style) registry**, so a novel
mechanic is added as one new pack file + level data + one test room instead
of edits spread across the core, renderer and HUD. Preserve everything that
already works: pure `step(state, input)` determinism, session JSONL
recording/replay/fork, the existing level JSON input, and all shipped
mechanics (timer, orbs, gate, warp/progression, keys/locks, 8-slot HUD).

## Success Criteria

- [ ] Kernel files contain **no** mechanic-specific strings or branches:
      no `'orb'`, `'*'`, `'O'`, `'G'`, `'X'`, `keyColor`/`lockColor`,
      colour lists, or `orbs_left` logic. Verified by grep gate (Phase 0).
- [ ] Every shipped mechanic behaves identically to today on observable
      state: same level + same timestamped input log → same per-step
      `readout` (position, inventory, orbs, status, timer) on all existing
      test rooms and `chip1`. Raw `stateDigest` strings change exactly
      once, at the `state.v=2` cutover in Phase 1, and are stable within
      each version thereafter.
- [ ] Keys/locks run as the **first pack** (`packs/keys-locks.js`) through
      the same registration API a future pack will use; disabling the pack
      disables only keys/locks (walls/floor/timer still work).
- [ ] A hypothetical new mechanic from § Pressure Test can be added by
      creating one pack file, extending a level legend, and adding one test
      room — zero kernel edits. Demonstrated for water + flippers (Phase 5
      proof pack, deletable).
- [ ] Levels larger than the viewport scroll with a camera; all current
      levels (≤17×16) render identically (camera clamped = no-op).
- [ ] Full suite green each phase: `python3 -m unittest discover -s tools`
      plus a browser smoke (play, replay-digest match, session written).

## 1. Current Architecture Map (verified in code)

### Entry point and boot
- Page: [game.html](/home/andrew/Sites/meta-global-ai-hackathon-jolly-challenge/tools/static/game.html)
  loads vendored PixiJS, then `game-core.js`, `game-hud.js`,
  `game-session.js`, `game-replay.js`, `game.js` as classic scripts.
- [game.js](/home/andrew/Sites/meta-global-ai-hackathon-jolly-challenge/tools/static/game.js)
  is the boot IIFE: parses `?level=&embed=&fork=&wipe=`, fetches
  `levels/<name>.json`, loads sprites, creates the Pixi app, builds the
  static board + HUD, then wires input, recording and replay. There is no
  bundler, module system, or build step for game code.

### Main loop and determinism
- There is no fixed-timestep loop. State advances only via
  [game-core.js `step(state, input)`](/home/andrew/Sites/meta-global-ai-hackathon-jolly-challenge/tools/static/game-core.js:209)
  — a pure function. Every input carries `t_ms`; the countdown is derived
  from recorded `t_ms`, never wall-clock. `replay()` folds `step` over a
  log; `stateDigest()` (FNV hash of `JSON.stringify(state)`) is the replay
  equality check. Rendering never drives state. This property is the
  refactor's hard constraint and is already well-factored — keep it.

### Where game state lives
Single flat object from
[`initialState()`](/home/andrew/Sites/meta-global-ai-hackathon-jolly-challenge/tools/static/game-core.js:169):
`grid` (array of strings, one char per cell), `player {x,y}`,
`inventory` (array of colour strings, max 8), `orbs_left`, `gate_open`,
`key_tiles`/`lock_tiles` (char→colour maps derived from the legend),
`steps`, `t_ms`, `elapsed_s`, `time_limit_s`, `time_left_s`,
`status: playing|won|lost`, `next_level`, `last_input`, `level`.
`step()` returns a fresh object each call (input never mutated).

### Responsibility map

| Concern | Today | Notes |
|---|---|---|
| Movement + collision | `game-core.js resolveMove()` | One if-chain decides everything |
| Pickup (orb, key) | same `resolveMove()` | Orb decrements counter; key appends colour |
| Lock dissolve | same | Consumes first matching colour in `inventory` |
| Gate pass/block | same, `ch === 'G'` branch | Open = derived `orbs_left === 0`, tile stays `G` |
| Warp / win | same, `isWarp('X')` → `warped` → `status won` | Progression via `state.next_level` |
| Timer / lose | `step()` expiry check | Pure in `t_ms`; won runs never flip to lost |
| Level loading | `game.js` fetch + `tools/game_levels.py` list/load | JSON: `rows` + `legend` + `time_limit/next/test` |
| Rendering (board) | `game.js` (~910 lines) | Static sprites + `dynamicTiles` visibility sync |
| HUD | `game.js` Pixi column + `game-hud.js` pure helpers | Timer/orbs/level digits + 8 inventory icons |
| Input | `game.js` keydown → `GameCore.inputForKey` | WASD/arrows only |
| Session record/replay/fork | `game-session.js`, `game-replay.js`, `game.js` glue | JSONL header/steps/end, fork seeds |
| Level preview (non-game) | `level-preview.html` | Reuses same level JSON + sprites |

### Large files and mixed responsibilities
- **`tools/static/game.js` (910 lines, 41 KB)** — everything view-side in
  one IIFE: URL/menu handling, level fetch, sprite/texture loading, Pixi
  app sizing, static board build, dynamic-tile sync, entire HUD column
  (readouts, inventory, retry/win groups, layout), player sprite + marker,
  debug DOM readouts, session recorder lifecycle, keyboard input, replay
  controls, level-summary modal, wipe transition. A HUD tweak and a
  rendering bug live in the same file.
- **`tools/static/game-core.js` (303 lines)** — clean determinism shell
  (`step`, timer, replay, digest) wrapped around one monolithic mechanic
  dispatcher (`resolveMove`), plus level-derived key/lock maps and
  orb/warp helpers. Small, but every mechanic touches it.
- `tools/server.py` (1,357 lines) and `tools/pm_store.py` (1,117 lines) are
  large but are **tools**, not engine — explicitly out of scope here.

### Every hardcode of a specific tile/mechanic in core
In `game-core.js`: `isWalkable` allows only `'.'`/`'P'`; `isOrb` checks
`'*'|'O'`; `isWarp` checks `'X'`; gate branch checks `'G'`;
`countOrbs`/`orbsLeftOf` scan the grid; `tileMaps()` reads legend
`key_color`/`lock_color`; inventory cap `8` and first-match consume in
`resolveMove`; `gate_open` recomputed in `initialState` and `step`.
In `game.js`: dynamic-tile test
`e.key_color || e.lock_color || ch==='*'||'O'||'G'`; gate sprite visibility
special-case (`'G'` shows only while shut); HUD loads
`key_red/gold/green/blue/silver.png` by name and assumes colour-string
inventory; `game-hud.js` recounts orbs by scanning for `'*'|'O'` and
hardcodes `KEY_COLORS`. In `tools/server.py`/`game_levels.py`: none for
mechanics (levels are opaque JSON) — good, keep it that way.

### Level / tile model today
One char per cell conflates three things: terrain (floor/wall), object
(orb, key, lock, gate, portal) and actor (player start `P` = floor +
spawn). Levels are tiny and fully on-screen: `chip1` is 17×16; test rooms
7×6 to 13×9. `game.js` sizes the canvas to `COLS*TILE + HUD` and letterboxes
to fit — there is **no camera, viewport, or scroll** (Next Steps item 3 is
currently unimplemented, not just unorganised).

## 2. Core vs Pack Boundary Proposal

### Recommendation on organisation style (Next Steps item 1)
**Lightweight component-style registry over plain data — not classic OOP
inheritance, not full ECS.** Rationale for this codebase:

| Style | Fit here | Verdict |
|---|---|---|
| Classic OOP inheritance (`Tile → Key → RedKey…`) | Deep hierarchies fight cross-cutting rules (water × flippers, button × trap); JS prototype chains obscure the pure step function | Reject |
| Full ECS (archetypes, queries, systems scheduler) | Right ideas, wrong scale: ≤ a few hundred cells, one actor today, no build step; ECS plumbing would exceed current core size | Reject (borrow its data-orientation only) |
| **Registry + behaviour hooks on plain state (chosen)** | Keeps `step` pure and Node-testable; a mechanic = data + 2–3 small hook functions; matches existing UMD/`module.exports` test pattern in `game-core.js`/`game-hud.js` | **Adopt** |

Concretely: entities/tiles are plain objects in layered arrays; a **pack**
is one JS file that registers tile definitions, item definitions and step
hooks by namespaced ID. No classes to instantiate per tile, no framework.

### What stays in the kernel (knows no specific tile)
`engine/kernel` responsibilities only:
- Grid storage + bounds, layered cell access (`getCell`, `setTerrain`,
  `setObject`, `moveActor`) with structural sharing so `step` stays pure.
- Level loading/normalisation: accepts today's `rows`+`legend` JSON and
  produces layered state (see §3); unknown chars are load errors, not
  silent magenta tiles (renderer fallback stays view-only).
- The fixed step pipeline (§3) and hook dispatch; turn/phase ordering.
- Determinism services: `t_ms` validation, `replay`, `stateDigest`,
  status machine shell (`playing → won/lost` transitions are *requested*
  by hooks via effects, arbitrated by kernel).
- Generic state containers: `inventory` (item-instance list), per-cell
  `meta` map, per-actor `flags`, `counters` map, `links` index.
- Namespaced definition registry (`registerPack`, `getDef`) and pack
  lifecycle (`onLevelLoad`, step hooks, `describeHud` contributions).
- Nothing else. Timer expiry is the one kernel-adjacent rule: kernel owns
  the clock (`elapsed/time_left` from `t_ms`); whether expiry *loses* is
  a core-pack rule so a future untimed/creative mode needs no kernel edit.

### Core pack vs kernel for timer / orbs / gate
**Decision: timer + orbs + gate become the `core` pack
(`packs/core-chips.js`), built with the exact registration API external
packs use. They do not stay in the kernel.** Justification:
- They are this game's identity (`docs/game-lore-and-mechanics.md`: orbs
  unlock the gated elevator/portal) but they are still *rules about
  specific tiles* (`*`, `G`, `X`). Keeping them in the kernel would keep
  the grep gate red forever and give packs a two-tier API.
- Dogfooding: if the core pack cannot express orbs/gate/timer cleanly,
  the API is wrong — better to learn that on mechanics we already have
  tests for (`test_orbs_and_gate.py`, `test_level_timer.py`) than on the
  first novel mechanic.
- Cost is low because `initialState`/`step` already isolate counting
  (`countOrbs`, `orbsLeftOf`) and the gate is already state-derived
  (`gate_open`), not a tile mutation. The kernel keeps only the clock and
  the `counters` store; the core pack owns `orbs_left` semantics.

### Warp: the general primitive
Warp today is `step on 'X' → won + next_level`. The reusable primitive is
**linked tiles + an `onEnter` effect that emits a kernel command**:
- Level data gains optional per-cell `link: "<group-id>"` (in legend entry
  or a `links` array in level JSON). Kernel builds a `links` index
  (`groupId → [cells]`) at load; kernel itself never interprets it.
- A pack hook returns *effects* (`{type:'teleport', actor, to}`,
  `{type:'win'}`, `{type:'loadLevel', id}`, `{type:'setMeta', …}`).
  Kernel applies effects in pipeline order and records them in state so
  replay reproduces them exactly.
- Warp pack (fold into `core` pack or `packs/warp.js`): portal def with
  `onEnter → win + loadLevel(next)`. The same primitive then covers
  teleport pairs (enter A → exit at linked B), button→trap (button
  `onEnter/onExit` sets linked trap's `meta.open`), and clone machines
  (timer hook spawns at linked cell) with no kernel change.

## 3. Target Architecture (high level, no implementation yet)

### Namespaced definitions and registration
- IDs are namespaced strings: `core:floor`, `core:wall`, `core:orb`,
  `core:gate`, `core:portal`, `keys:key-red`, `keys:lock-red`,
  `future:water`, `future:flipper`. Level JSON keeps its single-char
  `rows` for authoring compactness; the legend maps each char to a
  namespaced `def` plus sprite info, e.g.
  `"*": {"def":"core:orb","sprite":"orb.png","base":"core:floor"}`.
  A migration shim translates today's `key_color`/`lock_color` legend
  entries to defs so un-migrated levels keep loading during transition.
- A pack is one UMD file (same pattern as `game-hud.js`: browser global +
  `module.exports` for Node tests):
  `register(api)` where `api` offers `defineTile(id, def)`,
  `defineItem(id, def)`, `onPhase(phase, fn)`, `hudSlot(fn)`.
- Tile def (data + hooks, all hooks optional and pure):
  `walkable(state, cell, actor)`, `blocksActor`, `onEnter(state, cell,
  actor) → effects`, `onExit`, `onTick`, `layer: 'terrain'|'object'`.
  Item def: `id`, `icon`, `maxStack`/consumable flag, `hudOrder`.
  Hooks receive a read-only-ish view + an effects list; they never touch
  Pixi, DOM, or wall-clock.

### Layered grid model vs current model
Move from one char per cell to **three layers**, stored as parallel arrays
in state (still JSON-serialisable for digest/session compatibility via a
versioned state shape, `state.v = 2`):
- `terrain[]` — exactly one def per cell: floor, wall, water, ice, force
  floor. Owns base walkability and `onEnter` terrain effects.
- `objects[]` — at most one def per cell or `null`: orb, key, lock, gate,
  portal, button, trap, block. Owns pickup/blocking/interaction.
- `actors[]` — player today; monsters later. Each actor:
  `{id, def, x, y, dir, flags:{}, meta:{}}`. Player start `P` in level
  rows becomes terrain floor + actor spawn, removing the actor/terrain
  conflation.
- Per-cell `meta` (sparse map ` "x,y" → {link, open, count…}`) holds link
  IDs and pack-private tile state generically — no new top-level state
  fields per mechanic.
Migration impact: level files do **not** change (loader splits chars into
layers); saved sessions store the *input log + level*, not raw state, so
old sessions still replay. Replaying across the migration requires the
new core to reproduce the old per-step observable `readout` on the
regression corpus, which is the Phase-gate check. Raw `stateDigest`
values change once (v2) and are not comparable across versions; digests
remain a within-version replay guard and the debug UI must show `state.v`.

### Generic state primitives (stop adding mechanic fields)
- `inventory: [{item:'keys:key-red', n:1}…]` ordered, cap from level/
  kernel config (default 8, today's rule) — replaces colour-string array;
  HUD maps item def → icon. Flippers/boots are just items with flags.
- `counters: { 'core:orbs_left': n, … }` — replaces `orbs_left`/`gate_open`
  top-level fields; gate def reads the counter. Timer stays kernel clock
  fields (`t_ms/elapsed_s/time_*`) since every pack may read them.
- `actor.flags` / `cell.meta` / `state.flags` string-keyed maps for
  pack-private booleans (has-flippers is `inventory` presence, not a flag;
  trap-open is cell `meta.open`). Rule: a new mechanic may add **keys**,
  never new top-level state fields. `readout()` becomes an assembly of
  kernel fields + pack `describeState` contributions (HUD/replay compat).

### Step / tick pipeline (fixed order, kernel-owned)
1. **Input** — validate `t_ms` monotonic; snapshot clock. Expired/finished
   short-circuit exactly as today (no movement on/after expiry; won never
   flips to lost).
2. **Intent** — actor controllers produce moves: player from input; monster
   packs from `actorTick` hooks (deterministic, seeded from state only).
3. **Move resolution** — for each moving actor in stable ID order: terrain
   `walkable` + object `blocksActor` (locks consult inventory here) decide;
   pushing (future blocks) resolves in this phase.
4. **Terrain effects** — `onEnter` of the entered terrain (ice slide,
   force floor, water hazard check vs inventory) may queue extra moves;
   loop bounded (e.g. ≤ grid size) to guarantee termination.
5. **Object interaction** — entered object's `onEnter` (pickup orb/key,
   button press, portal) then `onExit` of the vacated cell (button
   release); effects applied (inventory/counter/meta/link changes).
6. **Links & effects arbitration** — teleport/win/loadLevel/spawn effects
   applied in emitted order; conflicting teleports: first wins, rest
   dropped and logged in `state.last_effects` for debugging.
7. **Actor/timer phase** — monster forced movement already in (2); periodic
   `onTick` hooks (clone machines, timed traps); core-pack timer rule
   turns expiry into `lost`.
8. **Win/lose arbitration** — if both requested same step, **lose wins**
   unless already won in a prior step (matches today's "won never flips";
   new explicit rule, covered by a test before it can regress anything).
9. **Commit** — derive readouts (`gate_open` etc. as computed views, not
   stored truth), increment `steps`, stamp `last_input`.

### Renderer and HUD stay dumb
- Pixi layer reads `state + registry defs` only: for each cell draw terrain
  sprite, then object sprite (hidden when object consumed — replaces
  `dynamicTiles` char comparisons with `objects[]` presence), then actors.
  Gate-open rendering = gate def's `spriteWhen(state, cell)` view hook.
- HUD is assembled from pack contributions: each pack may register a
  readout (`label, value(state), icon`) — core pack gives time/orbs/level,
  keys pack gives inventory slots. `game-hud.js` helpers become pure
  functions over the generic containers (no `'*'` scanning in HUD; orb
  count comes from `counters` via readout).
- Camera (Next Steps item 3): renderer-only concern. Add a `Camera`
  (viewport in tiles, e.g. 9×9 or fit-to-window at 64px tiles) that centres
  on the player and clamps to level bounds; levels smaller than the
  viewport clamp to origin and render exactly as today. Kernel/state never
  know the camera exists. Decide default viewport in Phase 4 with a large
  test level (e.g. 32×24) before committing to a size — see Open Questions.

## 4. Pressure Test (design validation, nothing implemented)

| Hypothetical mechanic | Pack-only? | How, with the target design |
|---|---|---|
| (a) Water kills unless carrying flippers | ✅ Yes | New pack: `terrain future:water` (`onEnter`: if actor lacks `future:flipper` item → effect `lose`) + item def with icon. Uses generic inventory query. Kernel untouched. |
| (b) Button linked to a trap elsewhere | ✅ Yes | Level cells share `meta.link='door-1'`; button object `onEnter/onExit` emits `setMeta` on linked cells; trap object reads own `meta.open` in `blocksActor`/sprite hook. Kernel only provides links index + effects. |
| (c) Monster with own movement rules | ✅ Yes | Monster is an `actors[]` entry with a pack-registered controller consulted in pipeline phase 2; movement reuses kernel move resolution + terrain/object rules. Determinism kept: controller is a pure function of state. Kernel untouched (actors array already generic). |
| (d) Ice / force floors move player after stepping | ✅ Yes | Terrain defs with `onEnter` queueing a forced move in phase 4; bounded chain loop handles ice→force→ice sequences. This is why terrain effects are a separate phase after the voluntary move. |

One design revision came out of this test: win/lose arbitration (phase 8)
had to be made explicit because water (lose) and portal (win) can trigger
in the same step once packs compose. Everything else fit without kernel
changes; if a future mechanic still needs a kernel edit, that is treated as
an API bug to fix in the kernel generically, never a mechanic `if` in core.

## 5. Phased Migration Plan (each phase leaves the game fully playable)

Workflow per phase: one PM feature + tasks per
`plans/simple-game-engine/template.md`, worktree `feat/<phase>`, test room
or regression corpus as evidence, human approves before merge (same as the
eight completed features). No new build tools, frameworks, TypeScript or
ECS library in any phase.

### Phase 0 — Regression corpus and grep gate (no behaviour change)
- **Goal:** Make "no behaviour change" provable before touching code.
- **Create:** `tools/test_refactor_regression.py` (or extend existing
  suites) that replays fixed input logs on every `levels/*.json` test room
  + `chip1` and asserts the per-step observable `readout` sequence plus the
  `stateDigest` sequence (stable guard within the current state version).
  A `tools/check_kernel_purity.sh` grep gate listing current
  hardcodes (baseline count; must only shrink).
- **Files moved/deleted:** none. **Behaviour change:** none.
- **Risk:** Low. **Verify:** suite green; gate script prints baseline;
  intentionally perturb `game-core.js` locally → corpus fails (prove the
  net works), then revert.

### Phase 1 — Registry + layered state inside the core (no behaviour change)
- **Goal:** Introduce `kernel` (grid layers, pipeline phases, registry,
  generic containers) with all current mechanics re-expressed as internal
  definitions still living in one file set; public `GameCore` API
  (`initialState/step/replay/stateDigest/readout/inputForKey`) unchanged.
- **Create:** `tools/static/engine/kernel.js`, `tools/static/engine/registry.js`
  (or a single `engine.js` if two files prove noisy — decide in-phase, keep
  UMD pattern). **Modify:** `game-core.js` becomes a thin façade delegating
  to kernel + built-in defs; `game.html` script order gains engine files.
  **Delete:** nothing yet.
- **Behaviour change:** state shape goes `v=2` (digest values change once;
  corpus updated deliberately with a before/after digest report attached
  to the feature). Session logs (inputs) unaffected.
- **Risk:** Medium (touches every mechanic at once, but behind the same API).
  **Verify:** Phase 0 corpus replay matches on states' *observable*
  readout (position/inventory/orbs/status per step) even though digests
  change; full suite green; browser play + replay + fork smoke.

### Phase 2 — Extract keys/locks as the first pack (proof of architecture)
- **Goal:** Per PLAN.md, keys/locks leave the core entirely.
- **Create:** `tools/static/packs/keys-locks.js` (key/lock defs per colour
  from legend, inventory consume rule, HUD slot contribution). Legend shim
  translates `key_color`/`lock_color` → `keys:*` defs. **Modify:** kernel
  façade drops key/lock branches; `game.js` dynamic-tile logic reads object
  presence generically; `game-hud.js` drops `KEY_COLORS` hardcode.
  **Delete:** `tileMaps()` from core.
- **Behaviour change:** none observable (same rooms: `keys-room`, `chip1`).
- **Risk:** Medium-low. **Verify:** `test_keys_and_locks.py` passes
  unmodified (test edits require justification in the feature); corpus
  green; pack-disable check: load game without the pack script → keys-room
  locks render as unknown-def placeholders and core still plays (proves
  isolation), then restore.

### Phase 3 — Core pack (timer/orbs/gate/warp) on the same API
- **Goal:** Move remaining mechanics into `packs/core-chips.js`; kernel
  grep gate reaches zero mechanic strings.
- **Create:** `tools/static/packs/core-chips.js` (orb counter, gate def
  reading counter, portal def emitting win/loadLevel effects, timer rule
  hook). **Modify:** façade shrinks to kernel + pack assembly; HUD readouts
  come from pack contributions. **Delete:** `isOrb/isWarp/countOrbs/G`
  branches from core files.
- **Behaviour change:** none observable. `orbs-room`, `warp-room`,
  `timer-room`, `chip1` are the acceptance rooms.
- **Risk:** Medium (win/lose arbitration and warp chain are the subtle
  parts). **Verify:** `test_orbs_and_gate.py`, `test_level_timer.py`,
  `test_warp_and_levels.py` green; purity gate prints zero; full corpus.

### Phase 4 — Camera and level scale (Next Steps item 3)
- **Goal:** Levels larger than the viewport scroll; small levels unchanged.
- **Create:** `tools/static/engine/camera.js` (pure viewport math,
  Node-testable) + one large test level `levels/scroll-room.json`
  (e.g. 32×24) exercising orbs/gate/keys across a scroll. **Modify:**
  `game.js` rendering offsets by camera (board container position),
  `fitBoard`/embed resize path. Kernel untouched.
- **Decision made in-phase (needs your call, see Open Questions):**
  viewport tiles and whether HUD keeps its fixed right column at all
  sizes. Default proposal: viewport = as many whole 64px tiles as fit the
  window beside the HUD column, camera centred on player, clamped.
- **Behaviour change:** visual only, and only on levels larger than the
  viewport. **Risk:** Medium-low (render-only, but embed layout is fiddly).
  **Verify:** `test_level_capture`/screenshot checks on `scroll-room` at
  two window sizes; existing rooms pixel-identical (camera at origin);
  replay determinism unaffected (camera absent from state).

### Phase 5 — Proof pack + slim `game.js` (novel mechanic, then cleanup)
- **Goal:** Prove the promise end-to-end, then pay down the 910-line file
  only where the new seams make it mechanical.
- **Create:** `tools/static/packs/proof-water.js` implementing Pressure
  Test (a) (water + flippers) + `levels/water-room.json`; this pack is a
  *candidate keeper* — keep if you like the mechanic, delete the two files
  to remove it (that deletability is the test). **Modify/split `game.js`
  into** `view/board.js`, `view/hud-view.js`, `view/input.js`,
  `view/session-ui.js` along the seams the registry created (no logic
  changes during the split). **Delete:** dead char-based dynamic-tile code.
- **Behaviour change:** new optional mechanic only; split is neutral.
- **Risk:** Low for pack; medium for the split (do it last, separately
  reviewable, corpus + screenshots as gate). **Verify:** water-room
  playtest (death without flippers, safe with), pack-removal check,
  full suite + browser smoke on all rooms.

## 6. Risks, Non-Goals, Open Questions

### Risks
- **Digest break (Phase 1):** state `v=2` invalidates old digest strings.
  Sessions store inputs, so replay survives, but any external tool
  comparing raw digests must be version-aware. Mitigated by corpus +
  `state.v` in the debug UI.
- **Hook-order bugs:** pack composition makes ordering load-bearing.
  Mitigated by fixed pipeline phases, stable actor order, effects log
  (`last_effects`), and Phase 0 corpus before any extraction.
- **Over-abstraction for AI cost:** the original motivation (Next Steps
  item 2) is cheaper AI implementation via isolation. If packs accrete
  kernel backdoors, cost goes *up*. Guard: purity grep gate in CI-local
  test command; kernel API changes require their own feature review.
- **`game.js` split churn (Phase 5):** purely organisational; scheduled
  last so a bad split never blocks the architecture. Can be dropped
  without invalidating Phases 1–4.

### Non-goals
- No external/true mod support, sandboxing, or user-supplied packs (per
  PLAN.md: internal structure only). No build step, bundler, TypeScript,
  framework, or ECS library. No changes to `tools/server.py`, PM tool,
  asset tool, or level file format (loader shims absorb differences). No
  new mechanics beyond the deletable Phase 5 proof pack. No Sokoban-style
  pushing or monsters in the migration itself — the design accommodates
  them (§4b–d) without implementing them.

### Answered decisions (human, 2026-10-30 — binding for implementation)
1. **Level scale:** support up to **64×64** maximum. Realistic levels are
   expected ≤64×64 (Chip's Challenge 2 allows 100×100 but its levels do
   not exceed ~40×40). Kernel, loader and camera must handle 64×64
   without performance pathology; Phase 4 proves it with a large test
   level inside that bound. Do not design for 100×100.
2. **Naming:** the exit is called **warp** (not elevator, not portal).
   Core IDs: `core:orb`, `core:gate`, `core:warp`. Orbs stay "orbs".
3. **Old sessions:** **discard** — breaking digest comparability once at
   `state.v=2` is accepted; no compat digest, no session migration.
4. **Proof pack:** **keep** water/flippers as a real mechanic after
   Phase 5 (still removable as two files, but kept by default).
---
*Evidence base: `tools/static/game-core.js` (303 lines), `tools/static/game.js`
(910 lines), `tools/static/game-hud.js`, `levels/*.json` (8 levels, max
17×16), `tools/test_*.py` (19 suites), `docs/pm-and-simple-game-engine.md`
§ Next Steps, `docs/game-lore-and-mechanics.md`, `plans/game-engine-refactor/PLAN.md`.*
