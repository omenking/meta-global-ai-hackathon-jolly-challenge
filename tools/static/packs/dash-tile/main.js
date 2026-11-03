// Pack: dash tile (mech-9-dash-tile sanity check).
// Stepping on the tile stores one dash (the dash:charge inventory
// item, shown in the HUD). Moving in the same direction twice in a
// row spends it: the second step travels two tiles and clears the
// tile in between. Changing direction keeps the charge. The dash
// itself is the kernel's terrain chain: the floor hook below returns
// the repeated direction once per step, so the kernel moves the
// player one extra tile and only the landing cell's object fires —
// a gap object on the cleared tile never triggers. Dashing toward a
// wall still spends the charge (the chain move is blocked, the
// consume effect still applies). The previous direction lives in
// the player actor's flags, refreshed every step by the tick hook;
// restart clears it because a fresh initialState rebuilds the room.
// All state advances through the pure step function; no rule reads
// wall-clock time. UMD: browser global GamePackDashTile + Node export.
(function (root) {
  'use strict';
  var DIRS = { up: 1, down: 1, left: 1, right: 1 };
  function hasCharge(state) {
    return (state.inventory || []).some(function (e) {
      return e.item === 'dash:charge';
    });
  }
  function registerDashPack(api) {
    for (const name of ['dash-tile.png', 'dash-tile-spent.png',
      'jolly-dashing.png', 'dash-charge.png']) {
      api.defineAsset(name, { pack: 'dash-tile', bundled: true });
    }
    api.defineItem('dash:charge', { icon: 'dash-charge.png', readout: 'dash' });
    api.defineTile('dash:dash-tile', { layer: 'object',
      sprite: 'dash-tile.png', glyph: 'D',
      onEnter: function (state, cell, actor, fx) {
        // One stored dash at most; landing here on a dash step whose
        // consume is still queued re-arms the tile for the player.
        const justDashed = actor && actor.flags
          && actor.flags.dash_step === state.steps;
        if (!hasCharge(state) || justDashed) {
          fx.push({ type: 'giveItem', item: 'dash:charge' });
        }
      } });
    api.defineTile('dash:gap', { layer: 'object',
      sprite: 'void.png', glyph: 'V',
      // Enterable, and entering on foot is falling. A dash clears
      // this tile without entering it (see the floor hook below).
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
      } });
    // The dash chain rides the floor's terrain hook: when the step's
    // direction repeats the previous step's and a charge is held,
    // return that direction once so this step travels two tiles.
    // Registered last, this redefines core:floor with the same
    // layer/sprite plus the hook; levels without a dash tile never
    // hold a charge, so their floors behave exactly as before.
    api.defineTile('core:floor', { layer: 'terrain',
      sprite: 'floor_default.png',
      onEnterTerrain: function (state, cell, actor, fx) {
        if (!actor || actor.id !== 'player' || !actor.flags) return null;
        if (actor.flags.dash_step === state.steps) return null;
        const dir = state.last_input;
        if (!dir || !DIRS[dir]) return null;
        if (actor.flags.last_dir !== dir) return null;
        if (!hasCharge(state)) return null;
        actor.flags.dash_step = state.steps;
        fx.push({ type: 'consumeItem', item: 'dash:charge' });
        return dir;
      } });
    // Remember each step's direction for the next step's repeat
    // check. Blocked pushes count as moves in that direction, as
    // the teaching room's wall spend relies on.
    api.onTick(function (state) {
      const player = (state.actors || []).find(function (a) {
        return a.id === 'player';
      }) || (state.actors || [])[0];
      if (player && state.last_input && DIRS[state.last_input]) {
        player.flags.last_dir = state.last_input;
      }
    });
    api.onLevelLoad(function (state) {
      if (!state.chars.object['dash:dash-tile']) {
        state.chars.object['dash:dash-tile'] = 'D';
      }
      if (!state.chars.object['dash:gap']) {
        state.chars.object['dash:gap'] = 'V';
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerDashPack;
  }
  root.GamePackDashTile = registerDashPack;
})(typeof window !== 'undefined' ? window : globalThis);
