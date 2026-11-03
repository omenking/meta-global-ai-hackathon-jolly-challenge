// Pack: dirt block (mech-90-dirt-block sanity check).
// On land the block moves only onto empty floor or a switch plate,
// exactly as a push block (81). Pushed into void, shallow water,
// deep water or lava it is consumed and that one tile becomes
// permanent floor. Fire blocks it like a wall, because the ice
// block (82) is the fire canceller. The hazard terrains here
// (dirt:shallow / dirt:deep / dirt:lava / dirt:void / dirt:fire)
// are local stand-ins for mechanics 50/41/44, crumbling's void and
// the fire tile, which are not on main yet; the cross-mechanic
// cases in the YAML are skipped-with-reason in the test file. The
// push is decided inside the tile's blocks predicate, which runs
// on the kernel's already-cloned next state during the pure step
// function: a legal land push moves the block object in that clone
// and lets the player follow, a fill consumes the block and
// rewrites the destination terrain to dirt:filled-floor, and a
// blocked push changes nothing so the block and the player both
// stay put. No rule reads wall-clock; restart restores every block
// and filled tile because a fresh initialState rebuilds the room.
// UMD: browser global GamePackDirtBlock + Node export (register fn).
(function (root) {
  'use strict';
  // Fail-closed destination allowlists: on land only empty floor
  // or a switch plate accepts the block; the fill terrains consume
  // it into permanent floor; every other terrain (wall, fire and
  // anything unlisted) blocks the push outright.
  const LAND = { 'core:floor': 1, 'core:spawn': 1,
    'dirt:filled-floor': 1, 'dirt:switch-plate': 1,
    'blocks:switch-plate': 1 };
  const FILL = { 'dirt:shallow': 1, 'dirt:deep': 1, 'dirt:lava': 1,
    'dirt:void': 1, 'water:water': 1 };
  function registerDirtBlockPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // the Muse image tool, cropped and resized to 512x512.
    for (const name of ['dirt-block.png', 'dirt-filled-floor.png']) {
      api.defineAsset(name, { pack: 'dirt-block', bundled: true });
    }
    api.defineTile('dirt:filled-floor', { layer: 'terrain',
      sprite: 'dirt-filled-floor.png' });
    api.defineTile('dirt:switch-plate', { layer: 'terrain',
      glyph: 'S' });
    function hazard(id, glyph) {
      api.defineTile(id, { layer: 'terrain', glyph: glyph,
        // Stepping into the hazard on foot loses the attempt; a
        // filled tile is dirt:filled-floor terrain instead, so the
        // crossing the block builds is safe to walk on.
        onEnterTerrain: function (state, cell, actor, fx) {
          fx.push({ type: 'lose' });
          return null;
        } });
    }
    hazard('dirt:shallow', '~');
    hazard('dirt:deep', 'W');
    hazard('dirt:lava', 'L');
    hazard('dirt:void', 'V');
    hazard('dirt:fire', 'F');
    api.defineTile('dirt:dirt-block', { layer: 'object',
      sprite: 'dirt-block.png', glyph: 'D',
      blocks: function (state, cell, actor) {
        // Only the player pushes; the block occupies its tile for
        // every other actor, so enemies cannot move through it.
        if (!actor || actor.id !== 'player') return true;
        const dx = cell.x - actor.x, dy = cell.y - actor.y;
        if (Math.abs(dx) + Math.abs(dy) !== 1) return true;
        const bx = cell.x + dx, by = cell.y + dy;
        if (bx < 0 || by < 0 || bx >= state.width
            || by >= state.height) return true;
        const destObj = state.objects[by][bx];
        // A void hole (crumbling's object tile) is fillable: the
        // block is consumed and the hole becomes permanent floor.
        if (destObj === 'crumble:void') {
          state.objects[by][bx] = null;
          state.terrain[by][bx] = 'dirt:filled-floor';
          state.objects[cell.y][cell.x] = null;
          return false;
        }
        // Another block, a lock, a closed gate or any other object
        // on the destination blocks the push.
        if (destObj) return true;
        // An enemy standing on the destination blocks the push.
        if (state.actors.some((a) => a.id !== actor.id
            && a.x === bx && a.y === by)) return true;
        const terr = state.terrain[by][bx];
        if (FILL[terr]) {
          // Consumed: exactly that one tile becomes permanent
          // floor and the player follows into the block's tile.
          state.objects[cell.y][cell.x] = null;
          state.terrain[by][bx] = 'dirt:filled-floor';
          return false;
        }
        if (LAND[terr]) {
          state.objects[cell.y][cell.x] = null;
          state.objects[by][bx] = 'dirt:dirt-block';
          return false;
        }
        // Wall, fire and every unlisted terrain block the push:
        // the block is never consumed and both stay put.
        return true;
      } });
    // The filled floor never appears in level rows, so give its
    // projected grid char a name here (the kernel projection falls
    // back to it).
    api.onLevelLoad(function (state) {
      state.chars.terrain['dirt:filled-floor'] = '.';
      if (!state.chars.object['dirt:dirt-block']) {
        state.chars.object['dirt:dirt-block'] = 'D';
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerDirtBlockPack;
  }
  root.GamePackDirtBlock = registerDirtBlockPack;
})(typeof window !== 'undefined' ? window : globalThis);
