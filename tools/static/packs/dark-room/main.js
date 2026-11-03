// Pack: dark room (mech-51-dark-room sanity check).
// A dark room draws only the tiles within two tiles of Jolly;
// tiles beyond that radius are not drawn at all, though they
// still exist to be walked into (floor stays walkable, walls
// still block). The HUD lives outside the board and still
// shows. Distance is Chebyshev: max(|dx|, |dy|) <= 2, a 5x5
// lit square centred on Jolly that moves with Jolly. The rule
// is view-only: it never blocks, collects or harms, so state
// advances only through the pure kernel step and no rule reads
// wall-clock. A level opts in with "dark_room": true; the pack
// hook stamps state.flags['dark:room'] so renderers and tests
// ask the state, not the level file. Restart restores the room
// because a fresh initialState re-stamps the flag and orbs.
// UMD: browser global GamePackDarkRoom + Node export (register fn).
(function (root) {
  'use strict';
  var LIGHT_RADIUS = 2;
  function isVisible(px, py, x, y, radius) {
    var r = radius === undefined ? LIGHT_RADIUS : radius;
    return Math.max(Math.abs(x - px), Math.abs(y - py)) <= r;
  }
  function isStateVisible(state, x, y) {
    if (!state || !state.flags || !state.flags['dark:room']) return true;
    var p = state.player || (state.actors && state.actors[0]) || { x: 0, y: 0 };
    return isVisible(p.x, p.y, x, y);
  }
  function registerDarkRoomPack(api) {
    for (var i = 0; i < 3; i++) {
      api.defineAsset(['dark-room-floor.png', 'darkness.png',
        'jolly-in-dark.png'][i], { pack: 'dark-room', bundled: true });
    }
    api.onLevelLoad(function (state, level) {
      if (level && level.dark_room) state.flags['dark:room'] = true;
    });
  }
  registerDarkRoomPack.LIGHT_RADIUS = LIGHT_RADIUS;
  registerDarkRoomPack.isVisible = isVisible;
  registerDarkRoomPack.isStateVisible = isStateVisible;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerDarkRoomPack;
  }
  root.GamePackDarkRoom = registerDarkRoomPack;
})(typeof window !== 'undefined' ? window : globalThis);
