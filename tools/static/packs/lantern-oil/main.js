// Pack: lantern oil (mech-65-lantern-oil sanity check).
// Lantern oil is a consumable spent on collection: stepping on it
// refills the lantern to full (100). In a dark room (any room with
// an oil pickup) the lantern burns down deterministically from the
// recorded t_ms on each input — 5 fuel per 100 ms of recorded
// time, never a wall-clock read — and the lit radius shrinks with
// the fuel, stopping at the base radius (1); the light never goes
// out. The conditional HUD gauge is the lantern:fuel counter,
// present only in dark rooms. Restart restores the oil and the
// starting fuel because a fresh initialState rebuilds the room.
// UMD: browser global GamePackLanternOil + Node export.
(function (root) {
  'use strict';
  var FULL = 100, START = 60, BASE_RADIUS = 1, FULL_RADIUS = 4;
  function radiusFor(fuel) {
    var f = Math.max(0, Math.min(FULL, fuel || 0));
    return BASE_RADIUS + Math.round((f / FULL) * (FULL_RADIUS - BASE_RADIUS));
  }
  function registerLanternOilPack(api) {
    for (const name of ['lantern-oil.png', 'lantern-oil-collected.png',
      'jolly-lantern-full.png', 'jolly-lantern-low.png',
      'lantern-fuel-gauge-full.png', 'lantern-fuel-gauge-low.png']) {
      api.defineAsset(name, { pack: 'lantern-oil', bundled: true });
    }
    api.defineTile('lantern:oil', { layer: 'object',
      sprite: 'lantern-oil.png', glyph: 'o',
      onEnter: function (state, cell, actor, fx) {
        var cur = state.counters['lantern:fuel'] || 0;
        fx.push({ type: 'incCounter', key: 'lantern:fuel', by: FULL - cur });
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'lantern:oil-collected' });
      } });
    api.defineTile('lantern:oil-collected', { layer: 'object',
      sprite: 'lantern-oil-collected.png', glyph: '.' });
    api.onLevelLoad(function (state) {
      var dark = false;
      for (const row of state.objects) for (const id of row) {
        if (id === 'lantern:oil') dark = true;
      }
      if (!dark) return;
      state.counters['lantern:fuel'] = START;
      state.counters['lantern:radius'] = radiusFor(START);
      state.flags['lantern:dark'] = true;
      state.flags['lantern:last_ms'] = 0;
      state.chars.object['lantern:oil'] = 'o';
      state.chars.object['lantern:oil-collected'] = '.';
    });
    // Burn only from recorded time: the delta between this input's
    // t_ms and the last recorded t_ms, so replay is exact.
    api.onTick(function (state) {
      if (!state.flags['lantern:dark']) return;
      var last = state.flags['lantern:last_ms'] || 0;
      var delta = Math.max(0, (state.t_ms || 0) - last);
      state.flags['lantern:last_ms'] = state.t_ms || 0;
      var fuel = (state.counters['lantern:fuel'] || 0) - delta / 25;
      fuel = Math.max(0, Math.min(FULL, fuel));
      state.counters['lantern:fuel'] = fuel;
      state.counters['lantern:radius'] = radiusFor(fuel);
    });
  }
  registerLanternOilPack.FULL = FULL;
  registerLanternOilPack.START = START;
  registerLanternOilPack.BASE_RADIUS = BASE_RADIUS;
  registerLanternOilPack.FULL_RADIUS = FULL_RADIUS;
  registerLanternOilPack.radiusFor = radiusFor;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerLanternOilPack;
  }
  root.GamePackLanternOil = registerLanternOilPack;
})(typeof window !== 'undefined' ? window : globalThis);
