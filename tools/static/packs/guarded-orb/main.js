// Pack: guarded orb (mech-19-guarded-orb sanity check).
// The guarded orb is an orb that flees: when the player ends a move
// within two tiles (Chebyshev), it steps exactly one tile away to a
// free floor tile, once per player move. It can never enter walls or
// water (only bare core:floor with no object and no actor counts as
// free), and it only steps when a neighbour is strictly farther from
// the player than its current tile, so driving it against a wall,
// water or a parked object corners it; stepping onto a cornered orb
// collects it. All state advances through the pure step function via
// the tick hook; no rule reads wall-clock time. Restart restores the
// orb because a fresh initialState rebuilds the room.
// UMD: browser global GamePackGuardedOrb + Node export (register fn).
(function (root) {
  'use strict';
  function registerGuardedOrbPack(api) {
    api.defineAsset('guarded-orb.png', { pack: 'guarded-orb', bundled: true });
    api.defineTile('guarded:guarded-orb', { layer: 'object',
      sprite: 'guarded-orb.png', glyph: 'Q' });
    api.onLevelLoad(function (state) {
      state.chars.object['guarded:guarded-orb'] = 'Q';
      let n = 0;
      for (const row of state.objects) {
        for (const id of row) if (id === 'guarded:guarded-orb') n++;
      }
      if (n) {
        state.counters['core:orbs_left'] =
          (state.counters['core:orbs_left'] || 0) + n;
      }
    });
    api.onTick(function (state, fx) {
      // A finished run is frozen; the kernel still runs tick hooks on
      // the expiry path, so never move or collect after the end.
      if (state.status !== 'playing') return;
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (!player) return;
      const orbs = [];
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] === 'guarded:guarded-orb') {
            orbs.push({ x: x, y: y });
          }
        }
      }
      const cheb = (x, y) => Math.max(Math.abs(x - player.x),
        Math.abs(y - player.y));
      const free = (x, y) => {
        if (x < 0 || y < 0 || x >= state.width || y >= state.height) {
          return false;
        }
        if (state.terrain[y][x] !== 'core:floor') return false;
        if (state.objects[y][x]) return false;
        return !state.actors.some((a) => a.x === x && a.y === y);
      };
      // Fixed order keeps the flee choice deterministic for replays.
      const dirs = [{ x: 0, y: -1 }, { x: 1, y: 0 },
        { x: 0, y: 1 }, { x: -1, y: 0 }];
      for (const orb of orbs) {
        const dist = cheb(orb.x, orb.y);
        const onPlayer = orb.x === player.x && orb.y === player.y;
        // Landing on the orb collects it: the player could only
        // start that move adjacent if the orb already failed to
        // flee on the previous move, i.e. it was cornered.
        if (onPlayer) {
          fx.push({ type: 'removeObject', x: orb.x, y: orb.y });
          fx.push({ type: 'incCounter', key: 'core:orbs_left', by: -1 });
          continue;
        }
        if (dist > 2) continue;
        let best = null, bestCheb = dist, bestMan = -1;
        for (const d of dirs) {
          const nx = orb.x + d.x, ny = orb.y + d.y;
          if (!free(nx, ny)) continue;
          const c = cheb(nx, ny);
          const m = Math.abs(nx - player.x) + Math.abs(ny - player.y);
          if (c > bestCheb || (c === bestCheb && c > dist && m > bestMan)) {
            best = { x: nx, y: ny }; bestCheb = c; bestMan = m;
          }
        }
        if (best) {
          fx.push({ type: 'removeObject', x: orb.x, y: orb.y });
          fx.push({ type: 'setObject', x: best.x, y: best.y,
            def: 'guarded:guarded-orb' });
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerGuardedOrbPack;
  }
  root.GamePackGuardedOrb = registerGuardedOrbPack;
})(typeof window !== 'undefined' ? window : globalThis);
