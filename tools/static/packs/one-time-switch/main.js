// Pack: one-time switch (mech-27-one-time-switch sanity check).
// First press fires its linked door permanently and the switch
// breaks (sprite changes to broken); it never resets in the attempt.
// Pressing/standing on the broken switch does nothing. Restart
// restores intact+closed because a fresh initialState rebuilds.
// All state advances through the pure step function; no wall-clock.
// Link: legend entries for switch and door share link:"exit"; the
// kernel records those object positions in state.links. On press,
// every linked switch:door-closed becomes switch:door-open.
// UMD: browser global GamePackOneTimeSwitch + Node export.
(function (root) {
  'use strict';
  function registerOneTimeSwitchPack(api) {
    for (const name of ['one-time-switch-intact.png',
      'one-time-switch-broken.png', 'door-closed.png', 'door-open.png']) {
      api.defineAsset(name, { pack: 'one-time-switch', bundled: true });
    }
    api.defineTile('switch:one-time-intact', { layer: 'object',
      sprite: 'one-time-switch-intact.png', glyph: 'S',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'switch:one-time-broken' });
        const seen = new Set();
        for (const group of Object.values(state.links || {})) {
          for (const p of group || []) {
            const k = p.x + ',' + p.y;
            if (seen.has(k)) continue; seen.add(k);
            if (state.objects[p.y] && state.objects[p.y][p.x] === 'switch:door-closed') {
              fx.push({ type: 'setObject', x: p.x, y: p.y,
                def: 'switch:door-open' });
            }
          }
        }
        // Fallback if no link group recorded: open any closed door.
        if (!Object.keys(state.links || {}).length) {
          for (let y = 0; y < state.objects.length; y++) {
            for (let x = 0; x < state.objects[y].length; x++) {
              if (state.objects[y][x] === 'switch:door-closed') {
                fx.push({ type: 'setObject', x: x, y: y, def: 'switch:door-open' });
              }
            }
          }
        }
      } });
    api.defineTile('switch:one-time-broken', { layer: 'object',
      sprite: 'one-time-switch-broken.png', glyph: 'B' });
    api.defineTile('switch:door-closed', { layer: 'object',
      sprite: 'door-closed.png', glyph: 'D',
      blocks: function () { return true; } });
    api.defineTile('switch:door-open', { layer: 'object',
      sprite: 'door-open.png', glyph: 'O' });
    api.onLevelLoad(function (state) {
      if (!state.chars.object['switch:one-time-intact']) {
        state.chars.object['switch:one-time-intact'] = 'S';
      }
      state.chars.object['switch:one-time-broken'] = 'B';
      if (!state.chars.object['switch:door-closed']) {
        state.chars.object['switch:door-closed'] = 'D';
      }
      state.chars.object['switch:door-open'] = 'O';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerOneTimeSwitchPack;
  }
  root.GamePackOneTimeSwitch = registerOneTimeSwitchPack;
})(typeof window !== 'undefined' ? window : globalThis);
