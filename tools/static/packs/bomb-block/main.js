// Pack: bomb block (mech-83-bomb-block sanity check).
// The bomb block is a pushable block with one exception: it slides
// exactly like a push block (one tile onto empty floor or a switch
// plate, never pulled, never into water, deep water, void, fire,
// lava, a lock, a closed gate or another block), but a push that
// would drive it into a wall explodes it instead: that wall tile
// becomes floor and the bomb block is consumed. It is the only
// block that destroys a wall. Pushing is resolved in the bomb
// tile's onEnter hook (the player steps toward the bomb; the hook
// slides the bomb, explodes it, or leaves both in place by
// returning the player), so all state advances through the pure
// step function with recorded t_ms and no wall-clock reads.
// Restart restores the bomb and every wall because a fresh
// initialState rebuilds the room.
// UMD: browser global GamePackBombBlock + Node export (register fn).
(function (root) {
  'use strict';
  var DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  // Terrain the bomb may slide onto: empty floor or a switch plate.
  var SLIDE_TERRAIN = { 'core:floor': true, 'core:spawn': true,
    'bomb:switch-plate': true };
  // Terrain a bomb push cracks to floor. Any other destination
  // (hazards included) blocks the push outright.
  var WALL_TERRAIN = { 'core:wall': true, 'bomb:cracked-wall': true };
  function hazardTile(glyph) {
    return { layer: 'terrain', glyph: glyph,
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
        return null;
      } };
  }
  function registerBombPack(api) {
    // Bundled assets (see manifest.json): Muse-generated art from
    // scripts/gen-image, one file per blocks.yml #83 assets entry.
    for (const name of ['cracked-wall.png', 'floor-after-blast.png',
      'bomb-block.png', 'bomb-block-exploding.png']) {
      api.defineAsset(name, { pack: 'bomb-block', bundled: true });
    }
    api.defineTile('bomb:cracked-wall', { layer: 'terrain',
      sprite: 'cracked-wall.png', glyph: 'W',
      blocks: function () { return true; } });
    api.defineTile('bomb:switch-plate', { layer: 'terrain',
      glyph: 'S' });
    // Hazard terrain for test rooms: deadly for the player to
    // enter (as water is), and never a bomb destination because
    // the slide allowlist above excludes it.
    api.defineTile('bomb:deep-water', hazardTile('D'));
    api.defineTile('bomb:fire', hazardTile('F'));
    api.defineTile('bomb:lava', hazardTile('A'));
    // A plain inert block: another block a bomb can be pushed
    // against; it never cracks and never moves.
    api.defineTile('bomb:crate', { layer: 'object', glyph: 'K',
      blocks: function () { return true; } });
    api.defineTile('bomb:bomb-block', { layer: 'object',
      sprite: 'bomb-block.png', glyph: 'B',
      onEnter: function (state, cell, actor, fx) {
        if (!actor || actor.id !== 'player') return;
        const d = DIRS[actor.dir];
        if (!d) return;
        const stay = { type: 'teleport', actor: actor.id,
          x: cell.x - d.x, y: cell.y - d.y };
        const dx = cell.x + d.x, dy = cell.y + d.y;
        if (dx < 0 || dy < 0 || dx >= state.width
            || dy >= state.height) { fx.push(stay); return; }
        // Any occupying object (lock, closed gate, orb, warp,
        // void, another block) blocks the push; nothing explodes.
        if (state.objects[dy][dx]) { fx.push(stay); return; }
        const destTerr = state.terrain[dy][dx];
        if (WALL_TERRAIN[destTerr]) {
          fx.push({ type: 'setTerrain', x: dx, y: dy,
            def: 'core:floor' });
          fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        } else if (SLIDE_TERRAIN[destTerr]) {
          fx.push({ type: 'setObject', x: dx, y: dy,
            def: 'bomb:bomb-block' });
          fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        } else { fx.push(stay); }
      } });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerBombPack;
  }
  root.GamePackBombBlock = registerBombPack;
})(typeof window !== 'undefined' ? window : globalThis);
