// Pack: hourglass (mech-69-hourglass sanity check).
// Stepping on the hourglass tile collects it at once (it never
// enters the inventory and cannot be saved for later) and freezes
// the level timer for 10 real seconds while the player keeps
// moving, shown by a frozen timer display. The freeze is
// deterministic: collection records the step's t_ms in counters,
// and the timer hook derives the effective elapsed time from
// recorded t_ms only, so the held value lasts exactly 10 real
// seconds however many moves are made inside it, then the timer
// resumes from the value it held. Collecting a second hourglass
// banks any elapsed part of the previous freeze and starts a
// fresh 10 seconds. Restart restores the hourglass because a
// fresh initialState rebuilds the room. No rule reads wall-clock.
// UMD: browser global GamePackHourglass + Node export (register fn).
(function (root) {
  'use strict';
  var FREEZE_MS = 10000;
  function effectiveElapsedS(prev, tMs) {
    var c = (prev && prev.counters) || {};
    if (!c['hourglass:collected']) return tMs / 1000;
    var collect = c['hourglass:collect_ms'];
    var offset = c['hourglass:offset_ms'] || 0;
    if (typeof collect !== 'number' || collect < 0) return tMs / 1000;
    var frozen = Math.min(Math.max(tMs - collect, 0), FREEZE_MS);
    return (tMs - offset - frozen) / 1000;
  }
  function registerHourglassPack(api) {
    for (const name of ['hourglass.png', 'hourglass-spent.png',
      'timer-frozen.png']) {
      api.defineAsset(name, { pack: 'hourglass', bundled: true });
    }
    api.defineTile('hourglass:hourglass', { layer: 'object',
      sprite: 'hourglass.png', glyph: 'H',
      onEnter: function (state, cell, actor, fx) {
        var c = state.counters || {};
        var offset = c['hourglass:offset_ms'] || 0;
        if (c['hourglass:collected']) {
          var prev = c['hourglass:collect_ms'];
          if (typeof prev === 'number' && prev >= 0) {
            offset += Math.min(Math.max(state.t_ms - prev, 0), FREEZE_MS);
          }
        }
        fx.push({ type: 'setCounter', key: 'hourglass:collect_ms',
          value: state.t_ms });
        fx.push({ type: 'setCounter', key: 'hourglass:offset_ms',
          value: offset });
        fx.push({ type: 'setCounter', key: 'hourglass:collected',
          value: 1 });
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'hourglass:spent' });
      } });
    api.defineTile('hourglass:spent', { layer: 'object',
      sprite: 'hourglass-spent.png', glyph: 'h' });
    api.onTimer(function (prev, tMs) {
      return effectiveElapsedS(prev, tMs);
    });
    api.onLevelLoad(function (state) {
      var found = false;
      for (const row of state.objects) {
        for (const id of row) if (id === 'hourglass:hourglass') found = true;
      }
      if (found) {
        state.counters['hourglass:collected'] = 0;
        state.counters['hourglass:collect_ms'] = -1;
        state.counters['hourglass:offset_ms'] = 0;
      }
      if (!state.chars.object['hourglass:hourglass']) {
        state.chars.object['hourglass:hourglass'] = 'H';
      }
      state.chars.object['hourglass:spent'] = 'h';
    });
  }
  registerHourglassPack.FREEZE_MS = FREEZE_MS;
  registerHourglassPack.effectiveElapsedS = effectiveElapsedS;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerHourglassPack;
  }
  root.GamePackHourglass = registerHourglassPack;
})(typeof window !== 'undefined' ? window : globalThis);
