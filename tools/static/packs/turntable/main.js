// Pack: turntable tile (mech-7-turntable-tile sanity check).
// A framed tile that turns on-foot movement 90 degrees, never a
// slide. Stepping onto it on foot turns its arrow 90 degrees
// clockwise and nudges the player one tile in the new arrow
// direction, automatically on entry with nothing to press. The
// arrow is cell meta (turntable_dir: north/east/south/west, seeded
// from the level legend at load); the nudge is the kernel's pure
// forced-move phase (onEnterTerrain), so it respects walls like
// any step and no rule reads wall-clock. Sliding on ice or riding
// a conveyor would pass straight over without turning, but those
// movers are not built yet (blocked-by mechanic 1, ice tile).
// Restart restores the placed arrow because a fresh initialState
// re-seeds the meta. UMD: browser global GamePackTurntable + Node.
(function (root) {
  'use strict';
  var ORDER = ['north', 'east', 'south', 'west'];
  var TO_KERNEL = { north: 'up', east: 'right', south: 'down', west: 'left' };
  function registerTurntablePack(api) {
    for (const name of ['turntable-north.png', 'turntable-east.png',
      'turntable-south.png', 'turntable-west.png']) {
      api.defineAsset(name, { pack: 'turntable', bundled: true });
    }
    api.defineTile('turntable:turntable', { layer: 'terrain',
      sprite: 'turntable-north.png', glyph: 'T',
      onEnterTerrain: function (state, cell, actor, fx) {
        const cur = (cell.meta && cell.meta.turntable_dir) || 'north';
        const nextDir = ORDER[(ORDER.indexOf(cur) + 1) % ORDER.length];
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'turntable_dir', value: nextDir });
        return TO_KERNEL[nextDir];
      } });
    api.onLevelLoad(function (state, level) {
      state.chars.terrain['turntable:turntable'] = 'T';
      const rows = (level && level.rows) || [];
      const legend = (level && level.legend) || {};
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.terrain[y][x] !== 'turntable:turntable') continue;
          const ch = rows[y] && rows[y][x];
          const dir = (ch && legend[ch] && legend[ch].turntable_dir) || 'north';
          state.meta[x + ',' + y] = { turntable_dir: dir };
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerTurntablePack;
  }
  root.GamePackTurntable = registerTurntablePack;
})(typeof window !== 'undefined' ? window : globalThis);
