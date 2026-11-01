// Pack: ice block (mech-82-ice-block sanity check).
// One push slides the block in the push direction over floor and
// ice until a wall, lock, gate or other block stops it. Sliding
// into fire melts and consumes it and that one fire tile becomes
// scorched floor; into lava or deep water it melts/sinks and is
// destroyed with the hazard unchanged; into shallow water it
// stops there and becomes an ice bridge; into void it falls and
// is destroyed with the void unchanged. The fire/shallow tiles
// here are local stand-ins (ice:fire / ice:shallow) for mechanics
// 43/50, which are not on main yet; the cross-mechanic cases in
// the YAML are skipped-with-reason in the test file. The push is
// resolved in the block's onEnter hook: the kernel lets the
// player step onto the block tile, the hook emits the whole
// slide as effects and teleports the player back to the tile
// they pushed from, so the player never moves on a push and no
// rule reads wall-clock time. Restart restores every tile
// because a fresh initialState rebuilds the room.
// UMD: browser global GamePackIceBlock + Node export.
(function (root) {
  'use strict';
  const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  const SPECIALS = { 'ice:fire': 'fire', 'ice:lava': 'lava',
    'ice:shallow': 'shallow', 'ice:deep': 'deep', 'ice:void': 'void' };
  const WALLS = { 'core:wall': 1, 'core:info': 1, 'core:unknown': 1 };

  function slide(state, cell, actor, fx) {
    const d = DIRS[state.last_input];
    // The player always stays on the tile they pushed from.
    fx.push({ type: 'teleport', actor: actor.id,
      x: cell.x - (d ? d.x : 0), y: cell.y - (d ? d.y : 0) });
    if (!d) return;
    let cx = cell.x, cy = cell.y, outcome = 'rest', ox = cx, oy = cy;
    for (;;) {
      const nx = cx + d.x, ny = cy + d.y;
      if (nx < 0 || ny < 0 || nx >= state.width || ny >= state.height) break;
      const terr = state.terrain[ny][nx];
      if (SPECIALS[terr]) { outcome = SPECIALS[terr]; ox = nx; oy = ny; break; }
      if (WALLS[terr]) break;
      const obj = state.objects[ny][nx];
      // Scorched floor is a passable overlay; every other object
      // (gate, lock, orb, key, another block, a bridge) stops it.
      if (obj && obj !== 'ice:scorched') break;
      cx = nx; cy = ny;
    }
    if (outcome === 'rest') {
      if (cx !== cell.x || cy !== cell.y) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'setObject', x: cx, y: cy, def: 'ice:ice-block' });
      }
      return;
    }
    fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
    if (outcome === 'fire') {
      fx.push({ type: 'setObject', x: ox, y: oy, def: 'ice:scorched' });
    } else if (outcome === 'shallow') {
      fx.push({ type: 'setObject', x: ox, y: oy, def: 'ice:ice-bridge' });
    }
    // lava / deep / void: the block is destroyed, tile unchanged.
  }

  function registerIceBlockPack(api) {
    for (const name of ['ice-block.png', 'ice-block-sliding.png',
      'ice-block-melting.png', 'ice-bridge.png', 'scorched.png']) {
      api.defineAsset(name, { pack: 'ice-block', bundled: true });
    }
    api.defineTile('ice:ice', { layer: 'terrain',
      sprite: 'floor_default.png', glyph: 'i' });
    api.defineTile('ice:fire', { layer: 'terrain', glyph: 'F',
      onEnterTerrain: function (state, cell, actor, fx) {
        if (state.objects[cell.y][cell.x] !== 'ice:scorched') {
          fx.push({ type: 'lose' });
        }
        return null;
      } });
    api.defineTile('ice:lava', { layer: 'terrain', glyph: 'A',
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
        return null;
      } });
    api.defineTile('ice:shallow', { layer: 'terrain', glyph: '~',
      onEnterTerrain: function (state, cell, actor, fx) {
        if (state.objects[cell.y][cell.x] !== 'ice:ice-bridge') {
          fx.push({ type: 'lose' });
        }
        return null;
      } });
    api.defineTile('ice:deep', { layer: 'terrain', glyph: 'D',
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
        return null;
      } });
    api.defineTile('ice:void', { layer: 'terrain', glyph: 'V',
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
        return null;
      } });
    api.defineTile('ice:ice-block', { layer: 'object',
      sprite: 'ice-block.png', glyph: 'I',
      onEnter: function (state, cell, actor, fx) {
        if (actor.id !== 'player') return;
        slide(state, cell, actor, fx);
      } });
    api.defineTile('ice:scorched', { layer: 'object',
      sprite: 'scorched.png', glyph: 'S' });
    api.defineTile('ice:ice-bridge', { layer: 'object',
      sprite: 'ice-bridge.png', glyph: 'B' });
    // Moved/transformed tiles never appear in level rows at their
    // destination, so give their projected grid chars names here.
    api.onLevelLoad(function (state) {
      state.chars.object['ice:ice-block'] = 'I';
      state.chars.object['ice:scorched'] = 'S';
      state.chars.object['ice:ice-bridge'] = 'B';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerIceBlockPack;
  }
  root.GamePackIceBlock = registerIceBlockPack;
})(typeof window !== 'undefined' ? window : globalThis);
