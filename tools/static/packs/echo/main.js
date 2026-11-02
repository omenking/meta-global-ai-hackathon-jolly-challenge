// Pack: echo tile (mech-54-echo-tile sanity check).
// Standing on the echo tile pings an eight-direction indicator
// toward the nearest uncollected orb. The ping gives a direction
// only: it stores one of eight compass names in state flags, never
// a picture, distance, route or reveal, so the search stays the
// player's. The tile is reusable after a few moves: a ping sets a
// cooldown of COOLDOWN_MOVES steps which ticks down only while the
// player is off the tile, so stepping straight back on does not
// re-ping at once. All state advances through the pure step
// function (onEnter + tick hooks); no rule reads wall-clock.
// Restart restores the ready tile because a fresh initialState
// rebuilds flags and cooldown.
// UMD: browser global GamePackEcho + Node export (register fn).
(function (root) {
  'use strict';
  var COOLDOWN_MOVES = 3;
  var DIRS = { '-1,-1': 'northwest', '0,-1': 'north', '1,-1': 'northeast',
    '-1,0': 'west', '1,0': 'east', '-1,1': 'southwest', '0,1': 'south',
    '1,1': 'southeast' };
  function directionTo(from, to) {
    var dx = Math.sign(to.x - from.x), dy = Math.sign(to.y - from.y);
    if (dx === 0 && dy === 0) return null;
    return DIRS[dx + ',' + dy] || null;
  }
  function nearestOrb(state, from) {
    var best = null, bestD = Infinity;
    for (var y = 0; y < state.height; y++) {
      for (var x = 0; x < state.width; x++) {
        var id = state.objects[y][x];
        if (id !== 'core:orb' && id !== 'hidden:hidden-orb') continue;
        var d = Math.max(Math.abs(x - from.x), Math.abs(y - from.y));
        if (d < bestD) { bestD = d; best = { x: x, y: y }; }
      }
    }
    return best;
  }
  function echoCells(state) {
    var out = [];
    for (var y = 0; y < state.height; y++) {
      for (var x = 0; x < state.width; x++) {
        if (state.objects[y][x] === 'echo:echo') out.push({ x: x, y: y });
      }
    }
    return out;
  }
  function registerEchoPack(api) {
    for (var i = 0; i < 4; i++) {
      api.defineAsset(['echo.png', 'echo-cooling.png',
        'jolly-on-echo.png', 'echo-ping.png'][i],
        { pack: 'echo', bundled: true });
    }
    api.defineTile('echo:echo', { layer: 'object',
      sprite: 'echo.png', glyph: 'e',
      onEnter: function (state, cell, actor, fx) {
        if ((state.flags['echo:cooldown'] || 0) > 0) return;
        var target = nearestOrb(state, cell);
        if (!target) return;
        var dir = directionTo(cell, target);
        if (!dir) return;
        state.flags['echo:direction'] = dir;
        state.flags['echo:cooldown'] = COOLDOWN_MOVES;
        state.flags['echo:ping_count'] =
          (state.flags['echo:ping_count'] || 0) + 1;
        state.flags['echo:last_ping_t_ms'] = state.t_ms;
      } });
    api.onTick(function (state, fx) {
      var cd = state.flags['echo:cooldown'] || 0;
      if (cd <= 0) return;
      var player = state.actors.find(function (a) {
        return a.id === 'player';
      }) || state.actors[0];
      if (!player) return;
      var onEcho = echoCells(state).some(function (c) {
        return c.x === player.x && c.y === player.y;
      });
      if (!onEcho) state.flags['echo:cooldown'] = cd - 1;
    });
    api.onLevelLoad(function (state) {
      state.chars.object['echo:echo'] = 'e';
      state.flags['echo:cooldown'] = 0;
      state.flags['echo:direction'] = null;
      state.flags['echo:ping_count'] = 0;
    });
    api.onLevelDefs(function (level, ch) {
      if (ch === 'e') return 'echo:echo';
      return null;
    });
  }
  registerEchoPack.COOLDOWN_MOVES = COOLDOWN_MOVES;
  registerEchoPack.directionTo = directionTo;
  registerEchoPack.nearestOrb = nearestOrb;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerEchoPack;
  }
  root.GamePackEcho = registerEchoPack;
})(typeof window !== 'undefined' ? window : globalThis);
