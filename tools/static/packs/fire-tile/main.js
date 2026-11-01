// Pack: fire tile (mech-43-fire-tile sanity check).
// Fire sits on flammable floor (grass or wood) and is lethal while
// burning. Every 10 moves each burning fire spreads to one adjacent
// flammable tile (first free cell in N/E/S/W order, snapshot of the
// fires burning at the start of that tick, so a fire lit this tick
// does not spread again in the same tick). Each fire burns out
// after 30 moves (steps - fire_born >= 30) leaving safe scorched
// floor, so it never burns forever. Fire never spreads onto stone
// (core:floor). The clock is the move count (state.steps), never
// wall-clock, and all state advances through the pure step
// function via tick effects. Restart restores placed fires because
// a fresh initialState re-runs onLevelLoad (fire_born = 0).
// Ice-block cancellation is blocked-by mechanic 82 (no ice block
// pack exists yet); it is an explicit skipped test, not faked here.
// UMD: browser global GamePackFireTile + Node export (register fn).
(function (root) {
  'use strict';
  var SPREAD_EVERY = 10;
  var BURN_OUT_AFTER = 30;
  var FLAMMABLE = { 'fire:grass': true, 'fire:wood': true };
  var DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]]; // N, E, S, W

  function registerFirePack(api) {
    for (const name of ['fire.png', 'scorched.png']) {
      api.defineAsset(name, { pack: 'fire-tile', bundled: true });
    }
    api.defineTile('fire:grass', { layer: 'terrain',
      sprite: 'floor_default.png', glyph: 'g' });
    api.defineTile('fire:wood', { layer: 'terrain',
      sprite: 'floor_default.png', glyph: 'w' });
    api.defineTile('fire:fire', { layer: 'object',
      sprite: 'fire.png', glyph: 'F',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
      } });
    api.defineTile('fire:scorched', { layer: 'object',
      sprite: 'scorched.png', glyph: 'H' });

    api.onLevelLoad(function (state) {
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] === 'fire:fire') {
            const k = x + ',' + y;
            state.meta[k] = Object.assign({}, state.meta[k],
              { fire_born: 0 });
          }
        }
      }
      state.chars.object['fire:fire'] = 'F';
      state.chars.object['fire:scorched'] = 'H';
      if (!state.chars.object['fire:grass']) {
        // Terrain chars are keyed by terrain id in chars.terrain;
        // nothing to add here.
      }
    });

    api.onTick(function (state, fx) {
      const steps = state.steps;
      // Snapshot of fires burning at the start of this tick.
      const fires = [];
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] === 'fire:fire') {
            const meta = state.meta[x + ',' + y] || {};
            const born = typeof meta.fire_born === 'number'
              ? meta.fire_born : 0;
            fires.push({ x: x, y: y, born: born });
          }
        }
      }
      const burning = {};
      for (const f of fires) burning[f.x + ',' + f.y] = true;
      // Burn-out first: a fire that dies this tick does not spread.
      const alive = [];
      for (const f of fires) {
        if (steps - f.born >= BURN_OUT_AFTER) {
          fx.push({ type: 'setObject', x: f.x, y: f.y,
            def: 'fire:scorched' });
          delete burning[f.x + ',' + f.y];
        } else {
          alive.push(f);
        }
      }
      // Spread on the move clock: one adjacent flammable tile each.
      if (steps > 0 && steps % SPREAD_EVERY === 0) {
        const claimed = {};
        for (const f of alive) {
          for (const d of DIRS) {
            const nx = f.x + d[0], ny = f.y + d[1];
            if (nx < 0 || ny < 0 || nx >= state.width
                || ny >= state.height) continue;
            if (!FLAMMABLE[state.terrain[ny][nx]]) continue;
            if (state.objects[ny][nx]) continue;
            const k = nx + ',' + ny;
            if (claimed[k]) continue;
            claimed[k] = true;
            fx.push({ type: 'setObject', x: nx, y: ny,
              def: 'fire:fire' });
            fx.push({ type: 'setMeta', x: nx, y: ny,
              key: 'fire_born', value: steps });
            break; // one new tile per fire per spread tick
          }
        }
      }
      // Fire spreading under the player is still lethal.
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (player && state.objects[player.y]
          && state.objects[player.y][player.x] === 'fire:fire') {
        fx.push({ type: 'lose' });
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerFirePack;
  }
  root.GamePackFireTile = registerFirePack;
})(typeof window !== 'undefined' ? window : globalThis);
