// Pack: peep hole (mech-60-peep-hole sanity check).
// Stepping on the peep hole locks the controls and pans the camera
// up for two seconds into the next room, which is otherwise drawn
// black until entered in person; then the camera returns and the
// player chooses whether to go in. The preview is partial: it
// covers a 5-wide strip above the door (the lock in the teaching
// room) and never the far side of the next room (its orb), and
// looking alone opens no way through, collects nothing and reveals
// nothing permanently. All timing comes from the recorded input
// t_ms: the lock expires at peep_start + 2000ms, the level timer
// keeps running through it (the kernel clock is t_ms), and restart
// (a fresh initialState) restores the unused hole and black room.
// The lock is enforced in the pure step: while peeping, a tick
// hook teleports the player back onto the hole, so the end-of-step
// position never leaves it. No rule reads wall-clock time.
// UMD: browser global GamePackPeepHole + Node export (register fn).
(function (root) {
  'use strict';
  var PEEP_MS = 2000;
  function previewCells(state) {
    var hx = state.flags['peep:hole_x'], hy = state.flags['peep:hole_y'];
    var div = state.flags['peep:divider_y'];
    if (typeof hx !== 'number' || typeof div !== 'number') return [];
    var cells = [];
    for (var y = Math.max(0, div - 2); y < div; y++) {
      for (var x = hx - 2; x <= hx + 2; x++) {
        if (x >= 0 && x < state.width) cells.push(x + ',' + y);
      }
    }
    return cells;
  }
  function registerPeepHolePack(api) {
    for (const name of ['peep-hole.png', 'peep-hole-active.png',
      'unrevealed-room.png', 'jolly-peeping.png']) {
      api.defineAsset(name, { pack: 'peephole', bundled: true });
    }
    api.defineTile('peep:hole', { layer: 'object',
      sprite: 'peep-hole.png', glyph: 'H',
      onEnter: function (state, cell, actor, fx) {
        state.flags['peep:active'] = true;
        state.flags['peep:until_ms'] = state.t_ms + PEEP_MS;
        state.flags['peep:x'] = cell.x;
        state.flags['peep:y'] = cell.y;
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'peep_triggered', value: true });
      } });
    // Door into the next room: passable floor in this sanity check.
    // The one-way rule itself is mechanic 4 (blocked-by); peeping
    // never changes this tile, so looking opens no way through.
    api.defineTile('peep:door', { layer: 'object', glyph: 'D' });
    api.onLevelLoad(function (state) {
      state.flags['peep:active'] = false;
      state.flags['peep:until_ms'] = 0;
      state.flags['peep:x'] = -1;
      state.flags['peep:y'] = -1;
      state.flags['peep:entered_next'] = false;
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] === 'peep:hole') {
            state.flags['peep:hole_x'] = x;
            state.flags['peep:hole_y'] = y;
          }
          if (state.objects[y][x] === 'peep:door') {
            state.flags['peep:divider_y'] = y;
          }
        }
      }
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (!player) return;
      const div = state.flags['peep:divider_y'];
      if (typeof div === 'number' && player.y < div) {
        state.flags['peep:entered_next'] = true;
      }
      if (!state.flags['peep:active']) return;
      if (state.t_ms >= (state.flags['peep:until_ms'] || 0)) {
        state.flags['peep:active'] = false;
        return;
      }
      if (player.x !== state.flags['peep:x']
          || player.y !== state.flags['peep:y']) {
        fx.push({ type: 'teleport', actor: player.id,
          x: state.flags['peep:x'], y: state.flags['peep:y'] });
      }
    });
  }
  registerPeepHolePack.previewCells = previewCells;
  registerPeepHolePack.PEEP_MS = PEEP_MS;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerPeepHolePack;
  }
  root.GamePackPeepHole = registerPeepHolePack;
})(typeof window !== 'undefined' ? window : globalThis);
