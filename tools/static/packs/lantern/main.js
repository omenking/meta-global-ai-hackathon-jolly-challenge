// Pack: lantern (mech-52-lantern sanity check).
// Picking up the lantern widens the light radius from two tiles
// to four for that room only; stepping on the room exit ends it.
// It is not consumed by time: no tick hook touches the radius, so
// waiting never shrinks it. The radius lives in counters
// (lantern:held / lantern:radius) set on level load and changed
// only by the pickup/exit tile effects through the pure step
// function; no rule reads wall-clock time. Visibility is a pure
// function of player position and radius (Chebyshev distance).
// Its fuel partner is lantern oil (mech 65) elsewhere: no fuel
// drains here, so the held item carries no gauge or timer.
// UMD: browser global GamePackLantern + Node export (register fn).
(function (root) {
  'use strict';
  var BASE_RADIUS = 2;
  var LANTERN_RADIUS = 4;
  function lightRadius(state) {
    var r = state && state.counters && state.counters['lantern:radius'];
    return typeof r === 'number' ? r : BASE_RADIUS;
  }
  function hasLantern(state) {
    return !!(state && state.counters
      && state.counters['lantern:held'] > 0);
  }
  function playerOf(state) {
    if (state.player) return state.player;
    var a = (state.actors || []).find(function (ac) {
      return ac.id === 'player';
    }) || (state.actors || [])[0];
    return a ? { x: a.x, y: a.y } : null;
  }
  function isLit(state, x, y) {
    var p = playerOf(state);
    if (!p) return false;
    return Math.max(Math.abs(x - p.x), Math.abs(y - p.y))
      <= lightRadius(state);
  }
  function registerLanternPack(api) {
    for (const name of ['lantern.png', 'lantern-room-floor.png',
      'jolly-with-lantern.png', 'jolly-without-lantern.png',
      'lantern-held.png']) {
      api.defineAsset(name, { pack: 'lantern', bundled: true });
    }
    api.defineItem('lantern:lantern-item', {
      icon: 'lantern-held.png', readout: 'lantern' });
    api.defineTile('lantern:lantern', { layer: 'object',
      sprite: 'lantern.png', glyph: 'L',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'giveItem', item: 'lantern:lantern-item' });
        fx.push({ type: 'incCounter', key: 'lantern:held', by: 1 });
        fx.push({ type: 'incCounter', key: 'lantern:radius',
          by: LANTERN_RADIUS - BASE_RADIUS });
      } });
    api.defineTile('lantern:exit', { layer: 'object',
      sprite: 'gate.png', glyph: 'E',
      onEnter: function (state, cell, actor, fx) {
        if (!hasLantern(state)) return;
        fx.push({ type: 'consumeItem', item: 'lantern:lantern-item' });
        fx.push({ type: 'incCounter', key: 'lantern:held', by: -1 });
        fx.push({ type: 'incCounter', key: 'lantern:radius',
          by: BASE_RADIUS - LANTERN_RADIUS });
      } });
    api.onLevelLoad(function (state) {
      let has = false;
      for (const row of state.objects) for (const id of row) {
        if (id === 'lantern:lantern' || id === 'lantern:exit') has = true;
      }
      if (!has) return;
      state.counters['lantern:held'] = 0;
      state.counters['lantern:radius'] = BASE_RADIUS;
    });
    api.onLevelDefs(function (level, ch, e) {
      if (ch === 'L') return 'lantern:lantern';
      if (ch === 'E') return 'lantern:exit';
      return null;
    });
  }
  registerLanternPack.BASE_RADIUS = BASE_RADIUS;
  registerLanternPack.LANTERN_RADIUS = LANTERN_RADIUS;
  registerLanternPack.lightRadius = lightRadius;
  registerLanternPack.hasLantern = hasLantern;
  registerLanternPack.isLit = isLit;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerLanternPack;
  }
  root.GamePackLantern = registerLanternPack;
})(typeof window !== 'undefined' ? window : globalThis);
