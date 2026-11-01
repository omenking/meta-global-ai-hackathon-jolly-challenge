// Pack: bounce pad (mech-6-bounce-pad sanity check).
// Stepping on the pad compresses it for exactly one full move with
// the player standing on it, exposed; the next directional input
// then launches the player exactly two tiles that way, clearing the
// tile in between, and the landing tile must be empty floor or the
// launch falls and loses the attempt. The pad stage lives in cell
// meta (0 rest, 1 compressing, 2 ready); all state advances only
// through the pure step function via tile hooks (onEnter/blocks)
// and the tick hook's teleport/setMeta effects, and no rule reads
// wall-clock time. Restart restores the pad because a fresh
// initialState rebuilds the room with no meta.
// UMD: browser global GamePackBounce + Node export (register fn).
(function (root) {
  'use strict';
  var DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  function stageOf(state, x, y) {
    var m = state.meta[x + ',' + y];
    return (m && m.bounce_stage) || 0;
  }
  function padAt(state, x, y) {
    return x >= 0 && y >= 0 && x < state.width && y < state.height &&
      state.objects[y][x] === 'bounce:pad';
  }
  function registerBouncePack(api) {
    for (const name of ['bounce-pad.png', 'bounce-pad-compressed.png',
      'jolly-launching.png']) {
      api.defineAsset(name, { pack: 'bounce', bundled: true });
    }
    api.defineTile('bounce:pad', { layer: 'object',
      sprite: 'bounce-pad.png', glyph: 'B',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'bounce_stage', value: 1 });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'bounce_fresh', value: 1 });
      } });
    api.defineTile('bounce:void', { layer: 'object',
      sprite: 'void.png', glyph: 'V',
      // While the pad under the player is still compressing, the
      // gap cannot be entered yet: the early move is the pause.
      blocks: function (state, cell, actor) {
        return !!(actor && padAt(state, actor.x, actor.y) &&
          stageOf(state, actor.x, actor.y) === 1);
      },
      // Entering on foot is falling, except when this tile is the
      // cleared middle tile of a launch from a ready pad behind.
      onEnter: function (state, cell, actor, fx) {
        const d = actor && DIRS[actor.dir];
        if (d && padAt(state, cell.x - d.x, cell.y - d.y) &&
            stageOf(state, cell.x - d.x, cell.y - d.y) === 2) return;
        fx.push({ type: 'lose' });
      } });
    api.onLevelLoad(function (state) {
      if (!state.chars.object['bounce:pad']) {
        state.chars.object['bounce:pad'] = 'B';
      }
      state.chars.object['bounce:void'] = 'V';
    });
    // Compression, suppression and the launch itself. The kernel
    // moves the player one tile before this hook; the hook settles
    // the end-of-step state: a move made while compressing ends
    // back on the pad (now ready), and a move made while ready
    // ends two tiles from the pad (or falls when not floor).
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player') ||
        state.actors[0];
      if (!player || state.status === 'won' || state.status === 'lost') return;
      if (padAt(state, player.x, player.y)) {
        const stage = stageOf(state, player.x, player.y);
        const meta = state.meta[player.x + ',' + player.y] || {};
        if (stage === 1 && meta.bounce_fresh) {
          fx.push({ type: 'setMeta', x: player.x, y: player.y,
            key: 'bounce_fresh', value: 0 });
        } else if (stage === 1) {
          fx.push({ type: 'setMeta', x: player.x, y: player.y,
            key: 'bounce_stage', value: 2 });
        }
        return;
      }
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (!padAt(state, x, y)) continue;
          if (Math.abs(player.x - x) + Math.abs(player.y - y) !== 1) continue;
          const stage = stageOf(state, x, y);
          if (stage === 1) {
            fx.push({ type: 'teleport', actor: player.id, x: x, y: y });
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'bounce_stage', value: 2 });
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'bounce_fresh', value: 0 });
            return;
          }
          if (stage === 2) {
            const d = DIRS[player.dir];
            if (!d || player.x - d.x !== x || player.y - d.y !== y) continue;
            const lx = x + 2 * d.x, ly = y + 2 * d.y;
            const floor = lx >= 0 && ly >= 0 && lx < state.width &&
              ly < state.height &&
              (state.terrain[ly][lx] === 'core:floor' ||
               state.terrain[ly][lx] === 'core:spawn') &&
              !state.objects[ly][lx];
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'bounce_stage', value: 0 });
            fx.push({ type: 'setMeta', x: x, y: y,
              key: 'bounce_fresh', value: 0 });
            if (floor) {
              fx.push({ type: 'teleport', actor: player.id, x: lx, y: ly });
              fx.push({ type: 'bounceLaunch' });
            } else {
              fx.push({ type: 'lose' });
            }
            return;
          }
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerBouncePack;
  }
  root.GamePackBounce = registerBouncePack;
})(typeof window !== 'undefined' ? window : globalThis);
