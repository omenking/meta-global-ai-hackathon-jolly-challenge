// Pack: button linked to a trap (pressure test b).
// link:button toggles every tile sharing its link group (level legend
// link: "<group>"); link:trap blocks while its cell meta.open is not
// set. Kernel supplies only the links index + setMeta effects.
// UMD: browser global GamePackButtonsTraps + Node export.
(function (root) {
  'use strict';
  function registerButtonsTrapsPack(api) {
    api.defineTile('link:trap', { layer: 'object', sprite: 'gate.png',
      blocks: function (state, cell) {
        return !(cell.meta && cell.meta.open);
      } });
    api.defineTile('link:button', { layer: 'object',
      onEnter: function (state, cell, actor, fx) {
        for (const group of Object.keys(state.links || {})) {
          const cells = state.links[group];
          if (!cells.some((c) => c.x === cell.x && c.y === cell.y)) continue;
          for (const c of cells) {
            const cur = (state.meta[c.x + ',' + c.y] || {}).open;
            fx.push({ type: 'setMeta', x: c.x, y: c.y, key: 'open', value: !cur });
          }
        }
      } });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerButtonsTrapsPack;
  }
  root.GamePackButtonsTraps = registerButtonsTrapsPack;
})(typeof window !== 'undefined' ? window : globalThis);
