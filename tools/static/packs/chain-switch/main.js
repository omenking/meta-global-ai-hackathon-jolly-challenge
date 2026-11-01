// Pack: chain switch (mech-28-chain-switch sanity check).
// Three switches carry order marks (1, 2, 3). Pressing them in
// order lights each in turn, and pressing the last one opens the
// linked chain door. Pressing any switch out of order resets the
// whole chain: every lit switch goes unlit and the progress count
// returns to zero, so the player starts again from switch 1 and is
// never stranded. Once the chain is complete the door stays open
// and further presses do nothing. Progress lives in the counter
// chain:progress (chain:total is counted at level load); lit and
// open states are object defs swapped through setObject effects,
// so all state advances only through the pure step function and
// no rule reads wall-clock time. Restart restores every switch
// unlit and the door closed because a fresh initialState rebuilds
// the room. UMD: browser global GamePackChainSwitch + Node export.
(function (root) {
  'use strict';
  function registerChainSwitchPack(api) {
    for (const name of ['chain-switch-unlit.png', 'chain-switch-lit.png',
      'door-closed.png', 'door-open.png']) {
      api.defineAsset(name, { pack: 'chain-switch', bundled: true });
    }
    function scanObjects(state, fn) {
      for (let y = 0; y < state.objects.length; y++) {
        for (let x = 0; x < state.objects[y].length; x++) {
          fn(state.objects[y][x], x, y);
        }
      }
    }
    function press(order) {
      return function (state, cell, actor, fx) {
        const progress = state.counters['chain:progress'] || 0;
        const total = state.counters['chain:total'] || 3;
        if (progress >= total) return;
        if (order === progress + 1) {
          fx.push({ type: 'setObject', x: cell.x, y: cell.y,
            def: 'chain:switch-' + order + '-lit' });
          fx.push({ type: 'incCounter', key: 'chain:progress', by: 1 });
          if (order === total) {
            scanObjects(state, function (id, x, y) {
              if (id === 'chain:door') {
                fx.push({ type: 'setObject', x: x, y: y,
                  def: 'chain:door-open' });
              }
            });
          }
        } else {
          scanObjects(state, function (id, x, y) {
            const m = /^chain:switch-(\d+)-lit$/.exec(id || '');
            if (m) {
              fx.push({ type: 'setObject', x: x, y: y,
                def: 'chain:switch-' + m[1] });
            }
          });
          if (progress > 0) {
            fx.push({ type: 'incCounter', key: 'chain:progress',
              by: -progress });
          }
        }
      };
    }
    for (const order of [1, 2, 3]) {
      api.defineTile('chain:switch-' + order, { layer: 'object',
        sprite: 'chain-switch-unlit.png', glyph: String(order),
        onEnter: press(order) });
      api.defineTile('chain:switch-' + order + '-lit', { layer: 'object',
        sprite: 'chain-switch-lit.png', glyph: String(order),
        onEnter: press(order) });
    }
    api.defineTile('chain:door', { layer: 'object',
      sprite: 'door-closed.png', glyph: 'D',
      blocks: function (state) {
        const total = state.counters['chain:total'] || 3;
        return (state.counters['chain:progress'] || 0) < total;
      } });
    api.defineTile('chain:door-open', { layer: 'object',
      sprite: 'door-open.png', glyph: 'D',
      blocks: function () { return false; } });
    api.onLevelLoad(function (state) {
      let total = 0;
      scanObjects(state, function (id) {
        if (/^chain:switch-\d+(-lit)?$/.test(id || '')) total++;
      });
      state.counters['chain:total'] = total;
      if (typeof state.counters['chain:progress'] !== 'number') {
        state.counters['chain:progress'] = 0;
      }
      for (const order of [1, 2, 3]) {
        state.chars.object['chain:switch-' + order + '-lit'] = String(order);
      }
      state.chars.object['chain:door-open'] = 'D';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerChainSwitchPack;
  }
  root.GamePackChainSwitch = registerChainSwitchPack;
})(typeof window !== 'undefined' ? window : globalThis);
