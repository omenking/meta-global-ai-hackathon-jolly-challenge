// Pack: still tile (mech-71-still-tile sanity check).
// While the player stands on a still tile the level timer is held:
// the display pauses and shows the held icon, and stepping off
// resumes the clock from the held value. Enemies already advance
// only on player inputs in the kernel, so standing still advances
// nothing else either. The hold is accumulated purely from the
// recorded t_ms of each step: the interval since the previous step
// counts as held when the player spent it standing on the tile.
// No rule reads wall-clock time; replaying the same timestamped
// log reproduces the same held totals. Restart restores the
// running clock because a fresh initialState re-runs onLevelLoad.
// This pack registers first so its tick adjusts elapsed_s before
// the core pack's expiry check reads it.
// UMD: browser global GamePackStill + Node export (register fn).
(function (root) {
  'use strict';
  function registerStillPack(api) {
    // Bundled assets (see manifest.json): real generated art.
    for (const name of ['still.png', 'still-held.png',
      'jolly-still.png', 'timer-held.png']) {
      api.defineAsset(name, { pack: 'still', bundled: true });
    }
    api.defineTile('still:still', { layer: 'terrain',
      sprite: 'still.png', glyph: 'S' });
    function hasStillTile(state) {
      for (const row of state.terrain) {
        for (const id of row) if (id === 'still:still') return true;
      }
      return false;
    }
    api.onLevelLoad(function (state) {
      if (!hasStillTile(state)) return;
      state.counters['still:held_ms'] = 0;
      state.counters['still:last_t_ms'] = 0;
      state.flags['still:present'] = true;
      state.flags['still:held'] = false;
    });
    api.onTick(function (state) {
      if (!state.flags['still:present']) return;
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (!player) return;
      const lastT = state.counters['still:last_t_ms'] || 0;
      const wasHeld = !!state.flags['still:held'];
      if (wasHeld && state.t_ms > lastT) {
        state.counters['still:held_ms'] =
          (state.counters['still:held_ms'] || 0) + (state.t_ms - lastT);
      }
      state.counters['still:last_t_ms'] = state.t_ms;
      const onTile = state.terrain[player.y]
        && state.terrain[player.y][player.x] === 'still:still';
      state.flags['still:held'] = !!onTile;
      const heldS = (state.counters['still:held_ms'] || 0) / 1000;
      state.elapsed_s = Math.max(0, state.t_ms / 1000 - heldS);
      state.time_left_s = state.time_limit_s === null
        || state.time_limit_s === undefined ? state.time_left_s
        : Math.max(0, state.time_limit_s - state.elapsed_s);
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerStillPack;
  }
  root.GamePackStill = registerStillPack;
})(typeof window !== 'undefined' ? window : globalThis);
