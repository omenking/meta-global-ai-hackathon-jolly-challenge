// Pack: toggle switch (mech-22-toggle-switch sanity check).
// Stepping onto the toggle swaps its two linked doors at once:
// open becomes closed and closed becomes open, and the swapped
// state persists after the player leaves. Each entry onto the
// switch is one press and one swap; standing on it does not
// repeat the swap (the kernel fires onEnter only on entry, and
// a blocked push while standing on it enters no new cell).
// Pressing again swaps them back. Restart restores the placed
// states because a fresh initialState rebuilds the room. All
// state advances through the pure step function; no rule reads
// wall-clock time.
// UMD: browser global GamePackToggleSwitch + Node export.
(function (root) {
  'use strict';
  function swapDoors(state, cell, fx) {
    // Swap the toggle's own face and every linked door in the room.
    // Doors are found by scanning the object layer for the two
    // door defs, so a level links doors simply by placing them.
    fx.push({ type: 'setObject', x: cell.x, y: cell.y,
      def: cell.def.id === 'toggle:switch-a'
        ? 'toggle:switch-b' : 'toggle:switch-a' });
    for (let y = 0; y < state.objects.length; y++) {
      for (let x = 0; x < state.objects[y].length; x++) {
        const id = state.objects[y][x];
        if (id === 'toggle:door-open') {
          fx.push({ type: 'setObject', x: x, y: y,
            def: 'toggle:door-closed' });
        } else if (id === 'toggle:door-closed') {
          fx.push({ type: 'setObject', x: x, y: y,
            def: 'toggle:door-open' });
        }
      }
    }
  }
  function registerTogglePack(api) {
    for (const name of ['toggle-switch-a.png', 'toggle-switch-b.png',
      'door-closed.png', 'door-open.png']) {
      api.defineAsset(name, { pack: 'toggle-switch', bundled: true });
    }
    api.defineTile('toggle:switch-a', { layer: 'object',
      sprite: 'toggle-switch-a.png', glyph: 'T',
      onEnter: function (state, cell, actor, fx) {
        swapDoors(state, cell, fx);
      } });
    api.defineTile('toggle:switch-b', { layer: 'object',
      sprite: 'toggle-switch-b.png', glyph: 'T',
      onEnter: function (state, cell, actor, fx) {
        swapDoors(state, cell, fx);
      } });
    api.defineTile('toggle:door-open', { layer: 'object',
      sprite: 'door-open.png', glyph: 'a' });
    api.defineTile('toggle:door-closed', { layer: 'object',
      sprite: 'door-closed.png', glyph: 'b',
      blocks: function () { return true; } });
    // Both switch faces project to 'T' and each door def keeps the
    // char of the tile where it was first placed, so the projected
    // grid swaps door letters exactly as the doors swap state.
    api.onLevelLoad(function (state) {
      state.chars.object['toggle:switch-a'] = 'T';
      state.chars.object['toggle:switch-b'] = 'T';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerTogglePack;
  }
  root.GamePackToggleSwitch = registerTogglePack;
})(typeof window !== 'undefined' ? window : globalThis);
