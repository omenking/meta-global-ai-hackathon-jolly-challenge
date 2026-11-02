// Pack: magnet glove (mech-63-magnet-glove sanity check).
// The glove is held in an inventory slot. While held, pressing
// toward a metal block in a clear line within 3 tiles slides the
// block one tile toward the player and the player stays; otherwise
// the player moves normally. A wall (or any other object) in the
// line means no pull happens, and a block already next to the
// player cannot be pulled onto the player's tile. The pull is
// decided in a before-move hook: it vetoes the player's move and
// slides the block inside the same pure step, so no state ever
// advances outside step() and no rule reads wall-clock time.
// Restart restores the glove and block because a fresh
// initialState rebuilds the room. Pushing the metal block is
// mechanic 81 (push block), not built here: the block simply
// blocks movement, as any unbuilt pushable would.
// UMD: browser global GamePackMagnetGlove + Node export.
(function (root) {
  'use strict';
  var DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  var BLOCK = 'magnet:metal-block';
  var GLOVE = 'magnet:glove';
  function registerMagnetGlovePack(api) {
    // Bundled assets (see manifest.json): generated art for every
    // asset in the candidate mechanic's YAML assets list.
    for (const name of ['magnet-glove.png', 'magnet-glove-collected.png',
      'jolly-magnet-glove.png', 'jolly-magnet-pulling.png',
      'magnet-glove-slot.png', 'metal-block.png']) {
      api.defineAsset(name, { pack: 'magnet-glove', bundled: true });
    }
    api.defineItem(GLOVE, { icon: 'magnet-glove-slot.png',
      readout: 'magnet-glove' });
    api.defineTile(GLOVE, { layer: 'object', sprite: 'magnet-glove.png',
      glyph: 'g',
      // Full 8-slot inventory: the glove stays and blocks, as keys do.
      blocks: function (state) { return state.inventory.length >= 8; },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: GLOVE });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    api.defineTile(BLOCK, { layer: 'object', sprite: 'metal-block.png',
      glyph: 'M',
      blocks: function () { return true; } });
    // Pull rule: runs before the player's move inside step(). Returns
    // false to veto the move (the pull replaces it); true lets the
    // normal move attempt proceed.
    api.onBeforeMove(function (state, actor, dirName) {
      const d = DIRS[dirName];
      if (!d) return true;
      const held = (state.inventory || []).some((e) => e.item === GLOVE);
      if (!held) return true;
      for (let i = 1; i <= 3; i++) {
        const x = actor.x + d.x * i, y = actor.y + d.y * i;
        if (x < 0 || y < 0 || x >= state.width || y >= state.height) return true;
        const terr = api.getTile(state.terrain[y][x]);
        if (terr && terr.blocks && terr.blocks(state,
          { x: x, y: y, def: terr, meta: (state.meta[x + ',' + y] || {}) },
          actor)) return true; // wall in the line: no pull
        const obj = state.objects[y][x];
        if (!obj) continue;
        if (obj !== BLOCK) return true; // other object in the line
        if (i < 2) return true; // too close: would land on the player
        state.objects[y][x] = null;
        state.objects[y - d.y][x - d.x] = BLOCK;
        state.last_effects.push('magnet:pull');
        return false;
      }
      return true;
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMagnetGlovePack;
  }
  root.GamePackMagnetGlove = registerMagnetGlovePack;
})(typeof window !== 'undefined' ? window : globalThis);
