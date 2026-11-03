// Pack: one-way door (mech-4-one-way-door sanity check).
// A one-way door is walkable only in its arrow direction and a
// wall from the other three sides, shown by chevrons. Passing
// through never consumes anything and it never resets: the tile
// has no inventory, counter or meta state at all. The kernel
// asks a tile's blocks(state, cell, actor) hook before a move;
// the attempted direction is the delta from the actor's current
// cell to the door cell, so the hook allows entry only when
// that delta equals the door's arrow. Leaving the door tile is
// unrestricted (the destination is floor, not the door), which
// is what makes the return attempt fail at the door itself:
// stepping back onto it from beyond moves against the arrow.
// All state advances through the pure step function and no rule
// reads wall-clock time.
// UMD: browser global GamePackOneWay + Node export (register fn).
(function (root) {
  'use strict';
  var DIRS = {
    north: { x: 0, y: -1, glyph: '^', file: 'one-way-door-north.png' },
    east: { x: 1, y: 0, glyph: '>', file: 'one-way-door-east.png' },
    south: { x: 0, y: 1, glyph: 'v', file: 'one-way-door-south.png' },
    west: { x: -1, y: 0, glyph: '<', file: 'one-way-door-west.png' },
  };
  function registerOneWayPack(api) {
    for (const name of Object.keys(DIRS)) {
      api.defineAsset(DIRS[name].file, { pack: 'oneway', bundled: true });
    }
    for (const name of Object.keys(DIRS)) {
      (function (dirName, dir) {
        api.defineTile('oneway:door-' + dirName, { layer: 'object',
          sprite: dir.file, glyph: dir.glyph,
          blocks: function (state, cell, actor) {
            if (!actor) return true;
            return !((cell.x - actor.x) === dir.x
              && (cell.y - actor.y) === dir.y);
          } });
      })(name, DIRS[name]);
    }
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerOneWayPack;
  }
  root.GamePackOneWay = registerOneWayPack;
})(typeof window !== 'undefined' ? window : globalThis);
