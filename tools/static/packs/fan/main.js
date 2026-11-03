// Pack: fan tile (mech-10-fan-tile sanity check).
// Fan tiles are terrain whose wind direction is marked on the
// tile. A player standing on a fan tile is pushed one tile
// downwind every recorded second if that tile is free, even
// with no directional input (a wait step). The push is driven
// only by the recorded t_ms carried in the input, never by an
// unrecorded wall-clock read, so a recorded session replays to
// the same end state. Blocked downwind (wall, closed gate,
// out of bounds) means no push that second. At most one tile
// per second, however large the t_ms gap.
// UMD: browser global GamePackFan + Node export (register fn).
(function (root) {
  'use strict';
  var DIRECTIONS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  function registerFanPack(api) {
    // Bundled assets (see manifest.json): generated art listed
    // in the candidate mechanic entry, saved into this pack.
    for (var i = 0, names = ['fan-north.png', 'fan-east.png',
      'fan-south.png', 'fan-west.png', 'jolly-pushed.png'];
         i < names.length; i++) {
      api.defineAsset(names[i], { pack: 'fan', bundled: true });
    }
    // Terrain tiles: walkable ground carrying a wind direction.
    api.defineTile('fan:fan-north', { layer: 'terrain',
      sprite: 'fan-north.png', glyph: '^', fanDir: 'up' });
    api.defineTile('fan:fan-east', { layer: 'terrain',
      sprite: 'fan-east.png', glyph: '>', fanDir: 'right' });
    api.defineTile('fan:fan-south', { layer: 'terrain',
      sprite: 'fan-south.png', glyph: 'v', fanDir: 'down' });
    api.defineTile('fan:fan-west', { layer: 'terrain',
      sprite: 'fan-west.png', glyph: '<', fanDir: 'left' });
    // Char -> def for levels that place fan tiles by glyph.
    api.onLevelDefs(function (level, ch, e) {
      if (!ch) return null;
      if (e && e.def) return null;
      if (ch === '^') return 'fan:fan-north';
      if (ch === '>') return 'fan:fan-east';
      if (ch === 'v') return 'fan:fan-south';
      if (ch === '<') return 'fan:fan-west';
      return null;
    });
    api.onLevelLoad(function (state) {
      state.counters['fan:last_second'] = Math.floor((state.t_ms || 0) / 1000);
    });
    function cellMeta(state, x, y) {
      return state.meta[x + ',' + y] || {};
    }
    function isEnterable(state, actor, x, y) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) return false;
      var terrId = state.terrain[y][x];
      var terr = terrId ? api.getTile(terrId) : null;
      if (terr && terr.blocks && terr.blocks(state,
          { x: x, y: y, def: terr, meta: cellMeta(state, x, y) }, actor)) {
        return false;
      }
      var objId = state.objects[y][x];
      var obj = objId ? api.getTile(objId) : null;
      if (obj && obj.blocks && obj.blocks(state,
          { x: x, y: y, def: obj, meta: cellMeta(state, x, y) }, actor)) {
        return false;
      }
      return true;
    }
    // One push per recorded second while the player stands on a
    // fan tile. Runs as a tick hook so it fires on every step,
    // including wait steps that carry no directional input.
    api.onTick(function (state, fx) {
      if (state.status && state.status !== 'playing') return;
      var player = (state.actors || []).find(function (a) {
        return a.id === 'player';
      }) || state.actors[0];
      if (!player) return;
      var terrId = state.terrain[player.y] && state.terrain[player.y][player.x];
      var def = terrId ? api.getTile(terrId) : null;
      var curSec = Math.floor((state.t_ms || 0) / 1000);
      if (!def || !def.fanDir) {
        state.counters['fan:last_second'] = curSec;
        return;
      }
      var lastSec = state.counters['fan:last_second'];
      if (typeof lastSec !== 'number') lastSec = 0;
      if (curSec <= lastSec) return;
      // One chance per second: the timer advances whether or not
      // the push succeeds, so a blocked second never queues.
      state.counters['fan:last_second'] = curSec;
      var d = DIRECTIONS[def.fanDir];
      var nx = player.x + d.x, ny = player.y + d.y;
      if (!isEnterable(state, player, nx, ny)) return;
      fx.push({ type: 'teleport', actor: player.id, x: nx, y: ny });
      // The tick runs after the kernel's object phase, so the
      // pushed-onto object's rule (orb, warp, void) must run here.
      var objId = state.objects[ny] && state.objects[ny][nx];
      if (objId) {
        var objDef = api.getTile(objId);
        if (objDef && objDef.onEnter) {
          objDef.onEnter(state,
            { x: nx, y: ny, def: objDef, meta: cellMeta(state, nx, ny) },
            player, fx);
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerFanPack;
  }
  root.GamePackFan = registerFanPack;
})(typeof window !== 'undefined' ? window : globalThis);
