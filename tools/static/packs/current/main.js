// Pack: current tile (mech-42-current-tile sanity check).
// While the player is on a current (water) tile, the current
// carries them one tile downstream at the start of each move,
// then they make their own move. Banks and islands are plain
// floor: no drift happens there, and a player carried past a
// 1-wide banked exit can still swim on to a later bank. The
// drift is a terrain onBeforeMove hook: the kernel applies it
// once, before the player's voluntary move, through tryMove,
// so a wall downstream blocks the drift. State advances only
// through the pure step function; no wall-clock reads.
// Life preserver (mech 61) is not built yet: the preserver is
// permission to be on the water, not control against the
// current, so this pack does not gate the drift on an item.
// UMD: browser global GamePackCurrent + Node export.
(function (root) {
  'use strict';
  function registerCurrentPack(api) {
    for (const name of ['current-north.png', 'current-east.png',
      'current-south.png', 'current-west.png', 'jolly-swimming.png']) {
      api.defineAsset(name, { pack: 'current', bundled: true });
    }
    const DIRS = { north: 'up', east: 'right', south: 'down', west: 'left' };
    const GLYPHS = { north: '^', east: '>', south: 'v', west: '<' };
    for (const dir of Object.keys(DIRS)) {
      api.defineTile('current:current-' + dir, { layer: 'terrain',
        sprite: 'current-' + dir + '.png', glyph: GLYPHS[dir],
        onBeforeMove: function () { return DIRS[dir]; } });
    }
    api.onLevelLoad(function (state) {
      for (const dir of Object.keys(DIRS)) {
        const id = 'current:current-' + dir;
        if (!state.chars.terrain[id]) state.chars.terrain[id] = GLYPHS[dir];
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerCurrentPack;
  }
  root.GamePackCurrent = registerCurrentPack;
})(typeof window !== 'undefined' ? window : globalThis);
