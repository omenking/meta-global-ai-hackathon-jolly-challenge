// Pack: patroller (mech-31-patroller sanity check).
// A patroller is an actor on a marked fixed loop: it moves one
// tile per player move along the loop, forever. The loop is the
// ordered `patroller_loop` cell list in the level JSON; the
// controller steps each patroller to the next listed cell (the
// list wraps, so a forth-and-back patrol lists its cells in the
// order they are visited). The loop never changes unless a
// mirror block redirects it (mech-84, not in this pack), so
// without one it is identical after any number of moves. Touch —
// the player and a patroller ending a step on the same tile, or
// swapping tiles within one step — returns the player to the
// level spawn (or the active checkpoint where one is placed, per
// mech-48; no checkpoint tile exists in this pack, so the spawn
// is the respawn here). The player is never stranded: after a
// touch they stand at the spawn and can retry immediately.
// Stepping onto the tile the patroller just left is safe — the
// gap behind it is the crossing window the teaching room teaches.
// Restart restores the patroller to its placed loop position
// because a fresh initialState rebuilds the room. All state
// advances through the pure step function; no rule reads
// wall-clock time (only the recorded input t_ms drives state).
// UMD: browser global GamePackPatroller + Node export.
(function (root) {
  'use strict';
  var DIRS = { '0,-1': 'up', '0,1': 'down', '-1,0': 'left', '1,0': 'right' };
  function registerPatrollerPack(api) {
    // Bundled assets (see manifest.json): real generated art.
    for (const name of ['patroller.png', 'patroller-loop.png']) {
      api.defineAsset(name, { pack: 'patroller', bundled: true });
    }
    // Marked loop tiles: walkable terrain the patroller follows.
    api.defineTile('patroller:loop', { layer: 'terrain',
      sprite: 'patroller-loop.png', glyph: 'L' });
    // Sprite carrier for the patroller actor: the kernel spawns
    // actors from the legend, and game.js draws each non-player
    // actor with the sprite of its actor def. Never placed as an
    // object tile.
    api.defineTile('patroller:patroller', { layer: 'object',
      sprite: 'patroller.png', glyph: 'A' });
    api.onLevelLoad(function (state, level) {
      state.chars.terrain['patroller:loop'] = 'L';
      const raw = (level && (level.patroller_loop || level.patroller_loops)) || [];
      const loop = (Array.isArray(raw[0]) || (raw[0] && typeof raw[0].x === 'number')
        ? raw : raw[0] || []).map(function (p) {
          return Array.isArray(p) ? { x: p[0], y: p[1] } : { x: p.x, y: p.y };
        });
      if (loop.length < 2) return;
      for (const actor of state.actors) {
        if (actor.def === 'patroller:patroller') {
          actor.flags.loop = loop;
          actor.flags.prevX = actor.x;
          actor.flags.prevY = actor.y;
          actor.flags.loopIndex = 0;
          for (let k = 0; k < loop.length; k++) {
            if (loop[k].x === actor.x && loop[k].y === actor.y) {
              actor.flags.loopIndex = k;
              break;
            }
          }
        }
      }
    });
    // One tile per player move along the marked loop. The loop
    // position is an index in actor flags (a forth-and-back list
    // visits the same cell twice per cycle, so the index, not the
    // cell, says where in the cycle the patroller is). Loop cells
    // are walkable floor, so the indexed move always lands; if a
    // future tile ever blocked one, the index still advances and
    // the direction lookup below simply finds no adjacent step.
    api.defineController('patroller:patroller', function (state, actor) {
      const loop = actor.flags && actor.flags.loop;
      if (!loop || loop.length < 2) return null;
      actor.flags.prevX = actor.x;
      actor.flags.prevY = actor.y;
      const i = typeof actor.flags.loopIndex === 'number' ? actor.flags.loopIndex : 0;
      const nxt = loop[(i + 1) % loop.length];
      actor.flags.loopIndex = (i + 1) % loop.length;
      return DIRS[(nxt.x - actor.x) + ',' + (nxt.y - actor.y)] || null;
    });
    // Touch resolution: same tile after the step, or the player
    // and patroller swapped tiles within the step. The respawn
    // is the level spawn; a checkpoint (mech-48) placed in the
    // level would own the respawn instead, but none exists here.
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return;
      const d = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[state.last_input] || [0, 0];
      const pPrevX = player.x - d[0], pPrevY = player.y - d[1];
      for (const actor of state.actors) {
        if (actor.def !== 'patroller:patroller') continue;
        const overlap = actor.x === player.x && actor.y === player.y;
        const swapped = actor.x === pPrevX && actor.y === pPrevY
          && player.x === actor.flags.prevX && player.y === actor.flags.prevY;
        if (overlap || swapped) {
          fx.push({ type: 'teleport', actor: player.id,
            x: state.spawn.x, y: state.spawn.y });
          return;
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerPatrollerPack;
  }
  root.GamePackPatroller = registerPatrollerPack;
})(typeof window !== 'undefined' ? window : globalThis);
