// Pack: move door (mech-79-move-door sanity check).
// The move door counts move inputs in the attempt and opens
// permanently on exactly the 50th move input, staying open after
// it, with no switch, key or timer involved. A move is one player
// input that attempts one step: the kernel increments state.steps
// for every step input (before movement resolves), so blocked
// attempts, pushes and detours all count, exactly as the mechanic
// definition requires. The closed door blocks while the count is
// under fifty; during the 50th input the kernel has already counted
// it, so that input opens the door and the player walks through.
// The pack tick hook mirrors the count into the movedoor:moves
// counter (the HUD move counter) and marks the door cell move_open
// once the count reaches fifty; the mark never clears, so the door
// stays open with no further counting needed. Every state advance
// goes through the pure step function and no rule reads wall-clock.
// Restart restores the closed door and a zero counter because a
// fresh initialState rebuilds the room. Per-cell meta (move_open)
// is a view of the count for rendering and tests, never a driver.
// UMD: browser global GamePackMoveDoor + Node export (register fn).
(function (root) {
  'use strict';
  const MOVES_TO_OPEN = 50;
  function registerMoveDoorPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image (Muse Image), one file per YAML asset entry.
    for (const name of ['move-door-closed.png', 'move-door-open.png',
      'move-counter.png']) {
      api.defineAsset(name, { pack: 'movedoor', bundled: true });
    }
    api.defineTile('movedoor:door', { layer: 'object',
      sprite: 'move-door-closed.png', glyph: 'D',
      // Closed it blocks like wall; the 50th move input is already
      // counted in state.steps when the kernel resolves movement,
      // so that input both opens the door and walks through it.
      blocks: function (state) {
        return (state.steps || 0) < MOVES_TO_OPEN;
      } });
    api.onLevelLoad(function (state) {
      let hasDoor = false;
      for (let y = 0; y < state.objects.length; y++) {
        for (let x = 0; x < state.objects[y].length; x++) {
          if (state.objects[y][x] !== 'movedoor:door') continue;
          hasDoor = true;
          state.meta[x + ',' + y] = Object.assign({},
            state.meta[x + ',' + y], { move_open: false });
        }
      }
      if (!hasDoor) return;
      state.chars.object['movedoor:door'] = 'D';
      state.counters['movedoor:moves'] = 0;
    });
    api.onTick(function (state, fx) {
      if (state.counters['movedoor:moves'] === undefined) return;
      state.counters['movedoor:moves'] = state.steps;
      if (state.steps < MOVES_TO_OPEN) return;
      for (let y = 0; y < state.objects.length; y++) {
        for (let x = 0; x < state.objects[y].length; x++) {
          if (state.objects[y][x] !== 'movedoor:door') continue;
          const m = state.meta[x + ',' + y] || {};
          if (m.move_open) continue;
          fx.push({ type: 'setMeta', x: x, y: y,
            key: 'move_open', value: true });
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMoveDoorPack;
  }
  root.GamePackMoveDoor = registerMoveDoorPack;
})(typeof window !== 'undefined' ? window : globalThis);
