// Pack: life preserver (mech-61-life-preserver sanity check).
// Picking it up fills one inventory slot for the rest of the level.
// While held, water is walkable and each deep-water tile costs two
// moves: the first move onto a deep tile wades in place (the terrain
// hook sends the player back and marks the tile), the second crosses.
// Without it, entering deep water teleports the player to spawn
// (the checkpoint). Shallow water is always walkable in one move.
// All state advances through the pure step function; no wall-clock.
// UMD: browser global GamePackLifePreserver + Node export.
(function (root) {
  'use strict';
  var OPPOSITE = { up: 'down', down: 'up', left: 'right', right: 'left' };
  function hasPreserver(state) {
    return (state.inventory || []).some(function (e) {
      return e.item === 'preserver:life-preserver';
    });
  }
  function registerLifePreserverPack(api) {
    for (const name of ['life-preserver.png', 'life-preserver-collected.png',
      'jolly-life-preserver.png', 'jolly-wading-deep.png',
      'life-preserver-slot.png']) {
      api.defineAsset(name, { pack: 'life-preserver', bundled: true });
    }
    api.defineItem('preserver:life-preserver', {
      icon: 'life-preserver-slot.png', readout: 'life-preserver' });
    api.defineTile('preserver:preserver', { layer: 'object',
      sprite: 'life-preserver.png', glyph: 'L',
      blocks: function (state) { return state.inventory.length >= 8; },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: 'preserver:life-preserver' });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    api.defineTile('preserver:water', { layer: 'terrain',
      sprite: 'life-preserver.png', glyph: '~' });
    api.defineTile('preserver:deep', { layer: 'terrain',
      sprite: 'jolly-wading-deep.png', glyph: 'D',
      onEnterTerrain: function (state, cell, actor, fx) {
        if (!hasPreserver(state)) {
          fx.push({ type: 'teleport', actor: actor.id,
            x: state.spawn.x, y: state.spawn.y });
          return null;
        }
        if (cell.meta && cell.meta.preserver_waded) {
          fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
            key: 'preserver_waded', value: 0 });
          return null;
        }
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'preserver_waded', value: 1 });
        return OPPOSITE[actor.dir] || null;
      } });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerLifePreserverPack;
  }
  root.GamePackLifePreserver = registerLifePreserverPack;
})(typeof window !== 'undefined' ? window : globalThis);
