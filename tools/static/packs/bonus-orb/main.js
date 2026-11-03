// Pack: bonus orb (mech-20-bonus-orb sanity check).
// A bonus orb is drawn with a gold ring, is not counted in
// orbs-left and the gate does not need it. Taking it adds exactly
// 10 seconds to the timer immediately: the pickup emits an
// addTime effect and the kernel raises the level time limit by
// that amount, so the gain survives in time_left_s on this and
// every later step. The counted-orb counter is never touched, so
// the gate opens on counted orbs only. All state advances
// through the pure step function from recorded t_ms; no rule
// reads wall-clock time. Restart is a fresh initialState, which
// restores the orb and the placed time limit.
// UMD: browser global GamePackBonusOrb + Node export (register fn).
(function (root) {
  'use strict';
  function registerBonusOrbPack(api) {
    // Bundled assets (see manifest.json): real generated art.
    for (const name of ['bonus-orb.png', 'timer-gain.png']) {
      api.defineAsset(name, { pack: 'bonus-orb', bundled: true });
    }
    api.defineTile('bonus:bonus-orb', { layer: 'object',
      sprite: 'bonus-orb.png', glyph: 'B',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'addTime', seconds: 10 });
      } });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerBonusOrbPack;
  }
  root.GamePackBonusOrb = registerBonusOrbPack;
})(typeof window !== 'undefined' ? window : globalThis);
