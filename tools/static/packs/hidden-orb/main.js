// Pack: hidden orb (mech-16-hidden-orb sanity check).
// The orb exists on its tile whether lit or not; it is only drawn
// inside the player's light radius (Chebyshev distance <= 2, per
// dark-room mechanic 51). Visibility is a pure function of player
// position and orb position - no wall-clock, no hidden state.
// Collecting works lit or not (walking onto it), counts toward gate.
// UMD: browser global GamePackHiddenOrb + Node export.
(function (root) {
  'use strict';
  var LIGHT_RADIUS = 2;
  function isLit(player, x, y) {
    if (!player) return false;
    return Math.max(Math.abs(x - player.x), Math.abs(y - player.y)) <= LIGHT_RADIUS;
  }
  function registerHiddenOrbPack(api) {
    api.defineAsset('hidden-orb.png', { pack: 'hidden-orb', bundled: true });
    api.defineTile('hidden:hidden-orb', { layer: 'object',
      sprite: 'hidden-orb.png', glyph: 'H',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'incCounter', key: 'core:orbs_left', by: -1 });
      } });
    api.onLevelLoad(function (state) {
      let n = 0;
      for (const row of state.objects) for (const id of row) if (id === 'hidden:hidden-orb') n++;
      if (n) state.counters['core:orbs_left'] = (state.counters['core:orbs_left'] || 0) + n;
    });
    api.onLevelDefs(function (level, ch, e) {
      if (ch === 'H') return 'hidden:hidden-orb';
      return null;
    });
  }
  registerHiddenOrbPack.LIGHT_RADIUS = LIGHT_RADIUS;
  registerHiddenOrbPack.isLit = isLit;
  if (typeof module !== 'undefined' && module.exports) module.exports = registerHiddenOrbPack;
  root.GamePackHiddenOrb = registerHiddenOrbPack;
})(typeof window !== 'undefined' ? window : globalThis);
