// Pack: power gloves (mech-89-power-gloves sanity check).
// Held in a slot, the gloves change pushing itself: a heavy block
// moves in one push instead of two (the strain graphic is skipped,
// no budge pending is ever set), and pushing a normal block into a
// line of blocks shifts the whole line one tile (the domino
// behaviour). Without the gloves a single block still pushes as a
// plain push block, a heavy block costs two consecutive pushes
// (first sets a budge pending in meta, second moves it), and a
// line does not shift at all. A line shifts only when the tile
// beyond the far block is empty floor or a switch plate, decided
// fail-closed: any object, any other actor, or any terrain off the
// floor/switch allowlist (wall, lock by occupancy, water, deep
// water, void, fire, lava) stops the whole line with nothing
// moving. The push is decided inside the tile blocks predicate,
// which runs on the kernel's already-cloned next state during the
// pure step function: a legal push moves the block object(s) in
// that clone and lets the player follow, a blocked push changes
// nothing. No rule reads wall-clock; restart restores the gloves
// and every block because a fresh initialState rebuilds the room.
// UMD: browser global GamePackPowerGloves + Node export.
(function (root) {
  'use strict';
  const ACCEPTS = { 'core:floor': 1, 'core:spawn': 1,
    'gloves:switch-plate': 1 };
  const PUSHABLE = { 'gloves:push-block': 1, 'gloves:heavy-block': 1 };

  function hasGloves(state) {
    return (state.inventory || []).some(
      (e) => e.item === 'gloves:gloves');
  }
  function switchHeld(state) {
    for (let y = 0; y < state.height; y++) {
      for (let x = 0; x < state.width; x++) {
        if (PUSHABLE[state.objects[y][x]]
            && state.terrain[y][x] === 'gloves:switch-plate') return true;
      }
    }
    return false;
  }
  function clearBudge(state, x, y) {
    const k = x + ',' + y;
    if (state.meta[k]) delete state.meta[k].heavy_budge;
  }

  // Shared push decision. Returns true when the push is blocked
  // (player and blocks stay), false after moving the block(s) in
  // the cloned state so the kernel lets the player follow.
  function attemptPush(state, cell, actor) {
    if (!actor || actor.id !== 'player') return true;
    const dx = cell.x - actor.x, dy = cell.y - actor.y;
    if (Math.abs(dx) + Math.abs(dy) !== 1) return true;
    const dirName = dx === 1 ? 'right' : dx === -1 ? 'left'
      : dy === 1 ? 'down' : 'up';
    // Collect the straight line of pushable blocks from the head.
    const chain = [];
    let cx = cell.x, cy = cell.y;
    while (cx >= 0 && cy >= 0 && cx < state.width && cy < state.height
        && PUSHABLE[state.objects[cy][cx]]) {
      chain.push({ x: cx, y: cy, id: state.objects[cy][cx] });
      cx += dx; cy += dy;
    }
    if (!chain.length) return true;
    const bx = cx, by = cy; // tile beyond the far block
    if (bx < 0 || by < 0 || bx >= state.width || by >= state.height) {
      return true;
    }
    if (state.objects[by][bx]) return true;
    if (state.actors.some((a) => a.id !== actor.id
        && a.x === bx && a.y === by)) return true;
    if (!ACCEPTS[state.terrain[by][bx]]) return true;
    const gloved = hasGloves(state);
    if (chain.length > 1) {
      // Domino line shift: only the gloves move a whole line.
      if (!gloved) return true;
      for (let i = chain.length - 1; i >= 0; i--) {
        state.objects[chain[i].y + dy][chain[i].x + dx] = chain[i].id;
      }
      state.objects[cell.y][cell.x] = null;
      state.flags.gloves_last_line_push_step = state.steps;
      delete state.flags.gloves_heavy_pending;
      return false;
    }
    const head = chain[0];
    if (head.id === 'gloves:heavy-block' && !gloved) {
      const pending = state.flags.gloves_heavy_pending;
      if (pending && pending.x === cell.x && pending.y === cell.y
          && pending.dir === dirName
          && pending.step === state.steps - 1) {
        state.objects[cell.y][cell.x] = null;
        state.objects[by][bx] = head.id;
        clearBudge(state, cell.x, cell.y);
        delete state.flags.gloves_heavy_pending;
        state.flags.gloves_heavy_moved_step = state.steps;
        return false;
      }
      // First push: budge in place and strain; nobody moves.
      state.flags.gloves_heavy_pending = { x: cell.x, y: cell.y,
        dir: dirName, step: state.steps };
      const k = cell.x + ',' + cell.y;
      state.meta[k] = Object.assign({}, state.meta[k],
        { heavy_budge: dirName });
      return true;
    }
    state.objects[cell.y][cell.x] = null;
    state.objects[by][bx] = head.id;
    if (head.id === 'gloves:heavy-block') {
      // Gloved heavy push: one push, strain graphic skipped.
      clearBudge(state, cell.x, cell.y);
      delete state.flags.gloves_heavy_pending;
      state.flags.gloves_heavy_moved_step = state.steps;
      state.flags.gloves_heavy_one_push = true;
    }
    return false;
  }

  function registerPowerGlovesPack(api) {
    for (const name of ['power-gloves.png', 'power-gloves-collected.png',
      'jolly-power-gloves.png', 'jolly-power-gloves-pushing.png',
      'jolly-line-push.png', 'power-gloves-slot.png']) {
      api.defineAsset(name, { pack: 'power-gloves', bundled: true });
    }
    api.defineItem('gloves:gloves', { icon: 'power-gloves-slot.png',
      readout: 'power-gloves' });
    api.defineTile('gloves:gloves', { layer: 'object',
      sprite: 'power-gloves.png', glyph: 'g',
      blocks: function (state) { return state.inventory.length >= 8; },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'giveItem', item: 'gloves:gloves' });
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
      } });
    api.defineTile('gloves:push-block', { layer: 'object', glyph: 'B',
      blocks: function (state, cell, actor) {
        return attemptPush(state, cell, actor);
      } });
    api.defineTile('gloves:heavy-block', { layer: 'object', glyph: 'H',
      blocks: function (state, cell, actor) {
        return attemptPush(state, cell, actor);
      } });
    api.defineTile('gloves:switch-plate', { layer: 'terrain',
      glyph: 'S' });
    // Hazard stand-ins (mechanics 41/43/44 + void): entering loses
    // for the player; a block never enters because the destination
    // allowlist above is fail-closed.
    for (const [id, glyph] of [['gloves:deep-water', 'd'],
      ['gloves:fire', 'f'], ['gloves:lava', 'l'],
      ['gloves:void', 'v']]) {
      api.defineTile(id, { layer: 'terrain', glyph: glyph,
        onEnterTerrain: function (state, cell, actor, fx) {
          fx.push({ type: 'lose' });
          return null;
        } });
    }
    api.onTick(function (state) {
      // A budge pending survives only into the next step.
      const pending = state.flags.gloves_heavy_pending;
      if (pending && pending.step < state.steps) {
        clearBudge(state, pending.x, pending.y);
        delete state.flags.gloves_heavy_pending;
      }
    });
    api.powerGlovesSwitchHeld = switchHeld;
    api.powerGlovesHasGloves = hasGloves;
  }
  registerPowerGlovesPack.switchHeld = switchHeld;
  registerPowerGlovesPack.hasGloves = hasGloves;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerPowerGlovesPack;
  }
  root.GamePackPowerGloves = registerPowerGlovesPack;
})(typeof window !== 'undefined' ? window : globalThis);
