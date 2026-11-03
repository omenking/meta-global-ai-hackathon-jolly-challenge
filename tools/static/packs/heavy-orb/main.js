// Pack: heavy orb (mech-17-heavy-orb sanity check).
// The heavy orb is a solid object the player pushes one tile at a
// time like a block; it is never walked over. It cannot be pushed
// into walls or water (nor out of bounds or onto another object):
// such a push simply does not happen and neither the orb nor the
// player moves. Pushing it onto a scale tile locks it there (it
// becomes heavy:orb-locked and can never be pushed off again) and
// counts it as collected by decrementing core:orbs_left, which the
// core pack's level hook initialised and this pack tops up with the
// heavy orbs on the board. Restart restores the orb because a fresh
// initialState rebuilds the room. All state advances through the
// pure step function: the push is resolved inside the blocks
// predicate, which runs on the kernel's cloned next state during
// canEnter, so the input state is never mutated and no rule reads
// wall-clock time.
// UMD: browser global GamePackHeavyOrb + Node export (register fn).
(function (root) {
  'use strict';
  function registerHeavyOrbPack(api) {
    for (const name of ['scale.png', 'scale-locked.png', 'heavy-orb.png']) {
      api.defineAsset(name, { pack: 'heavy-orb', bundled: true });
    }
    api.defineTile('heavy:scale', { layer: 'terrain',
      sprite: 'scale.png', glyph: 'S' });
    api.defineTile('heavy:orb-locked', { layer: 'object',
      sprite: 'scale-locked.png', glyph: 'H',
      blocks: function () { return true; } });
    api.defineTile('heavy:orb', { layer: 'object',
      sprite: 'heavy-orb.png', glyph: 'H',
      blocks: function (state, cell, actor) {
        if (!actor || actor.id !== 'player') return true;
        const dx = cell.x - actor.x, dy = cell.y - actor.y;
        if (Math.abs(dx) + Math.abs(dy) !== 1) return true;
        const bx = cell.x + dx, by = cell.y + dy;
        if (bx < 0 || by < 0 || bx >= state.width || by >= state.height) {
          return true;
        }
        const terr = state.terrain[by][bx];
        if (terr === 'core:wall' || terr === 'water:water') return true;
        if (state.objects[by][bx]) return true;
        // The push happens: move the orb exactly one tile in the
        // cloned step state, then let the player follow into the
        // vacated cell by not blocking.
        state.objects[cell.y][cell.x] = null;
        if (terr === 'heavy:scale') {
          state.objects[by][bx] = 'heavy:orb-locked';
          state.counters['core:orbs_left'] =
            (state.counters['core:orbs_left'] || 0) - 1;
        } else {
          state.objects[by][bx] = 'heavy:orb';
        }
        return false;
      } });
    api.onLevelLoad(function (state) {
      let n = 0;
      for (const row of state.objects) {
        for (const id of row) if (id === 'heavy:orb') n++;
      }
      if (n) {
        state.counters['core:orbs_left'] =
          (state.counters['core:orbs_left'] || 0) + n;
      }
      if (!state.chars.object['heavy:orb']) {
        state.chars.object['heavy:orb'] = 'H';
      }
      state.chars.object['heavy:orb-locked'] = 'H';
      state.chars.terrain['heavy:scale'] = 'S';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerHeavyOrbPack;
  }
  root.GamePackHeavyOrb = registerHeavyOrbPack;
})(typeof window !== 'undefined' ? window : globalThis);
