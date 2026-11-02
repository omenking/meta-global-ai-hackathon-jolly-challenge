// Pack: orb pouch (mech-67-orb-pouch sanity check).
// A pouch level flips the orb counter: orbs walked onto count UP
// into a held pouch (counters pouch:held / pouch:collected) instead
// of orbs-left counting down. Pressing into an orb-door spends
// exactly 1 held orb and opens it; pressing into the scale spends
// exactly 2. With too few held, a press spends nothing and the tile
// blocks like a wall (kernel blocks() gate, same pattern as locks).
// The gate opens on pouch spent (pouch:spent >= 2, the scale cost),
// never on orbs collected. Warping turns every unspent held orb
// into pouch:score. All state advances only through the pure step
// function; no rule reads wall-clock. Restart is a fresh
// initialState, which re-zeroes every pouch counter and restores
// every orb, door and the scale.
// UMD: browser global GamePackOrbPouch + Node export (register fn).
(function (root) {
  'use strict';
  var DOOR_COST = 1, SCALE_COST = 2, GATE_SPENT = 2;
  function held(state) { return (state.counters && state.counters['pouch:held']) || 0; }
  function registerOrbPouchPack(api) {
    api.defineAsset('orb-door-closed.png', { pack: 'orb-pouch', bundled: true });
    api.defineAsset('orb-door-open.png', { pack: 'orb-pouch', bundled: true });
    api.defineAsset('pouch-counter.png', { pack: 'orb-pouch', bundled: true });
    api.defineTile('pouch:orb', { layer: 'object', sprite: 'orb.png',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'incCounter', key: 'pouch:held', by: 1 });
        fx.push({ type: 'incCounter', key: 'pouch:collected', by: 1 });
      } });
    api.defineTile('pouch:orb-door', { layer: 'object',
      sprite: 'orb-door-closed.png', glyph: 'D',
      blocks: function (state) { return held(state) < DOOR_COST; },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'incCounter', key: 'pouch:held', by: -DOOR_COST });
        fx.push({ type: 'incCounter', key: 'pouch:spent', by: DOOR_COST });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    api.defineTile('pouch:scale', { layer: 'object',
      sprite: 'pouch-counter.png', glyph: 'S',
      blocks: function (state) { return held(state) < SCALE_COST; },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'incCounter', key: 'pouch:held', by: -SCALE_COST });
        fx.push({ type: 'incCounter', key: 'pouch:spent', by: SCALE_COST });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    api.defineTile('pouch:gate', { layer: 'object', sprite: 'gate.png',
      glyph: 'G',
      blocks: function (state) {
        return ((state.counters && state.counters['pouch:spent']) || 0) < GATE_SPENT;
      } });
    api.defineTile('pouch:warp', { layer: 'object', sprite: 'portal.png',
      glyph: 'X',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'incCounter', key: 'pouch:score', by: held(state) });
        fx.push({ type: 'win' });
      } });
    api.onLevelLoad(function (state, level) {
      if (!level || level.pouch !== true) return;
      state.counters['pouch:held'] = 0;
      state.counters['pouch:collected'] = 0;
      state.counters['pouch:spent'] = 0;
      state.counters['pouch:score'] = 0;
      state.counters['pouch:gate_cost'] = GATE_SPENT;
      state.flags.pouch = true;
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerOrbPouchPack;
  }
  root.GamePackOrbPouch = registerOrbPouchPack;
})(typeof window !== 'undefined' ? window : globalThis);
