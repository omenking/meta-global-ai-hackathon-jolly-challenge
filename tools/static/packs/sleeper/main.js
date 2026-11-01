// Pack: sleeper (mech-33-sleeper sanity check).
// A sleeper sits asleep and solid on its tile until any orb
// anywhere in the level is collected; it is not tied to one
// specific orb. From then on it patrols a fixed marked loop at
// one tile per player move, lethal on touch like a patroller
// (mech-31): touch — ending a step on the same tile, or swapping
// tiles within one step — returns the player to the level spawn
// (or the active checkpoint where one is placed, per mech-48; no
// checkpoint tile exists in this pack, so the spawn is the
// respawn here), and the room can be retried, never stranded.
// While asleep its tile carries a solid blocker object, so the
// tile cannot be entered; the blocker is removed on the step the
// first orb is collected, and the sleeper starts patrolling on
// the next player move. The loop is the ordered `sleeper_loop`
// cell list in the level JSON; the controller steps each sleeper
// to the next listed cell (the list wraps). Restart restores the
// sleeper asleep on its placed tile with no orb collected,
// because a fresh initialState rebuilds the room. All state
// advances through the pure step function; no rule reads
// wall-clock time (only the recorded input t_ms drives state).
// UMD: browser global GamePackSleeper + Node export.
(function (root) {
  'use strict';
  var DIRS = { '0,-1': 'up', '0,1': 'down', '-1,0': 'left', '1,0': 'right' };
  function awake(state) {
    const total = state.counters['sleeper:orbs_at_start'];
    return typeof total === 'number' && total > 0
      && (state.counters['core:orbs_left'] || 0) < total;
  }
  function registerSleeperPack(api) {
    // Bundled assets (see manifest.json): real generated art.
    for (const name of ['sleeper-asleep.png', 'sleeper-awake.png',
      'sleeper-loop.png']) {
      api.defineAsset(name, { pack: 'sleeper', bundled: true });
    }
    // Marked loop tiles: walkable terrain the sleeper follows.
    api.defineTile('sleeper:loop', { layer: 'terrain',
      sprite: 'sleeper-loop.png', glyph: 'L' });
    // Sprite carrier for the sleeper actor: the kernel spawns
    // actors from the legend, and game.js draws each non-player
    // actor with the sprite of its actor def (asleep sprite here;
    // game.js swaps to the awake sprite once woken). Never placed
    // as an object tile.
    api.defineTile('sleeper:sleeper', { layer: 'object',
      sprite: 'sleeper-asleep.png', glyph: 'S' });
    // Asleep body: solid on its tile until the first orb wakes
    // the sleeper, when the tick hook below removes it.
    api.defineTile('sleeper:blocker', { layer: 'object',
      sprite: 'sleeper-asleep.png', glyph: 'S',
      blocks: function () { return true; } });
    api.onLevelLoad(function (state, level) {
      state.chars.terrain['sleeper:loop'] = 'L';
      state.chars.object['sleeper:blocker'] = 'S';
      state.counters['sleeper:orbs_at_start'] =
        state.counters['core:orbs_left'] || 0;
      state.flags['sleeper:awake'] = false;
      const raw = (level && level.sleeper_loop) || [];
      const loop = raw.map(function (p) {
        return Array.isArray(p) ? { x: p[0], y: p[1] } : { x: p.x, y: p.y };
      });
      for (const actor of state.actors) {
        if (actor.def !== 'sleeper:sleeper') continue;
        state.objects[actor.y][actor.x] = 'sleeper:blocker';
        if (loop.length < 2) continue;
        actor.flags.loop = loop;
        actor.flags.prevX = actor.x;
        actor.flags.prevY = actor.y;
        actor.flags.loopIndex = 0;
        for (let k = 0; k < loop.length; k++) {
          if (loop[k].x === actor.x && loop[k].y === actor.y) {
            actor.flags.loopIndex = k;
            break;
          }
        }
      }
    });
    // Asleep: no move. Awake: one tile per player move along the
    // marked loop (index in actor flags, as in the patroller).
    api.defineController('sleeper:sleeper', function (state, actor) {
      actor.flags.prevX = actor.x;
      actor.flags.prevY = actor.y;
      if (!awake(state)) return null;
      const loop = actor.flags && actor.flags.loop;
      if (!loop || loop.length < 2) return null;
      const i = typeof actor.flags.loopIndex === 'number'
        ? actor.flags.loopIndex : 0;
      const nxt = loop[(i + 1) % loop.length];
      actor.flags.loopIndex = (i + 1) % loop.length;
      return DIRS[(nxt.x - actor.x) + ',' + (nxt.y - actor.y)] || null;
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return;
      if (!state.flags['sleeper:awake'] && awake(state)) {
        state.flags['sleeper:awake'] = true;
        for (const actor of state.actors) {
          if (actor.def === 'sleeper:sleeper') {
            fx.push({ type: 'removeObject', x: actor.x, y: actor.y });
          }
        }
      }
      if (!awake(state)) return;
      const d = { up: [0, -1], down: [0, 1], left: [-1, 0],
        right: [1, 0] }[state.last_input] || [0, 0];
      const pPrevX = player.x - d[0], pPrevY = player.y - d[1];
      for (const actor of state.actors) {
        if (actor.def !== 'sleeper:sleeper') continue;
        const overlap = actor.x === player.x && actor.y === player.y;
        const swapped = actor.x === pPrevX && actor.y === pPrevY
          && player.x === actor.flags.prevX
          && player.y === actor.flags.prevY;
        if (overlap || swapped) {
          fx.push({ type: 'teleport', actor: player.id,
            x: state.spawn.x, y: state.spawn.y });
          return;
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerSleeperPack;
  }
  root.GamePackSleeper = registerSleeperPack;
})(typeof window !== 'undefined' ? window : globalThis);
