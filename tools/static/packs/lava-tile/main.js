// Pack: lava tile (mech-44-lava-tile sanity check).
// Static lethal lava: a fixed terrain tile that never spreads,
// never burns out and is never cancelled. Entering it loses the
// attempt. Unlike fire (mech 43) there is no cancel rule and no
// tick hook, so lava can only be routed around (or, once the dirt
// block lands per mechanic 90, filled). Ice blocks (mechanic 82)
// pushed into lava melt while the lava stays; that interaction
// arrives with the pushable-block mechanic and is not faked here.
// All state advances through the pure step function; no rule
// reads wall-clock time. Restart restores the room because a
// fresh initialState rebuilds it. UMD: browser global
// GamePackLavaTile + Node export (register fn).
(function (root) {
  'use strict';
  function registerLavaPack(api) {
    api.defineAsset('lava.png', { pack: 'lava-tile', bundled: true });
    api.defineTile('lava:lava', { layer: 'terrain',
      sprite: 'lava.png', glyph: 'L',
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
        return null;
      } });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerLavaPack;
  }
  root.GamePackLavaTile = registerLavaPack;
})(typeof window !== 'undefined' ? window : globalThis);
