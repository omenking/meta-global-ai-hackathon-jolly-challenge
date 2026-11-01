// Pack: timed orb (mech-15-timed-orb sanity check).
// The countdown starts the first time the orb enters the camera
// view, with a ring showing the seconds left; collected in time it
// counts as a normal orb; if it expires it dissolves and reforms
// at its start tile after 5 seconds, so the level is never
// unwinnable. Restart restores it unseen because a fresh
// initialState rebuilds the room. All timing derives from the
// recorded input t_ms via the pure step function: the tick hook
// reads state.t_ms / state.elapsed_s only, never wall-clock.
// Camera view mirrors engine/camera.js (at most 17x16 tiles,
// centred on the player and clamped to the level), so "on sight"
// means inside that same viewport. UMD like the crumbling pack.
(function (root) {
  'use strict';
  var COLLECT_WINDOW_MS = 10000;
  var REFORM_MS = 5000;
  var VIEW_W = 17, VIEW_H = 16;

  function inView(state, x, y) {
    var player = null;
    for (var i = 0; i < state.actors.length; i++) {
      if (state.actors[i].id === 'player') player = state.actors[i];
    }
    if (!player) player = state.actors[0];
    if (!player) return false;
    var vw = Math.min(state.width, VIEW_W), vh = Math.min(state.height, VIEW_H);
    var cx = Math.max(0, Math.min(Math.max(0, state.width - vw),
      player.x - Math.floor(vw / 2)));
    var cy = Math.max(0, Math.min(Math.max(0, state.height - vh),
      player.y - Math.floor(vh / 2)));
    return x >= cx && x < cx + vw && y >= cy && y < cy + vh;
  }

  function registerTimedOrbPack(api) {
    for (const name of ['timed-orb.png', 'timed-orb-ringing.png',
      'timed-orb-reforming.png']) {
      api.defineAsset(name, { pack: 'timed-orb', bundled: true });
    }
    api.defineTile('timed:timed-orb', { layer: 'object',
      sprite: 'timed-orb.png', glyph: 'T',
      onEnter: function (state, cell, actor, fx) {
        const meta = cell.meta || {};
        if (meta.timed_phase === 'collected'
            || meta.timed_phase === 'dissolved') return;
        if (meta.timed_phase === 'ringing'
            && typeof meta.timed_seen_ms === 'number'
            && state.t_ms - meta.timed_seen_ms >= COLLECT_WINDOW_MS) {
          // Entering at/after the deadline is too late: it
          // dissolves under the player instead of collecting.
          fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
            key: 'timed_phase', value: 'dissolved' });
          fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
            key: 'timed_gone_ms', value: state.t_ms });
          return;
        }
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'incCounter', key: 'core:orbs_left', by: -1 });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'timed_phase', value: 'collected' });
      } });
    api.onLevelLoad(function (state) {
      let n = 0;
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] === 'timed:timed-orb') {
            n++;
            state.meta[x + ',' + y] = { timed_phase: 'unseen',
              timed_seen_ms: null, timed_gone_ms: null };
          }
        }
      }
      if (n) {
        state.counters['core:orbs_left'] =
          (state.counters['core:orbs_left'] || 0) + n;
      }
      if (!state.chars.object['timed:timed-orb']) {
        state.chars.object['timed:timed-orb'] = 'T';
      }
    });
    api.onTick(function (state, fx) {
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          const meta = state.meta[x + ',' + y];
          if (!meta || !meta.timed_phase) continue;
          if (meta.timed_phase === 'unseen') {
            if (state.objects[y][x] === 'timed:timed-orb'
                && inView(state, x, y)) {
              fx.push({ type: 'setMeta', x: x, y: y,
                key: 'timed_phase', value: 'ringing' });
              fx.push({ type: 'setMeta', x: x, y: y,
                key: 'timed_seen_ms', value: state.t_ms });
            }
          } else if (meta.timed_phase === 'ringing') {
            if (typeof meta.timed_seen_ms === 'number'
                && state.t_ms - meta.timed_seen_ms >= COLLECT_WINDOW_MS) {
              fx.push({ type: 'removeObject', x: x, y: y });
              fx.push({ type: 'setMeta', x: x, y: y,
                key: 'timed_phase', value: 'dissolved' });
              fx.push({ type: 'setMeta', x: x, y: y,
                key: 'timed_gone_ms', value: state.t_ms });
            }
          } else if (meta.timed_phase === 'dissolved') {
            if (typeof meta.timed_gone_ms === 'number'
                && state.t_ms - meta.timed_gone_ms >= REFORM_MS) {
              fx.push({ type: 'setObject', x: x, y: y,
                def: 'timed:timed-orb' });
              fx.push({ type: 'setMeta', x: x, y: y,
                key: 'timed_phase', value: 'unseen' });
              fx.push({ type: 'setMeta', x: x, y: y,
                key: 'timed_seen_ms', value: null });
              fx.push({ type: 'setMeta', x: x, y: y,
                key: 'timed_gone_ms', value: null });
            }
          }
        }
      }
    });
  }
  registerTimedOrbPack.COLLECT_WINDOW_MS = COLLECT_WINDOW_MS;
  registerTimedOrbPack.REFORM_MS = REFORM_MS;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerTimedOrbPack;
  }
  root.GamePackTimedOrb = registerTimedOrbPack;
})(typeof window !== 'undefined' ? window : globalThis);
