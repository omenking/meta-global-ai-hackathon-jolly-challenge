// Pack: glass tile (mech-46-glass-tile sanity check).
// Glass over a drop allows exactly one return crossing, unlike
// crumbling (mech-5). First crossing cracks it: leaving an intact
// tile sets glass_stage 1 (cracked, still safe to stand on).
// Second crossing shatters it: leaving a cracked tile replaces it
// with glass:void behind the player. Standing/turning/blocked
// pushes never advance the stage because only onExit fires, never
// onEnter. The void is blocked (pressing toward it does not move
// the player per the YAML adversarial case); the room always has
// the long-way route or restart, so no state is stranded. Restart
// restores intact glass because a fresh initialState rebuilds the
// room. All state advances through the pure step function; no
// rule reads wall-clock time.
// UMD: browser global GamePackGlassTile + Node export (register fn).
(function (root) {
  'use strict';
  function registerGlassPack(api) {
    for (const name of ['glass.png', 'glass-cracked.png', 'void.png']) {
      api.defineAsset(name, { pack: 'glass-tile', bundled: true });
    }
    api.defineTile('glass:glass', { layer: 'object',
      sprite: 'glass.png', glyph: 'g',
      onExit: function (state, cell, actor, fx) {
        const stage = (cell.meta && cell.meta.glass_stage) || 0;
        if (stage >= 1) {
          fx.push({ type: 'setObject', x: cell.x, y: cell.y,
            def: 'glass:void' });
        } else {
          fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
            key: 'glass_stage', value: 1 });
        }
      } });
    api.defineTile('glass:void', { layer: 'object',
      sprite: 'void.png', glyph: 'V',
      blocks: function () { return true; } });
    api.onLevelLoad(function (state) {
      if (!state.chars.object['glass:glass']) {
        state.chars.object['glass:glass'] = 'g';
      }
      state.chars.object['glass:void'] = 'V';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerGlassPack;
  }
  root.GamePackGlassTile = registerGlassPack;
})(typeof window !== 'undefined' ? window : globalThis);
