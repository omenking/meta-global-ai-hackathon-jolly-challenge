// Pack: mirror block (mech-84-mirror-block sanity check).
// A mirror block is pushed exactly like a push block (81): one tile
// onto empty floor or a switch plate only; water, deep water, void,
// fire and lava (and walls, locks, gates, other blocks, enemies)
// block the push and both stay. An enemy that moves into it reverses
// direction instead of passing, so it edits a patroller/guard loop
// without touching the player; the player is unaffected by the face.
// Push is delivered through onEnter: the player steps toward the
// block, the block moves beyond (or the player is teleported back
// when the push is blocked). Enemy reversal is delivered by the
// patroller/guard controllers, which turn before entering the block.
// All state advances through the pure step function; no wall-clock.
// UMD: browser global GamePackMirrorBlock + Node export.
(function (root) {
  'use strict';
  var DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  var REV = { up: 'down', down: 'up', left: 'right', right: 'left' };
  var FLOOR_TERRAINS = { 'core:floor': 1, 'core:spawn': 1, 'mirror:switch': 1 };
  function registerMirrorPack(api) {
    for (const name of ['mirror-block.png', 'mirror-block-reversing.png']) {
      api.defineAsset(name, { pack: 'mirror-block', bundled: true });
    }
    // Terrain helpers owned by this pack so pushes can be tested
    // against every blocking ground without another mechanic built.
    api.defineTile('mirror:switch', { layer: 'terrain', sprite: 'floor_default.png', glyph: 's' });
    api.defineTile('mirror:water', { layer: 'terrain', glyph: '~',
      blocks: function () { return true; } });
    api.defineTile('mirror:deep-water', { layer: 'terrain', glyph: 'w',
      blocks: function () { return true; } });
    api.defineTile('mirror:void', { layer: 'terrain', glyph: 'v',
      blocks: function () { return true; } });
    api.defineTile('mirror:fire', { layer: 'terrain', glyph: 'f',
      blocks: function () { return true; } });
    api.defineTile('mirror:lava', { layer: 'terrain', glyph: 'l',
      blocks: function () { return true; } });
    api.defineTile('mirror:mirror-block', { layer: 'object',
      sprite: 'mirror-block.png', glyph: 'M',
      // Enemies never enter; the player enters only to push (below).
      blocks: function (state, cell, actor) {
        return !(actor && actor.id === 'player');
      },
      onEnter: function (state, cell, actor, fx) {
        if (!actor || actor.id !== 'player') return;
        var dir = actor.dir, d = DIRS[dir];
        if (!d) return;
        var bx = cell.x + d.x, by = cell.y + d.y;
        var ok = bx >= 0 && by >= 0 && bx < state.width && by < state.height
          && FLOOR_TERRAINS[state.terrain[by][bx]]
          && !state.objects[by][bx]
          && !state.actors.some(function (a) {
            return a.id !== 'player' && a.x === bx && a.y === by; });
        if (ok) {
          fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          fx.push({ type: 'setObject', x: bx, y: by, def: 'mirror:mirror-block' });
        } else {
          fx.push({ type: 'teleport', actor: actor.id,
            x: cell.x - d.x, y: cell.y - d.y });
        }
      } });
    function enemyDir(state, actor) {
      var cur = (actor.flags && actor.flags.dir) || actor.dir || 'right';
      if (!DIRS[cur]) cur = 'right';
      function blocked(x, y) {
        if (x < 0 || y < 0 || x >= state.width || y >= state.height) return true;
        if (state.objects[y][x] === 'mirror:mirror-block') return 'mirror';
        if (state.objects[y][x]) return true;
        return !FLOOR_TERRAINS[state.terrain[y][x]];
      }
      var d = DIRS[cur];
      var hit = blocked(actor.x + d.x, actor.y + d.y);
      if (hit) {
        var rev = REV[cur], rd = DIRS[rev];
        actor.flags = actor.flags || {};
        actor.flags.dir = rev;
        // Reverse on this move; stay only if the way back is blocked.
        return blocked(actor.x + rd.x, actor.y + rd.y) ? null : rev;
      }
      actor.flags = actor.flags || {};
      actor.flags.dir = cur;
      return cur;
    }
    api.defineController('mirror:patroller', enemyDir);
    api.defineController('mirror:guard', enemyDir);
    // Touch resets the attempt (kernel arbitration turns lose into
    // status lost; the game returns the player to the room start).
    api.onTick(function (state, fx) {
      var player = state.actors.find(function (a) { return a.id === 'player'; });
      if (!player) return;
      for (const a of state.actors) {
        if (a.id !== 'player' && a.x === player.x && a.y === player.y) {
          fx.push({ type: 'lose' }); return;
        }
      }
    });
    api.onLevelLoad(function (state) {
      if (!state.chars.object['mirror:mirror-block']) {
        state.chars.object['mirror:mirror-block'] = 'M';
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMirrorPack;
  }
  root.GamePackMirrorBlock = registerMirrorPack;
})(typeof window !== 'undefined' ? window : globalThis);
