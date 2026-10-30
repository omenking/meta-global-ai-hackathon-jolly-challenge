// Pack: keys and locks (first extracted pack, Phase 2).
// Registers keys:key-<color> pickup tiles/items and keys:lock-<color>
// tiles from the level legend (key_color/lock_color shim). Removing
// this file (and its script tag / require) disables only keys/locks.
// UMD: browser global GamePackKeysLocks + Node export (register fn).
(function (root) {
  'use strict';
  function registerKeysPack(api) {
    api.onLevelDefs(function (level, ch, e) {
      if (!ch || !e) return null;
      if (e.key_color) {
        const color = e.key_color, itemId = 'keys:key-' + color;
        api.defineItem(itemId, { icon: 'key_' + color + '.png', readout: color });
        api.defineTile(itemId, { layer: 'object', sprite: 'key_' + color + '.png',
          // Full 8-slot inventory: the key stays and blocks, as before.
          blocks: function (state) { return state.inventory.length >= 8; },
          onEnter: function (state, cell, actor, fx) {
            fx.push({ type: 'giveItem', item: itemId });
            fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          } });
        return itemId;
      }
      if (e.lock_color) {
        const color = e.lock_color, tileId = 'keys:lock-' + color,
          itemId = 'keys:key-' + color;
        api.defineTile(tileId, { layer: 'object',
          sprite: 'wall_keyhole_' + color + '.png',
          blocks: function (state) {
            return !state.inventory.some((en) => en.item === itemId);
          },
          onEnter: function (state, cell, actor, fx) {
            fx.push({ type: 'consumeItem', item: itemId });
            fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          } });
        return tileId;
      }
      return null;
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = registerKeysPack;
  root.GamePackKeysLocks = registerKeysPack;
})(typeof window !== 'undefined' ? window : globalThis);
