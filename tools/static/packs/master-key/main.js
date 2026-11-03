// Pack: master key (mech-12-master-key sanity check).
// A silver key that fits any lock, then breaks: pressing it into a
// lock of any colour consumes the master key and dissolves that one
// lock only. When the player holds both the matching coloured key
// and the master key, the coloured key is spent first, so fetching
// the coloured key is how the master is saved for a colour that
// cannot be found. All state advances through the pure step
// function; no rule reads wall-clock time.
// UMD: browser global GamePackMasterKey + Node export (register fn).
(function (root) {
  'use strict';
  var COLOURS = ['red', 'gold', 'green', 'blue', 'silver'];
  function registerMasterKeyPack(api) {
    api.defineAsset('master-key.png', { pack: 'master-key', bundled: true });
    api.defineAsset('master-key-held.png', { pack: 'master-key', bundled: true });
    api.defineItem('master:master-key', { icon: 'master-key-held.png', readout: 'master' });
    api.defineTile('master:key', { layer: 'object',
      sprite: 'master-key.png', glyph: 'M',
      blocks: function (state) { return state.inventory.length >= 8; },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: 'master:master-key' });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    COLOURS.forEach(function (colour) {
      var colourItem = 'keys:key-' + colour;
      api.defineTile('master:lock-' + colour, { layer: 'object',
        sprite: 'wall_keyhole_' + colour + '.png', glyph: 'L',
        blocks: function (state) {
          return !state.inventory.some(function (en) {
            return en.item === colourItem || en.item === 'master:master-key';
          });
        },
        onEnter: function (state, cell, actor, fx) {
          var hasColour = state.inventory.some(function (en) { return en.item === colourItem; });
          fx.push({ type: 'consumeItem', item: hasColour ? colourItem : 'master:master-key' });
          fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        } });
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMasterKeyPack;
  }
  root.GamePackMasterKey = registerMasterKeyPack;
})(typeof window !== 'undefined' ? window : globalThis);
