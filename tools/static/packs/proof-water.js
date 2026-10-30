// Pack: water + flippers (Phase 5 proof pack, KEPT per human
// decision 2026-10-30). Water terrain kills an actor that does not
// carry the flipper item; the flipper is a generic inventory item.
// Levels opt in via legend defs (def: water:water / water:flipper).
// Removing this file + water-room.json removes the mechanic.
// UMD: browser global GamePackProofWater + Node export.
(function (root) {
  'use strict';
  function registerWaterPack(api) {
    api.defineItem('water:flipper', { icon: 'key.png', readout: 'flipper' });
    api.defineTile('water:water', { layer: 'terrain',
      onEnterTerrain: function (state, cell, actor, fx) {
        const has = (state.inventory || []).some((e) => e.item === 'water:flipper');
        if (!has) fx.push({ type: 'lose' });
        return null;
      } });
    api.defineTile('water:flipper', { layer: 'object',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: 'water:flipper' });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = registerWaterPack;
  root.GamePackProofWater = registerWaterPack;
})(typeof window !== 'undefined' ? window : globalThis);
