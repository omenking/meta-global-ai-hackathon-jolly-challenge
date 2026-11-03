// Pack: ice tile (mech-1-ice-tile sanity check).
// Stepping onto ice in a direction slides the player that way
// within the same input until the next tile is a wall, lock or
// block: no steering and no stopping midway, and orbs on the line
// are collected. The slide is the kernel's bounded terrain chain:
// this pack's onEnterTerrain keeps returning the entry direction
// while the next tile can be entered, and returns null where the
// slide must stop (the braking wall/lock/block, or plain floor
// beyond the strip, which the slide carries onto and stops). An
// orb on an ice tile the slide passes over is collected here; an
// orb on the tile the slide stops on is collected by the kernel's
// normal object phase, so no orb is ever counted twice. All state
// advances through the pure step function; no rule reads
// wall-clock time. Restart restores the room because a fresh
// initialState rebuilds it. UMD: browser global GamePackIce +
// Node export (register fn).
(function (root) {
  'use strict';
  const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  function registerIcePack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image.
    api.defineAsset('ice.png', { pack: 'ice', bundled: true });
    api.defineAsset('jolly-sliding.png', { pack: 'ice', bundled: true });
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
    api.defineTile('ice:ice', { layer: 'terrain',
      sprite: 'ice.png', glyph: 'I',
      onEnterTerrain: function (state, cell, actor, fx) {
        const d = DIRS[actor.dir];
        if (!d) return null;
        const nx = cell.x + d.x, ny = cell.y + d.y;
        if (!canEnter(state, actor, nx, ny)) return null;
        // The slide passes over this tile: collect an orb on it
        // here (the stopping tile's orb is the kernel's phase 5).
        if (state.objects[cell.y][cell.x] === 'core:orb') {
          fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          fx.push({ type: 'incCounter', key: 'core:orbs_left', by: -1 });
        }
        return actor.dir;
      } });
    api.onLevelLoad(function (state) {
      if (!state.chars.terrain['ice:ice']) {
        state.chars.terrain['ice:ice'] = 'I';
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerIcePack;
  }
  root.GamePackIce = registerIcePack;
})(typeof window !== 'undefined' ? window : globalThis);
