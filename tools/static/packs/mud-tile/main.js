// Pack: mud tile (mech-47-mud-tile sanity check).
// Mud is floor that stores the walked path as scent prints in
// walk order: entering a mud cell stamps it with the next print
// order (cell meta mud_order, counted by mud:print_count), so the
// ordered trail is readable start to finish from state alone.
// Enemies reading the trail (chaser, mech 32) are not built yet;
// their YAML test cases are skipped-with-reason in the test file.
// Restart restores plain mud because a fresh initialState rebuilds
// the room with no meta. All state advances through the pure step
// function and no rule reads wall-clock time.
// UMD: browser global GamePackMudTile + Node export (register fn).
(function (root) {
  'use strict';
  function registerMudTilePack(api) {
    for (const name of ['mud.png', 'mud-prints.png']) {
      api.defineAsset(name, { pack: 'mud-tile', bundled: true });
    }
    api.defineTile('mud:mud', { layer: 'terrain',
      sprite: 'mud.png', glyph: 'M',
      onEnterTerrain: function (state, cell, actor, fx) {
        const order = ((state.counters || {})['mud:print_count'] || 0) + 1;
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'mud_print', value: true });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'mud_order', value: order });
        fx.push({ type: 'incCounter', key: 'mud:print_count', by: 1 });
        return null;
      } });
    api.onLevelLoad(function (state) {
      if (typeof state.counters['mud:print_count'] !== 'number') {
        state.counters['mud:print_count'] = 0;
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMudTilePack;
  }
  root.GamePackMudTile = registerMudTilePack;
})(typeof window !== 'undefined' ? window : globalThis);
