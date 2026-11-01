// Pack: deep water (mech-41-deep-water sanity check).
// Dark deep water. Without the life preserver, entering it sends
// the player back to the active checkpoint (the last checkpoint
// tile touched, else the level spawn) with the timer still
// running and the run still playing. With the preserver held,
// each deep tile costs two moves: the first input wades in
// place (the player stays on the origin tile while the target
// tile records the wade), and only the second input crosses.
// The wade is a count in the target cell's meta, so hesitation
// never strands the player: every deep tile can still be exited
// in at most two inputs, or resolves to the checkpoint. The
// preserver pickup and checkpoint tiles live in this pack so the
// teaching room is playable standalone; their full mechanics
// (61, 48) refine them later. All state advances through the
// pure step function; no rule reads wall-clock time. Restart
// restores the room because a fresh initialState rebuilds it.
// UMD: browser global GamePackDeepWater + Node export.
(function (root) {
  'use strict';
  const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  function registerDeepWaterPack(api) {
    api.defineAsset('deep-water.png', { pack: 'deep-water', bundled: true });
    api.defineAsset('jolly-wading.png', { pack: 'deep-water', bundled: true });
    api.defineItem('deep:life-preserver',
      { icon: 'jolly-wading.png', readout: 'life-preserver' });
    api.defineTile('deep:water', { layer: 'terrain',
      sprite: 'deep-water.png', glyph: 'W',
      onEnterTerrain: function (state, cell, actor, fx) {
        const has = (state.inventory || [])
          .some((e) => e.item === 'deep:life-preserver');
        if (!has) {
          const cx = typeof state.flags.deep_cx === 'number'
            ? state.flags.deep_cx : state.spawn.x;
          const cy = typeof state.flags.deep_cy === 'number'
            ? state.flags.deep_cy : state.spawn.y;
          fx.push({ type: 'teleport', actor: actor.id, x: cx, y: cy });
          return null;
        }
        const waded = (cell.meta && cell.meta.deep_wade) || 0;
        if (!waded) {
          const d = DIRS[actor.dir] || { x: 0, y: 0 };
          fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
            key: 'deep_wade', value: 1 });
          fx.push({ type: 'teleport', actor: actor.id,
            x: cell.x - d.x, y: cell.y - d.y });
        } else {
          fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
            key: 'deep_wade', value: 0 });
        }
        return null;
      } });
    api.defineTile('deep:preserver', { layer: 'object', glyph: 'L',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: 'deep:life-preserver' });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    api.defineTile('deep:checkpoint', { layer: 'object', glyph: 'K',
      onEnter: function (state, cell, actor, fx) {
        state.flags.deep_cx = cell.x;
        state.flags.deep_cy = cell.y;
      } });
    api.onLevelLoad(function (state) {
      if (!state.chars.terrain['deep:water']) {
        state.chars.terrain['deep:water'] = 'W';
      }
      state.chars.object['deep:preserver'] = 'L';
      state.chars.object['deep:checkpoint'] = 'K';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerDeepWaterPack;
  }
  root.GamePackDeepWater = registerDeepWaterPack;
})(typeof window !== 'undefined' ? window : globalThis);
