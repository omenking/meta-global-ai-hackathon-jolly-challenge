// Pack: fog tile (mech-53-fog-tile sanity check).
// A fog tile never shows what is on it until the player stands
// next to it (a tile sharing a side, Manhattan distance <= 1,
// including standing on the fog itself), after which it stays
// revealed for the attempt in cell meta (fog_revealed). Movement
// through fog is normal: fog tiles never block and cost the
// usual one move per tile, so fog hides locally in a lit room.
// An orb on a fog tile (fog:fog-orb) is hidden until that tile is
// revealed, counts toward the gate like any orb, and stepping
// onto it collects it, leaving revealed empty fog behind. The
// reveal advances only in the tick hook of the pure step function
// and on level load (spawn adjacency); no rule reads wall-clock.
// Restart restores every fog tile because a fresh initialState
// rebuilds the room with all fog unrevealed.
// UMD: browser global GamePackFog + Node export (register fn).
(function (root) {
  'use strict';
  var FOG_DEFS = { 'fog:fog': true, 'fog:fog-orb': true };
  function isFogDef(id) { return !!FOG_DEFS[id]; }
  function isRevealed(state, x, y) {
    var m = (state && state.meta && state.meta[x + ',' + y]) || {};
    return !!m.fog_revealed;
  }
  function adjacentFog(state, px, py) {
    var out = [];
    for (var y = 0; y < state.height; y++) {
      for (var x = 0; x < state.width; x++) {
        if (!isFogDef(state.objects[y][x])) continue;
        if (Math.abs(x - px) + Math.abs(y - py) <= 1) {
          out.push({ x: x, y: y });
        }
      }
    }
    return out;
  }
  function registerFogPack(api) {
    for (var i = 0; i < 3; i++) {
      api.defineAsset(['fog.png', 'fog-revealed.png',
        'fog-revealed-orb.png'][i], { pack: 'fog', bundled: true });
    }
    api.defineTile('fog:fog', { layer: 'object',
      sprite: 'fog.png', glyph: 'F' });
    api.defineTile('fog:fog-orb', { layer: 'object',
      sprite: 'fog.png', glyph: 'f',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'fog:fog' });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'fog_revealed', value: true });
        fx.push({ type: 'incCounter', key: 'core:orbs_left', by: -1 });
      } });
    api.onLevelLoad(function (state) {
      state.chars.object['fog:fog'] = 'F';
      state.chars.object['fog:fog-orb'] = 'f';
      var n = 0;
      for (var y = 0; y < state.height; y++) {
        for (var x = 0; x < state.width; x++) {
          if (isFogDef(state.objects[y][x])) {
            var k = x + ',' + y;
            state.meta[k] = Object.assign({}, state.meta[k],
              { fog_revealed: false });
            if (state.objects[y][x] === 'fog:fog-orb') n++;
          }
        }
      }
      if (n) {
        state.counters['core:orbs_left'] =
          (state.counters['core:orbs_left'] || 0) + n;
      }
      var player = state.actors.find(function (a) {
        return a.id === 'player';
      }) || state.actors[0];
      if (player) {
        for (var j = 0; j < adjacentFog(state, player.x, player.y).length; j++) {
          var c = adjacentFog(state, player.x, player.y)[j];
          state.meta[c.x + ',' + c.y] = Object.assign({},
            state.meta[c.x + ',' + c.y], { fog_revealed: true });
        }
      }
    });
    api.onTick(function (state, fx) {
      var player = state.actors.find(function (a) {
        return a.id === 'player';
      }) || state.actors[0];
      if (!player) return;
      var cells = adjacentFog(state, player.x, player.y);
      for (var i = 0; i < cells.length; i++) {
        if (!isRevealed(state, cells[i].x, cells[i].y)) {
          fx.push({ type: 'setMeta', x: cells[i].x, y: cells[i].y,
            key: 'fog_revealed', value: true });
        }
      }
    });
    api.onLevelDefs(function (level, ch) {
      if (ch === 'F') return 'fog:fog';
      if (ch === 'f') return 'fog:fog-orb';
      return null;
    });
  }
  registerFogPack.isRevealed = isRevealed;
  registerFogPack.isFogDef = isFogDef;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerFogPack;
  }
  root.GamePackFog = registerFogPack;
})(typeof window !== 'undefined' ? window : globalThis);
