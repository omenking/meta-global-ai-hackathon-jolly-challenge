// Pack: map tile (mech-55-map-tile sanity check).
// Stepping on the map tile consumes it (it becomes the spent tile)
// and shows the whole level as an overlay for three seconds while
// play continues, then the view fades back. The overlay window is
// derived only from the recorded step clock: onEnter stores
// map_overlay_until_ms = state.t_ms + 3000 in state.flags, and the
// tick hook clears map_overlay_active once state.t_ms reaches it.
// No rule reads wall-clock time, so a recorded session replays to
// the same overlay state. Restart restores the unconsumed tile
// because a fresh initialState rebuilds the room and its flags.
// UMD: browser global GamePackMapTile + Node export (register fn).
(function (root) {
  'use strict';
  var OVERLAY_MS = 3000;
  function registerMapTilePack(api) {
    for (const name of ['map.png', 'map-spent.png', 'map-overlay.png']) {
      api.defineAsset(name, { pack: 'maptile', bundled: true });
    }
    api.defineTile('map:map', { layer: 'object',
      sprite: 'map.png', glyph: 'M',
      onEnter: function (state, cell, actor, fx) {
        state.flags['map_overlay_until_ms'] = state.t_ms + OVERLAY_MS;
        state.flags['map_overlay_active'] = true;
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'map:spent' });
      } });
    api.defineTile('map:spent', { layer: 'object',
      sprite: 'map-spent.png', glyph: 'm' });
    api.onTick(function (state) {
      if (state.flags['map_overlay_active']
          && typeof state.flags['map_overlay_until_ms'] === 'number'
          && state.t_ms >= state.flags['map_overlay_until_ms']) {
        state.flags['map_overlay_active'] = false;
      }
    });
    api.onLevelLoad(function (state) {
      state.chars.object['map:map'] = 'M';
      state.chars.object['map:spent'] = 'm';
    });
  }
  registerMapTilePack.OVERLAY_MS = OVERLAY_MS;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMapTilePack;
  }
  root.GamePackMapTile = registerMapTilePack;
})(typeof window !== 'undefined' ? window : globalThis);
