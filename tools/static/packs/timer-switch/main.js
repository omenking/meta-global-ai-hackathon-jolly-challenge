// Pack: timer switch (mech-25-timer-switch sanity check).
// Pressing the switch opens its linked door and starts a visible
// 5-second countdown on the door; at zero the door closes, and
// pressing again resets the countdown to five. The countdown is
// deterministic: the deadline is recorded state (press t_ms +
// 5000) and every advance derives from the recorded input t_ms
// in the pure step function. No rule reads wall-clock time.
// The remaining seconds live in the door cell meta
// (timer_secs_left / timer_deadline_ms) so render and tests read
// state, never a clock. Restart rebuilds via initialState.
// UMD: browser global GamePackTimerSwitch + Node export.
(function (root) {
  'use strict';
  var WINDOW_MS = 5000;
  function registerTimerSwitchPack(api) {
    for (const name of ['timer-switch-ready.png',
      'timer-switch-running.png', 'door-closed.png',
      'door-open.png', 'timer-countdown.png']) {
      api.defineAsset(name, { pack: 'timer-switch', bundled: true });
    }
    function linkedDoors(state, cell) {
      const out = [];
      const links = state.links || {};
      for (const group of Object.keys(links)) {
        const cells = links[group] || [];
        if (!cells.some((c) => c.x === cell.x && c.y === cell.y)) continue;
        for (const c of cells) {
          if (state.objects[c.y] && state.objects[c.y][c.x]
              && String(state.objects[c.y][c.x]).indexOf('timer:door') === 0) {
            out.push(c);
          }
        }
      }
      return out;
    }
    api.defineTile('timer:switch', { layer: 'object',
      sprite: 'timer-switch-ready.png', glyph: 'S',
      onEnter: function (state, cell, actor, fx) {
        const deadline = state.t_ms + WINDOW_MS;
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'timer_running', value: true });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'timer_deadline_ms', value: deadline });
        for (const d of linkedDoors(state, cell)) {
          fx.push({ type: 'setObject', x: d.x, y: d.y,
            def: 'timer:door-open' });
          fx.push({ type: 'setMeta', x: d.x, y: d.y,
            key: 'timer_deadline_ms', value: deadline });
          fx.push({ type: 'setMeta', x: d.x, y: d.y,
            key: 'timer_secs_left', value: 5 });
        }
      } });
    api.defineTile('timer:door-closed', { layer: 'object',
      sprite: 'door-closed.png', glyph: 'D',
      blocks: function () { return true; } });
    api.defineTile('timer:door-open', { layer: 'object',
      sprite: 'door-open.png', glyph: 'O' });
    api.onLevelLoad(function (state) {
      if (!state.chars.object['timer:switch']) {
        state.chars.object['timer:switch'] = 'S';
      }
      if (!state.chars.object['timer:door-closed']) {
        state.chars.object['timer:door-closed'] = 'D';
      }
      state.chars.object['timer:door-open'] = 'O';
    });
    // Countdown tick: derive remaining seconds from recorded
    // t_ms and the stored deadline; close at zero.
    api.onTick(function (state, fx) {
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] !== 'timer:door-open') continue;
          const meta = (state.meta && state.meta[x + ',' + y]) || {};
          const deadline = meta.timer_deadline_ms;
          if (typeof deadline !== 'number') continue;
          if (state.t_ms >= deadline) {
            fx.push({ type: 'setObject', x: x, y: y,
              def: 'timer:door-closed' });
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'timer_secs_left', value: 0 });
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'timer_deadline_ms', value: null });
          } else {
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'timer_secs_left',
              value: Math.ceil((deadline - state.t_ms) / 1000) });
          }
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerTimerSwitchPack;
  }
  root.GamePackTimerSwitch = registerTimerSwitchPack;
})(typeof window !== 'undefined' ? window : globalThis);
