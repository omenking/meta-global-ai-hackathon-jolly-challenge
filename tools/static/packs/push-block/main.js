// Pack: push block (mech-81-push-block sanity check).
// Pressing toward the block moves it exactly one tile, and only
// onto empty floor or a switch plate. It can never be pulled:
// moving away simply leaves it. Walls, locks, closed gates, other
// blocks and enemies block the push, and water, deep water, void,
// fire and lava destinations block it too (a fail-closed allowlist:
// only core:floor / core:spawn / blocks:switch-plate terrain with
// no object and no other actor on it accepts the block). While the
// block sits on a switch plate it holds that switch down, which
// holds the switch gate open; the block occupies its tile, so
// non-player actors can never move through it. The push is decided
// inside the tile's blocks predicate, which runs on the kernel's
// already-cloned next state during the pure step function: a legal
// push moves the block object in that clone and lets the player
// follow, a blocked push changes nothing and both stay put. No
// rule reads wall-clock; restart restores the block because a
// fresh initialState rebuilds the room.
// UMD: browser global GamePackPushBlock + Node export (register fn).
(function (root) {
  'use strict';
  function switchHeld(state) {
    for (let y = 0; y < state.height; y++) {
      for (let x = 0; x < state.width; x++) {
        if (state.objects[y][x] === 'blocks:push-block'
            && state.terrain[y][x] === 'blocks:switch-plate') return true;
      }
    }
    return false;
  }
  function registerPushBlockPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image (Muse Image), grounded on the floor sprite.
    for (const name of ['push-block.png', 'push-block-on-switch.png']) {
      api.defineAsset(name, { pack: 'push-block', bundled: true });
    }
    api.defineTile('blocks:push-block', { layer: 'object',
      sprite: 'push-block.png', glyph: 'B',
      blocks: function (state, cell, actor) {
        // Only the player pushes; the block occupies its tile for
        // every other actor, so enemies cannot move through it.
        if (!actor || actor.id !== 'player') return true;
        const dx = cell.x - actor.x, dy = cell.y - actor.y;
        if (Math.abs(dx) + Math.abs(dy) !== 1) return true;
        const bx = cell.x + dx, by = cell.y + dy;
        if (bx < 0 || by < 0 || bx >= state.width || by >= state.height) {
          return true;
        }
        // Another block, a lock, a closed gate, a void or any other
        // object on the destination blocks the push.
        if (state.objects[by][bx]) return true;
        // An enemy standing on the destination blocks the push.
        if (state.actors.some((a) => a.id !== actor.id
            && a.x === bx && a.y === by)) return true;
        // Fail-closed destination allowlist: empty floor or a
        // switch plate only. Wall, water, deep water, fire, lava
        // and every other terrain block the push, so the block
        // never enters or covers a hazard.
        const terr = state.terrain[by][bx];
        if (terr !== 'core:floor' && terr !== 'core:spawn'
            && terr !== 'blocks:switch-plate') return true;
        state.objects[cell.y][cell.x] = null;
        state.objects[by][bx] = 'blocks:push-block';
        return false;
      } });
    api.defineTile('blocks:switch-plate', { layer: 'terrain',
      glyph: 'S' });
    api.defineTile('blocks:switch-gate', { layer: 'object',
      sprite: 'gate.png', glyph: 'D',
      blocks: function (state) { return !switchHeld(state); } });
    // Render/readout helper: true while any push block holds a
    // switch plate down. Pure read of state, never a driver of it.
    api.pushBlockSwitchHeld = switchHeld;
  }
  registerPushBlockPack.switchHeld = switchHeld;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerPushBlockPack;
  }
  root.GamePackPushBlock = registerPushBlockPack;
})(typeof window !== 'undefined' ? window : globalThis);
