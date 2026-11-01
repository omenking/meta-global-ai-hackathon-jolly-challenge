// Pack: conveyor tile (mech-2-conveyor-tile sanity check).
// Step onto a belt and, at the start of each later move, it carries
// you one tile in its arrow direction. While on the belt you cannot
// step off sideways: any input while standing on a belt resolves to
// the belt's one-tile carry instead of the voluntary step. You get
// off only where the belt ends on a normal tile, so the route is
// chosen on the normal tile before the belt takes over. A belt that
// runs into a hazard carries you into it (the hazard's own onEnter
// resolves the attempt, e.g. void loses), never a stranded belt
// state. All state advances through the pure step function: the
// carry is a tick-hook teleport effect computed only from the
// recorded input (state.last_input) and the belt under the player,
// with no wall-clock reads. The entry step itself never carries:
// entering a belt marks the actor with the current step count, and
// the tick carry is skipped for that step, so each move on the belt
// moves exactly one tile. Restart restores the placed belts because
// a fresh initialState rebuilds the room.
// UMD: browser global GamePackConveyor + Node export (register fn).
(function (root) {
  'use strict';
  var DIRS = { north: { x: 0, y: -1 }, east: { x: 1, y: 0 },
    south: { x: 0, y: 1 }, west: { x: -1, y: 0 } };
  var INPUT_DIRS = { up: 'north', down: 'south',
    left: 'west', right: 'east' };
  function registerConveyorPack(api) {
    for (const name of ['conveyor-north.png', 'conveyor-east.png',
      'conveyor-south.png', 'conveyor-west.png', 'jolly-carried.png']) {
      api.defineAsset(name, { pack: 'conveyor', bundled: true });
    }
    function belt(id, dirName, sprite, glyph) {
      api.defineTile(id, { layer: 'terrain', sprite: sprite,
        glyph: glyph, conveyorDir: dirName,
        onEnterTerrain: function (state, cell, actor, fx) {
          // Mark the entry step; the tick carry below skips it so
          // stepping onto a belt never also carries in that move.
          actor.flags.conveyor_step = state.steps;
          return null;
        } });
    }
    belt('conveyor:conveyor-north', 'north', 'conveyor-north.png', '^');
    belt('conveyor:conveyor-east', 'east', 'conveyor-east.png', '>');
    belt('conveyor:conveyor-south', 'south', 'conveyor-south.png', 'v');
    belt('conveyor:conveyor-west', 'west', 'conveyor-west.png', '<');
    function tileDef(state, layer, x, y) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) {
        return null;
      }
      const id = state[layer][y][x];
      return id ? api.getTile(id) : null;
    }
    function metaAt(state, x, y) {
      return (state.meta && state.meta[x + ',' + y]) || {};
    }
    function enterable(state, actor, x, y) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) {
        return false;
      }
      const terr = tileDef(state, 'terrain', x, y);
      if (terr && terr.blocks && terr.blocks(state,
        { x: x, y: y, def: terr, meta: metaAt(state, x, y) }, actor)) {
        return false;
      }
      const obj = tileDef(state, 'objects', x, y);
      if (obj && obj.blocks && obj.blocks(state,
        { x: x, y: y, def: obj, meta: metaAt(state, x, y) }, actor)) {
        return false;
      }
      return true;
    }
    api.onTick(function (state, fx) {
      const player = (state.actors || []).find(
        (a) => a.id === 'player') || (state.actors || [])[0];
      if (!player) return;
      // Entered a belt on this very step: no carry yet.
      if (player.flags && player.flags.conveyor_step === state.steps) {
        return;
      }
      // Reconstruct where this move started. If the voluntary step
      // moved the player, the start is one recorded-input tile back;
      // if it was blocked, the start is the player's own tile.
      let start = null;
      const inputDir = INPUT_DIRS[state.last_input];
      if (inputDir) {
        const d = DIRS[inputDir];
        const cx = player.x - d.x, cy = player.y - d.y;
        const cand = tileDef(state, 'terrain', cx, cy);
        if (cand && cand.conveyorDir) start = { x: cx, y: cy, def: cand };
      }
      if (!start) {
        const here = tileDef(state, 'terrain', player.x, player.y);
        if (here && here.conveyorDir) {
          start = { x: player.x, y: player.y, def: here };
        }
      }
      if (!start) return;
      const d = DIRS[start.def.conveyorDir];
      const tx = start.x + d.x, ty = start.y + d.y;
      if (tx === player.x && ty === player.y) return;
      if (!enterable(state, player, tx, ty)) return;
      fx.push({ type: 'teleport', actor: player.id, x: tx, y: ty });
      // Resolve the landing cell through its own defs (void loses,
      // warp wins, orb collects), as if the player had entered it.
      const terr = tileDef(state, 'terrain', tx, ty);
      if (terr && terr.onEnterTerrain) {
        terr.onEnterTerrain(state,
          { x: tx, y: ty, def: terr, meta: metaAt(state, tx, ty) },
          player, fx);
      }
      const obj = tileDef(state, 'objects', tx, ty);
      if (obj && obj.onEnter) {
        obj.onEnter(state,
          { x: tx, y: ty, def: obj, meta: metaAt(state, tx, ty) },
          player, fx);
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerConveyorPack;
  }
  root.GamePackConveyor = registerConveyorPack;
})(typeof window !== 'undefined' ? window : globalThis);
