// Pack: ghost (mech-78-ghost sanity check).
// Ghosts of your failed attempts replay one step behind, and there
// can be several. An attempt ends by stepping into the ghost pit
// (ghost:pit) or by touching a ghost; ending an attempt records its
// whole route (the player position after every step, spawn first)
// as a new trail and restarts the player at the spawn with orbs
// restored, all inside the same pure step, so the run never freezes
// and repeated failures lay down a trailing line of ghosts. On the
// next attempt each ghost shows the position its trail had one step
// earlier (attempt step k shows trail[k-1]); ghosts pass through
// each other (positions are independent, several may share a tile),
// a ghost shows its fading pose on the first step past its trail
// and is gone after that, and meeting a ghost on a tile — or
// crossing it head-on while backtracking — ends the attempt. A
// fresh initialState (R / restart) rebuilds the room with no
// trails, so restart clears every ghost. All state lives in
// state.flags/counters and advances only through the pure step
// function; no rule reads wall-clock time.
// UMD: browser global GamePackGhost + Node export (register fn).
(function (root) {
  'use strict';
  function registerGhostPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image.
    for (const name of ['ghost-start.png', 'ghost-jolly.png',
      'ghost-jolly-fading.png']) {
      api.defineAsset(name, { pack: 'ghost', bundled: true });
    }
    // The pit is terrain that ends the attempt: the tick hook below
    // turns standing on it into a recorded failure + respawn, so it
    // never pushes a kernel lose itself.
    api.defineTile('ghost:pit', { layer: 'terrain', glyph: 'H' });
    api.onLevelLoad(function (state) {
      const pits = [];
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.terrain[y][x] === 'ghost:pit') pits.push({ x: x, y: y });
        }
      }
      if (!pits.length) return;
      let orbs = 0;
      for (const row of state.objects) {
        for (const id of row) if (id === 'core:orb') orbs++;
      }
      state.flags.ghost_pits = pits;
      state.flags.ghost_trails = [];
      state.flags.ghost_current = [{ x: state.spawn.x, y: state.spawn.y }];
      state.flags.ghost_positions = [];
      state.flags.ghost_deaths = 0;
      state.flags.ghost_just_failed = false;
      state.flags.ghost_snapshot = {
        objects: state.objects.map((r) => r.slice()), orbs: orbs };
      state.counters['ghost:deaths'] = 0;
    });
    api.onTick(function (state, fx) {
      const flags = state.flags || {};
      if (!flags.ghost_current || !flags.ghost_pits) return;
      // flags is shallow-cloned by the kernel; detach nested data
      // before mutating so stepping never mutates the input state.
      state.flags = JSON.parse(JSON.stringify(flags));
      const f = state.flags;
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (!player) return;
      const prev = f.ghost_current[f.ghost_current.length - 1];
      f.ghost_current.push({ x: player.x, y: player.y });
      const stepInAttempt = f.ghost_current.length - 1;
      const onWarp = state.objects[player.y]
        && state.objects[player.y][player.x] === 'core:warp';
      let failed = f.ghost_pits.some(
        (p) => p.x === player.x && p.y === player.y);
      const positions = [];
      for (const trail of f.ghost_trails) {
        const idx = stepInAttempt - 1; // one step behind
        if (idx < 0) continue;
        if (idx < trail.length) {
          const pos = trail[idx];
          positions.push({ x: pos.x, y: pos.y,
            kind: idx === 0 ? 'start' : 'ghost', fading: false });
          if (!onWarp && pos.x === player.x && pos.y === player.y) {
            failed = true; // meeting a ghost on a tile
          }
          // Head-on crossing while backtracking: player and ghost
          // swap tiles this step.
          const prevIdx = stepInAttempt - 2;
          if (!onWarp && prev && prevIdx >= 0 && prevIdx < trail.length) {
            const gPrev = trail[prevIdx];
            if (gPrev.x === player.x && gPrev.y === player.y
              && pos.x === prev.x && pos.y === prev.y
              && (pos.x !== player.x || pos.y !== player.y)) {
              failed = true;
            }
          }
        } else if (idx === trail.length) {
          const last = trail[trail.length - 1];
          positions.push({ x: last.x, y: last.y,
            kind: 'fading', fading: true });
        }
      }
      f.ghost_positions = positions;
      f.ghost_just_failed = false;
      if (!failed) return;
      // End the attempt: record its route as a new ghost trail,
      // restore orbs, and restart the player at the spawn.
      f.ghost_trails.push(f.ghost_current);
      f.ghost_deaths = (f.ghost_deaths || 0) + 1;
      state.counters['ghost:deaths'] = f.ghost_deaths;
      const snap = f.ghost_snapshot;
      if (snap) {
        for (let y = 0; y < state.height; y++) {
          for (let x = 0; x < state.width; x++) {
            const want = snap.objects[y][x];
            if (want === state.objects[y][x]) continue;
            if (want) fx.push({ type: 'setObject', x: x, y: y, def: want });
            else fx.push({ type: 'removeObject', x: x, y: y });
          }
        }
        const delta = snap.orbs - (state.counters['core:orbs_left'] || 0);
        if (delta) {
          fx.push({ type: 'incCounter', key: 'core:orbs_left', by: delta });
        }
      }
      fx.push({ type: 'teleport', actor: 'player',
        x: state.spawn.x, y: state.spawn.y });
      f.ghost_current = [{ x: state.spawn.x, y: state.spawn.y }];
      f.ghost_positions = [];
      f.ghost_just_failed = true;
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerGhostPack;
  }
  root.GamePackGhost = registerGhostPack;
})(typeof window !== 'undefined' ? window : globalThis);
