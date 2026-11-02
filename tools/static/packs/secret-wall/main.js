// Pack: secret wall (mech-59-secret-wall sanity check).
// A secret wall is drawn exactly as a wall but has no collision:
// the player walks straight through it. The first time the player
// walks through, its sprite fades (the tile swaps to the found
// variant) so the opening stays known for the attempt, and it
// stays passable in both directions. Restart restores the unfaded
// wall because a fresh initialState rebuilds the room. All state
// advances through the pure step function; no rule reads wall-clock.
// UMD: browser global GamePackSecretWall + Node export (register fn).
(function (root) {
  'use strict';
  function registerSecretWallPack(api) {
    // Bundled assets (see manifest.json): real generated art.
    for (const name of ['secret-wall.png', 'secret-wall-faded.png',
      'wall.png', 'jolly-through-wall.png']) {
      api.defineAsset(name, { pack: 'secret-wall', bundled: true });
    }
    api.defineTile('secret:wall', { layer: 'object',
      sprite: 'secret-wall.png', glyph: 'S',
      // No blocks(): appearance is the only secret. Entering marks
      // the wall found by swapping to the faded variant.
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'secret:wall-found' });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'secret_found', value: true });
      } });
    api.defineTile('secret:wall-found', { layer: 'object',
      sprite: 'secret-wall-faded.png', glyph: 's' });
    // The found variant never appears in level rows, so give its
    // projected grid char a name here (kernel projection falls
    // back to it), mirroring the crumbling pack's void handling.
    api.onLevelLoad(function (state) {
      if (!state.chars.object['secret:wall']) {
        state.chars.object['secret:wall'] = 'S';
      }
      state.chars.object['secret:wall-found'] = 's';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerSecretWallPack;
  }
  root.GamePackSecretWall = registerSecretWallPack;
})(typeof window !== 'undefined' ? window : globalThis);
