// Pack: ice cleats (mech-62-ice-cleats sanity check).
// Gear held in one inventory slot for the rest of the level. While
// held, ice tiles behave as normal floor: no slide, the player can
// stop and turn on them, and every ice tile costs the normal one
// move. All other movement is unchanged. Without the cleats the
// pack-local ice terrain slides the player in the entry direction
// until a wall, lock or block brakes the slide (or plain floor
// beyond the strip carries and stops it); that baseline slide is
// the teaching room's naive action and stands in for the ice tile
// (mechanic 1, movement-tiles.yml), which is not built on main yet
// — when that pack lands it owns the slide and this terrain def is
// retired in its favour. An orb is collected only on the tile the
// player stops on (the kernel's object phase), never mid-slide.
// Every stage advances through the pure step function; no rule
// reads wall-clock time. Restart restores the pickup because a
// fresh initialState rebuilds the room. UMD: browser global
// GamePackIceCleats + Node export (register fn).
(function (root) {
  'use strict';
  const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  function registerIceCleatsPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image.
    for (const name of ['ice-cleats.png', 'ice-cleats-collected.png',
      'jolly-ice-cleats-on-ice.png', 'jolly-ice-cleats.png',
      'ice-cleats-slot.png']) {
      api.defineAsset(name, { pack: 'ice-cleats', bundled: true });
    }
    api.defineItem('cleats:cleats',
      { icon: 'ice-cleats-slot.png', readout: 'cleats' });
    api.defineTile('cleats:cleats', { layer: 'object',
      sprite: 'ice-cleats.png', glyph: 'K',
      // Full 8-slot inventory: the cleats stay and block, as keys do.
      blocks: function (state) { return state.inventory.length >= 8; },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: 'cleats:cleats' });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    function hasCleats(state) {
      return (state.inventory || []).some((e) => e.item === 'cleats:cleats');
    }
    function canEnter(state, actor, x, y) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) return false;
      const meta = state.meta[x + ',' + y] || {};
      const terrId = state.terrain[y][x];
      const terr = terrId ? api.getTile(terrId) : null;
      if (terr && terr.blocks &&
        terr.blocks(state, { x: x, y: y, def: terr, meta: meta }, actor)) return false;
      const objId = state.objects[y][x];
      const obj = objId ? api.getTile(objId) : null;
      if (obj && obj.blocks &&
        obj.blocks(state, { x: x, y: y, def: obj, meta: meta }, actor)) return false;
      return true;
    }
    api.defineTile('cleats:ice', { layer: 'terrain', glyph: 'I',
      onEnterTerrain: function (state, cell, actor, fx) {
        // Wearing the cleats, ice is normal floor: never slide.
        if (hasCleats(state)) return null;
        const d = DIRS[actor.dir];
        if (!d) return null;
        const nx = cell.x + d.x, ny = cell.y + d.y;
        if (!canEnter(state, actor, nx, ny)) return null;
        return actor.dir;
      } });
    api.onLevelLoad(function (state) {
      if (!state.chars.terrain['cleats:ice']) {
        state.chars.terrain['cleats:ice'] = 'I';
      }
      if (!state.chars.object['cleats:cleats']) {
        state.chars.object['cleats:cleats'] = 'K';
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerIceCleatsPack;
  }
  root.GamePackIceCleats = registerIceCleatsPack;
})(typeof window !== 'undefined' ? window : globalThis);
