// Pack: orb bank (mech-94-orb-bank sanity check).
// A higher-level campaign rule in one teaching room: a bonus orb
// (B) taken before the bank warp (W) is banked at the warp, and
// the bank gate (K) in the next chamber deducts its stated cost
// from that bank instead of orbs in its own chamber. Counted
// orbs (*) never bank and are never deducted by the gate. The
// bank lives in counters (bank:bank, bank:pending), so the HUD
// can show it between the chambers; all state advances through
// the pure step function and no rule reads wall-clock time.
// Restart restores the entry bank because a fresh initialState
// rebuilds counters, gate meta and both chambers.
// UMD: browser global GamePackOrbBank + Node export (register fn).
(function (root) {
  'use strict';
  function registerOrbBankPack(api) {
    // Bundled assets (see manifest.json): generated art for this pack.
    for (const name of ['bank-gate-closed.png', 'bank-gate-open.png',
      'bank-counter.png']) {
      api.defineAsset(name, { pack: 'orb-bank', bundled: true });
    }
    // Shared art reused from level-sprites (declared by core-chips;
    // re-declared here so the pack names everything it renders).
    api.defineAsset('orb.png', { pack: 'orb-bank', bundled: false });
    api.defineAsset('portal.png', { pack: 'orb-bank', bundled: false });

    api.defineTile('bank:bonus-orb', { layer: 'object',
      sprite: 'orb.png', glyph: 'B',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'incCounter', key: 'bank:pending', by: 1 });
      } });
    api.defineTile('bank:entry', { layer: 'object',
      sprite: 'floor_default.png', glyph: 'E' });
    api.defineTile('bank:warp', { layer: 'object',
      sprite: 'portal.png', glyph: 'W',
      onEnter: function (state, cell, actor, fx) {
        const pending = state.counters['bank:pending'] || 0;
        if (pending) {
          fx.push({ type: 'incCounter', key: 'bank:bank', by: pending });
          fx.push({ type: 'incCounter', key: 'bank:pending', by: -pending });
        }
        const dest = (state.links && state.links['bank-warp-in'] || [])[0];
        if (dest) fx.push({ type: 'teleport', actor: 'player',
          x: dest.x, y: dest.y });
      } });
    api.defineTile('bank:gate', { layer: 'object',
      sprite: 'bank-gate-closed.png', glyph: 'K',
      blocks: function (state, cell) {
        if (cell.meta && cell.meta.bank_paid) return false;
        const cost = (cell.meta && cell.meta.bank_cost) || 1;
        return (state.counters['bank:bank'] || 0) < cost;
      },
      onEnter: function (state, cell, actor, fx) {
        if (cell.meta && cell.meta.bank_paid) return;
        const cost = (cell.meta && cell.meta.bank_cost) || 1;
        fx.push({ type: 'incCounter', key: 'bank:bank', by: -cost });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'bank_paid', value: true });
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'bank:gate-open' });
      } });
    api.defineTile('bank:gate-open', { layer: 'object',
      sprite: 'bank-gate-open.png', glyph: 'k' });
    // The open gate never appears in level rows, so give its
    // projected grid char a name here (kernel projection fallback).
    api.onLevelLoad(function (state, level) {
      if (typeof state.counters['bank:bank'] !== 'number') {
        state.counters['bank:bank'] = 0;
      }
      if (typeof state.counters['bank:pending'] !== 'number') {
        state.counters['bank:pending'] = 0;
      }
      state.chars.object['bank:gate-open'] = 'k';
      // Per-gate cost comes from the level legend (bank_cost);
      // it lives in cell meta so blocks/onEnter stay pure.
      const rows = (level && level.rows) || [];
      const legend = (level && level.legend) || {};
      for (let y = 0; y < rows.length; y++) {
        for (let x = 0; x < rows[y].length; x++) {
          const e = legend[rows[y][x]] || {};
          if (e.def === 'bank:gate') {
            const k = x + ',' + y;
            state.meta[k] = Object.assign({}, state.meta[k],
              { bank_cost: e.bank_cost || 1 });
          }
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerOrbBankPack;
  }
  root.GamePackOrbBank = registerOrbBankPack;
})(typeof window !== 'undefined' ? window : globalThis);
