// Pack: heavy block (mech-87-heavy-block sanity check).
// A heavy block follows the push block (81) destination rules —
// only empty floor or a switch plate accepts it, via a fail-closed
// terrain allowlist, so water, deep water, void, fire and lava
// (and walls and every other terrain) block it, and any object or
// other actor on the destination blocks it too — but it costs two
// consecutive pushes per tile: the first push input sets a budge
// pending (the block budges but stays, Jolly strains) and only the
// immediately following push in the same direction moves it one
// tile. Any step in between clears the pending, so the two pushes
// must be consecutive. Wearing power gloves moves it in one push.
// Time and enemies keep running while you strain: a strain push is
// a blocked move inside the pure step function, so controllers and
// tick hooks still advance. The pack-local switch plate/gate,
// power gloves, patroller and hazard terrains are stand-ins for
// mechanics 29/89/31/41/43/44, which are not on main yet; the
// cross-mechanic YAML cases are skipped-with-reason in the test
// file. No rule reads wall-clock; restart restores the block with
// no budge pending because a fresh initialState rebuilds the room.
// UMD: browser global GamePackHeavyBlock + Node export (register fn).
(function (root) {
  'use strict';
  const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  const ACCEPTS = { 'core:floor': 1, 'core:spawn': 1,
    'heavy:switch-plate': 1 };

  function switchHeld(state) {
    for (let y = 0; y < state.height; y++) {
      for (let x = 0; x < state.width; x++) {
        if (state.objects[y][x] === 'heavy:heavy-block'
            && state.terrain[y][x] === 'heavy:switch-plate') return true;
      }
    }
    return false;
  }
  function clearBudge(state, x, y) {
    const k = x + ',' + y;
    if (state.meta[k]) delete state.meta[k].heavy_budge;
  }

  function registerHeavyBlockPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image (Muse Image), grounded on the floor sprite.
    for (const name of ['heavy-block.png', 'heavy-block-budging.png',
      'jolly-straining.png', 'jolly-pushing-heavy.png']) {
      api.defineAsset(name, { pack: 'heavy-block', bundled: true });
    }
    api.defineItem('heavy:power-gloves', { readout: 'power gloves' });
    // Hazard stand-ins (mechanics 41/43/44 + void): entering loses
    // for the player; the block never enters because its terrain
    // allowlist below is fail-closed.
    for (const [id, glyph] of [['heavy:deep', 'd'], ['heavy:fire', 'f'],
      ['heavy:lava', 'l'], ['heavy:void', 'v']]) {
      api.defineTile(id, { layer: 'terrain', glyph: glyph,
        onEnterTerrain: function (state, cell, actor, fx) {
          fx.push({ type: 'lose' });
          return null;
        } });
    }
    api.defineTile('heavy:switch-plate', { layer: 'terrain',
      glyph: 'S' });
    api.defineTile('heavy:switch-gate', { layer: 'object',
      sprite: 'gate.png', glyph: 'D',
      blocks: function (state) { return !switchHeld(state); } });
    api.defineTile('heavy:power-gloves', { layer: 'object', glyph: 'V',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: 'heavy:power-gloves' });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    api.defineTile('heavy:heavy-block', { layer: 'object',
      sprite: 'heavy-block.png', glyph: 'H',
      blocks: function (state, cell, actor) {
        // Only the player pushes; the block occupies its tile for
        // every other actor, so enemies cannot move through it.
        if (!actor || actor.id !== 'player') return true;
        const dx = cell.x - actor.x, dy = cell.y - actor.y;
        if (Math.abs(dx) + Math.abs(dy) !== 1) return true;
        const dirName = dx === 1 ? 'right' : dx === -1 ? 'left'
          : dy === 1 ? 'down' : 'up';
        const bx = cell.x + dx, by = cell.y + dy;
        if (bx < 0 || by < 0 || bx >= state.width || by >= state.height) {
          return true;
        }
        if (state.objects[by][bx]) return true;
        if (state.actors.some((a) => a.id !== actor.id
            && a.x === bx && a.y === by)) return true;
        // Fail-closed: only empty floor or a switch plate accepts
        // the block; water, deep water, void, fire, lava and walls
        // block every push, strain included (no pending is set).
        if (!ACCEPTS[state.terrain[by][bx]]) return true;
        const gloved = (state.inventory || []).some(
          (e) => e.item === 'heavy:power-gloves');
        const pending = state.flags.heavy_pending;
        if (gloved || (pending && pending.x === cell.x
            && pending.y === cell.y && pending.dir === dirName
            && pending.step === state.steps - 1)) {
          state.objects[cell.y][cell.x] = null;
          state.objects[by][bx] = 'heavy:heavy-block';
          clearBudge(state, cell.x, cell.y);
          delete state.flags.heavy_pending;
          state.flags.heavy_last_push_step = state.steps;
          return false;
        }
        // First push: budge in place and strain; the block and the
        // player both stay while the rest of the step still runs.
        state.flags.heavy_pending = { x: cell.x, y: cell.y,
          dir: dirName, step: state.steps };
        const k = cell.x + ',' + cell.y;
        state.meta[k] = Object.assign({}, state.meta[k],
          { heavy_budge: dirName });
        return true;
      } });
    // Patroller stand-in (mechanic 31): deterministic vertical
    // bounce between walls/objects; contact with the player loses.
    api.defineController('heavy:patroller', function (state, actor) {
      let dir = actor.flags.patrol_dir || 'up';
      for (let attempt = 0; attempt < 2; attempt++) {
        const d = DIRS[dir];
        const nx = actor.x + d.x, ny = actor.y + d.y;
        const blocked = nx < 0 || ny < 0 || nx >= state.width
          || ny >= state.height
          || state.terrain[ny][nx] === 'core:wall'
          || !!state.objects[ny][nx];
        if (!blocked) { actor.flags.patrol_dir = dir; return dir; }
        dir = dir === 'up' ? 'down' : 'up';
      }
      actor.flags.patrol_dir = dir;
      return null;
    });
    api.onTick(function (state, fx) {
      // A budge pending survives only into the immediately next
      // step: any other step in between clears it.
      const pending = state.flags.heavy_pending;
      if (pending && pending.step < state.steps) {
        clearBudge(state, pending.x, pending.y);
        delete state.flags.heavy_pending;
      }
      // Contact: a patroller reaching the player's tile catches
      // the player (this is what makes straining dangerous).
      const player = state.actors.find((a) => a.id === 'player');
      if (player && state.actors.some((a) => a.id !== 'player'
          && a.x === player.x && a.y === player.y)) {
        fx.push({ type: 'lose' });
      }
    });
    // Render/readout helper: true while a heavy block holds a
    // switch plate down. Pure read of state, never a driver of it.
    api.heavyBlockSwitchHeld = switchHeld;
  }
  registerHeavyBlockPack.switchHeld = switchHeld;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerHeavyBlockPack;
  }
  root.GamePackHeavyBlock = registerHeavyBlockPack;
})(typeof window !== 'undefined' ? window : globalThis);
