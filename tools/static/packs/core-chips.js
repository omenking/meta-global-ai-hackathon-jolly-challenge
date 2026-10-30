// Pack: core Chips mechanics (Phase 3) — floor/wall/spawn/info,
// orbs + gate, warp, and the timer lose rule, all registered through
// the same pack API as keys-locks and future packs. The exit tile is
// named warp (human decision 2026-10-30): def core:warp.
// UMD: browser global GamePackCoreChips + Node export (register fn).
(function (root) {
  'use strict';
  function registerCorePack(api) {
    api.defineTile('core:floor', { layer: 'terrain', sprite: 'floor_default.png' });
    api.defineTile('core:spawn', { layer: 'terrain', sprite: 'floor_default.png' });
    api.defineTile('core:wall', { layer: 'terrain', sprite: 'wall.png',
      blocks: function () { return true; } });
    api.defineTile('core:info', { layer: 'terrain',
      blocks: function () { return true; } });
    api.defineTile('core:unknown', { layer: 'terrain',
      blocks: function () { return true; } });
    api.defineTile('core:orb', { layer: 'object', sprite: 'orb.png',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'incCounter', key: 'core:orbs_left', by: -1 });
      } });
    api.defineTile('core:gate', { layer: 'object', sprite: 'gate.png',
      blocks: function (state) { return (state.counters['core:orbs_left'] || 0) > 0; } });
    api.defineTile('core:warp', { layer: 'object', sprite: 'portal.png',
      onEnter: function (state, cell, actor, fx) { fx.push({ type: 'win' }); } });
    api.onLevelLoad(function (state) {
      let n = 0;
      for (const row of state.objects) for (const id of row) if (id === 'core:orb') n++;
      state.counters['core:orbs_left'] = n;
    });
    // Timer rule: the kernel owns the clock; this pack decides that
    // reaching the limit loses the run (an untimed mode omits it).
    api.onTick(function (state, fx) {
      if (state.time_limit_s !== null && state.time_limit_s !== undefined
          && state.elapsed_s >= state.time_limit_s) fx.push({ type: 'lose' });
    });
    api.onLevelDefs(function (level, ch, e) {
      if (!ch) return null;
      if (ch === '.') return 'core:floor';
      if (ch === '#') return 'core:wall';
      if (ch === 'P') return 'core:spawn';
      if (ch === '*' || ch === 'O') return 'core:orb';
      if (ch === 'G') return 'core:gate';
      if (ch === 'X') return 'core:warp';
      if (ch === '?') return 'core:info';
      return null;
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = registerCorePack;
  root.GamePackCoreChips = registerCorePack;
})(typeof window !== 'undefined' ? window : globalThis);
