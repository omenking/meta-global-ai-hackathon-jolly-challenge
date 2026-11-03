// Pack: thief (mech-35-thief sanity check).
// The thief is an actor, not a tile: it moves one tile per player
// move away from the player and is not lethal, so touching it can
// never lose the attempt. If it starts a move next to the player it
// snatches the player's most recent key, carries it visibly (the
// renderer swaps to the carrying sprite from actor flags), then
// runs for its burrow tile and drops the key there, where the
// player can pick it back up. Cornering it and touching it before
// it reaches the burrow makes it drop the key where it stands.
// All state advances through the pure step function (controller +
// tick hooks only) and no rule reads wall-clock time. Restart
// restores the thief, burrow and keys because a fresh initialState
// respawns every actor. UMD: browser global GamePackThief + Node
// export (register fn).
(function (root) {
  'use strict';
  function registerThiefPack(api) {
    for (const name of ['thief.png', 'thief-carrying-key.png',
      'thief-burrow.png']) {
      api.defineAsset(name, { pack: 'thief', bundled: true });
    }
    // Visual def for the actor: the kernel never places this as a
    // tile (the thief spawns as an actor), but game.js resolves the
    // actor's sprite through getTileDef(actor.def).
    api.defineTile('thief:thief', { layer: 'object',
      sprite: 'thief.png', glyph: 'T' });
    api.defineTile('thief:burrow', { layer: 'terrain',
      sprite: 'thief-burrow.png', glyph: 'B' });
    const ORDER = ['up', 'left', 'right', 'down'];
    const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
      left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
    function dist(ax, ay, bx, by) {
      return Math.abs(ax - bx) + Math.abs(ay - by);
    }
    function cellFree(state, x, y, actor) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) {
        return false;
      }
      const terr = api.getTile(state.terrain[y][x]);
      if (terr && terr.blocks && terr.blocks(state,
        { x: x, y: y, def: terr, meta: {} }, actor)) return false;
      const objId = state.objects[y][x];
      const obj = objId ? api.getTile(objId) : null;
      if (obj && obj.blocks && obj.blocks(state,
        { x: x, y: y, def: obj, meta: {} }, actor)) return false;
      return true;
    }
    function findBurrow(state) {
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.terrain[y][x] === 'thief:burrow') return { x: x, y: y };
        }
      }
      return null;
    }
    function mostRecentKey(state) {
      const inv = state.inventory || [];
      for (let i = inv.length - 1; i >= 0; i--) {
        if (typeof inv[i].item === 'string'
          && inv[i].item.indexOf('keys:key-') === 0) return inv[i].item;
      }
      return null;
    }
    // One step per player step. The controller runs while the kernel
    // collects intents, so positions here are the start-of-move
    // positions the snatch rule is stated in.
    api.defineController('thief:thief', function (state, actor) {
      const player = state.actors.find((a) => a.id === 'player');
      actor.flags.snatch = null;
      if (!player) return null;
      let carrying = actor.flags.carrying || null;
      if (!carrying
        && dist(actor.x, actor.y, player.x, player.y) === 1) {
        const key = mostRecentKey(state);
        if (key) { actor.flags.snatch = key; carrying = key; }
      }
      const burrow = findBurrow(state);
      if (carrying && burrow) {
        if (actor.x === burrow.x && actor.y === burrow.y) return null;
        let best = null, bestScore = null;
        for (const dir of ORDER) {
          const nx = actor.x + DIRS[dir].x, ny = actor.y + DIRS[dir].y;
          if (!cellFree(state, nx, ny, actor)) continue;
          const score = dist(nx, ny, burrow.x, burrow.y) * 100
            - dist(nx, ny, player.x, player.y);
          if (bestScore === null || score < bestScore) {
            bestScore = score; best = dir;
          }
        }
        return best;
      }
      // Flee: the free neighbour farthest from the player; the fixed
      // ORDER breaks ties so replays stay deterministic.
      let best = null, bestDist = -1;
      for (const dir of ORDER) {
        const nx = actor.x + DIRS[dir].x, ny = actor.y + DIRS[dir].y;
        if (!cellFree(state, nx, ny, actor)) continue;
        const d = dist(nx, ny, player.x, player.y);
        if (d > bestDist) { bestDist = d; best = dir; }
      }
      return best;
    });
    // Snatch, burrow drop and touch drop settle after the move: the
    // snatch removes the most recent key, reaching the burrow or
    // being touched drops the carried key as a pickable tile.
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return;
      const burrow = findBurrow(state);
      for (const actor of state.actors) {
        if (actor.def !== 'thief:thief') continue;
        if (actor.flags.snatch) {
          const inv = state.inventory || [];
          for (let i = inv.length - 1; i >= 0; i--) {
            if (inv[i].item === actor.flags.snatch) {
              inv.splice(i, 1); break;
            }
          }
          actor.flags.carrying = actor.flags.snatch;
          actor.flags.snatch = null;
        }
        const carrying = actor.flags.carrying;
        if (!carrying) continue;
        const atBurrow = burrow && actor.x === burrow.x
          && actor.y === burrow.y;
        const touched = actor.x === player.x && actor.y === player.y;
        if (atBurrow || touched) {
          fx.push({ type: 'setObject', x: actor.x, y: actor.y,
            def: carrying });
          actor.flags.carrying = null;
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerThiefPack;
  }
  root.GamePackThief = registerThiefPack;
})(typeof window !== 'undefined' ? window : globalThis);
