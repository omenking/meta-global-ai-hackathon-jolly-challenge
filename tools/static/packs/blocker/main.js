// Pack: blocker (mech-34-blocker sanity check).
// A guard that lives in a three-wide doorway strip and shuffles
// one tile per player move sideways to stay between the player
// and the exit, tracking the player x. It never leaves its strip
// and never moves toward or away (its row never changes).
// Getting past: pinning (push block, mech 81) and luring (decoy
// Jolly, mech 39) are deferred synergies; here the player crosses
// behind a guard window — once the player steps up to the
// doorway (the row beside it or in it) the blocker is committed
// and holds its tile, so feinting it to one side from afar then
// walking up and crossing at the other side works, while a
// head-on slip at the column it guards is touched. Touch (stepping onto the blocker, or the blocker
// stepping onto the player) loses the attempt, returning the
// player to the room start on retry. All state advances through
// the pure step function (tick hook); no wall-clock reads.
// UMD: browser global GamePackBlocker + Node export (register fn).
(function (root) {
  'use strict';
  function registerBlockerPack(api) {
    for (const name of ['blocker.png', 'blocker-doorway.png',
      'push-block.png']) {
      api.defineAsset(name, { pack: 'blocker', bundled: true });
    }
    api.defineTile('blocker:doorway', { layer: 'terrain',
      sprite: 'blocker-doorway.png', glyph: 'D' });
    api.defineTile('blocker:blocker', { layer: 'object',
      sprite: 'blocker.png', glyph: 'B',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
      } });
    api.onLevelLoad(function (state) {
      // Record each doorway strip + previous player pos (tick use).
      const strips = [];
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] !== 'blocker:blocker') continue;
          let min = x, max = x;
          while (min > 0
            && state.terrain[y][min - 1] === 'blocker:doorway') min--;
          while (max < state.width - 1
            && state.terrain[y][max + 1] === 'blocker:doorway') max++;
          strips.push({ x: x, y: y, min: min, max: max });
        }
      }
      state.flags['blocker:strips'] = strips;
      state.flags['blocker:prevX'] = state.spawn.x;
      state.flags['blocker:prevY'] = state.spawn.y;
      if (!state.chars.object['blocker:blocker']) {
        state.chars.object['blocker:blocker'] = 'B';
      }
      if (!state.chars.terrain['blocker:doorway']) {
        state.chars.terrain['blocker:doorway'] = 'D';
      }
    });
    api.onTick(function (state, fx) {
      const strips = state.flags['blocker:strips'] || [];
      if (!strips.length || state.status !== 'playing') return;
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (!player) return;
      const prevY = state.flags['blocker:prevY'];
      for (const home of strips) {
        // Locate the blocker object (it stays on its home row).
        let bx = -1;
        for (let x = 0; x < state.width; x++) {
          if (state.objects[home.y][x] === 'blocker:blocker') bx = x;
        }
        if (bx < 0) continue;
        if (player.x === bx && player.y === home.y) {
          fx.push({ type: 'lose' });
          continue;
        }
        // Guard window: beside or in the doorway the blocker is
        // committed and holds its tile this step.
        if (Math.abs(player.y - home.y) <= 1) continue;
        const target = Math.max(home.min,
          Math.min(home.max, player.x));
        if (bx === target) continue;
        const nx = bx + (target > bx ? 1 : -1);
        if (state.objects[home.y][nx]) continue;
        fx.push({ type: 'removeObject', x: bx, y: home.y });
        fx.push({ type: 'setObject', x: nx, y: home.y,
          def: 'blocker:blocker' });
        if (player.x === nx && player.y === home.y) {
          fx.push({ type: 'lose' });
        }
      }
      state.flags['blocker:prevX'] = player.x;
      state.flags['blocker:prevY'] = player.y;
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerBlockerPack;
  }
  root.GamePackBlocker = registerBlockerPack;
})(typeof window !== 'undefined' ? window : globalThis);
