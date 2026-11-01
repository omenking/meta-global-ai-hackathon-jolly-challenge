// Pack: crumbling tile (mech-5-crumbling-tile sanity check).
// A crumbling tile is safe while the player stands on it. It falls
// on the step that leaves it: the vacated tile becomes a void tile
// (a blocker) for the rest of the attempt, so it can never be
// re-occupied. A one-move delay instead let backtracking isolate
// the middle tile of a bridge (void on both sides, no legal move),
// which review-fixes-2 removed. Restart restores it because a fresh
// initialState rebuilds the room. All state advances through the
// pure step function; the deadline is a step count, never time.
// UMD: browser global GamePackCrumbling + Node export (register fn).
(function (root) {
  'use strict';
  function registerCrumblingPack(api) {
    // Bundled assets (see manifest.json): generated placeholders from
    // tools/make_placeholder_sprites.sh until real art lands.
    for (const name of ['crumbling.png', 'crumbling-cracked.png', 'void.png']) {
      api.defineAsset(name, { pack: 'crumbling', bundled: true });
    }
    api.defineTile('crumble:crumbling', { layer: 'object',
      sprite: 'crumbling.png', glyph: 'C',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'crumble_deadline', value: 0 });
      },
      onExit: function (state, cell, actor, fx) {
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'crumble_deadline', value: state.steps });
      } });
    api.defineTile('crumble:void', { layer: 'object',
      sprite: 'void.png', glyph: 'V',
      blocks: function () { return true; } });
    // The void never appears in level rows, so give its projected
    // grid char a name here (the kernel projection falls back to it).
    api.onLevelLoad(function (state) {
      if (!state.chars.object['crumble:crumbling']) {
        state.chars.object['crumble:crumbling'] = 'C';
      }
      state.chars.object['crumble:void'] = 'V';
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] !== 'crumble:crumbling') continue;
          const meta = state.meta[x + ',' + y] || {};
          const deadline = meta.crumble_deadline || 0;
          if (!deadline || state.steps < deadline) continue;
          if (player && player.x === x && player.y === y) {
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'crumble_deadline', value: 0 });
          } else {
            fx.push({ type: 'setObject', x: x, y: y,
              def: 'crumble:void' });
          }
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerCrumblingPack;
  }
  root.GamePackCrumbling = registerCrumblingPack;
})(typeof window !== 'undefined' ? window : globalThis);
