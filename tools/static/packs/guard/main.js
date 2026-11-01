// Pack: guard (mech-37-guard sanity check, candidate #37).
// A guard never leaves its corridor tile. Its facing rotates 90
// degrees clockwise every four successful player moves (a move
// counts only when the player's tile actually changes; pushing
// into a wall does not advance the cycle), shown by the arrow in
// its four bundled sprites. Stepping onto its tile head-on, from
// the front it faces (player moving opposite to its facing),
// loses the attempt, which resets the player to the room start
// on retry. Entering from behind (moving with its facing) or
// from either side passes through. Restart restores the placed
// tile and starting facing because a fresh initialState rebuilds
// the room. All state advances through the pure step function:
// the move count lives in counters/meta and no rule reads
// wall-clock time.
// UMD: browser global GamePackGuard + Node export (register fn).
(function (root) {
  'use strict';
  var ORDER = ['up', 'right', 'down', 'left'];
  var OPPOSITE = { up: 'down', down: 'up', left: 'right', right: 'left' };
  function facingOf(defId) {
    return String(defId || '').replace('guard:guard-', '');
  }
  function registerGuardPack(api) {
    for (const dir of ORDER) {
      api.defineAsset('guard-facing-' + dir + '.png',
        { pack: 'guard', bundled: true });
    }
    for (const dir of ORDER) {
      api.defineTile('guard:guard-' + dir, { layer: 'object',
        sprite: 'guard-facing-' + dir + '.png', glyph: 'U',
        onEnter: function (state, cell, actor, fx) {
          // actor.dir is the direction the player just moved.
          // Head-on means moving opposite to the guard's facing.
          if (actor && actor.dir === OPPOSITE[dir]) {
            fx.push({ type: 'lose' });
          }
        } });
    }
    api.onLevelLoad(function (state) {
      state.counters['guard:move_count'] = 0;
      state.flags['guard:last'] = state.spawn.x + ',' + state.spawn.y;
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          const id = state.objects[y][x];
          if (id && id.indexOf('guard:guard-') === 0) {
            for (const dir of ORDER) {
              state.chars.object['guard:guard-' + dir] = 'U';
            }
            const k = x + ',' + y;
            state.meta[k] = Object.assign({}, state.meta[k],
              { guard_facing: facingOf(id) });
          }
        }
      }
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (!player) return;
      const here = player.x + ',' + player.y;
      const last = state.flags['guard:last'];
      state.flags['guard:last'] = here;
      if (last === undefined || last === here) return;
      const count = (state.counters['guard:move_count'] || 0) + 1;
      state.counters['guard:move_count'] = count;
      if (count % 4 !== 0) return;
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          const id = state.objects[y][x];
          if (id && id.indexOf('guard:guard-') === 0) {
            const cur = facingOf(id);
            const nxt = ORDER[(ORDER.indexOf(cur) + 1) % ORDER.length];
            fx.push({ type: 'setObject', x: x, y: y,
              def: 'guard:guard-' + nxt });
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'guard_facing', value: nxt });
          }
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerGuardPack;
  }
  root.GamePackGuard = registerGuardPack;
})(typeof window !== 'undefined' ? window : globalThis);
