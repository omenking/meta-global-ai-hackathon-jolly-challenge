// Pack: chaser (mech-32-chaser sanity check).
// The chaser is an actor, not a tile: after each player move it
// takes one step in the same direction the player just moved, if
// that tile is free (the kernel's own enterability check decides);
// otherwise it stays. It is lethal on touch: stepping onto it, or
// it stepping onto the player, loses the attempt. Copying happens
// only when the player actually moves, so pushing into a wall does
// not drag the chaser along. All state advances through the pure
// step function and no rule reads wall-clock time. Restart restores
// the chaser because a fresh initialState respawns every actor.
// UMD: browser global GamePackChaser + Node export (register fn).
(function (root) {
  'use strict';
  function registerChaserPack(api) {
    for (const name of ['chaser.png', 'chaser-blocked.png']) {
      api.defineAsset(name, { pack: 'chaser', bundled: true });
    }
    const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
      left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
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
    // One copied step per player move: the controller runs while
    // the kernel collects move intents, so it copies the direction
    // of this step's input, but only if the player can really move
    // that way (a blocked push is not a move and copies nothing).
    api.defineController('chaser:chaser', function (state, actor) {
      const dir = state.last_input;
      actor.flags.want_dir = null;
      actor.flags.blocked = false;
      if (!dir || !DIRS[dir]) return null;
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return null;
      const d = DIRS[dir];
      if (!cellFree(state, player.x + d.x, player.y + d.y, player)) {
        return null;
      }
      actor.flags.want_dir = dir;
      actor.flags.from_x = actor.x;
      actor.flags.from_y = actor.y;
      return dir;
    });
    // Touch is lethal, and a copied step that was not free leaves
    // the chaser visibly held (the blocked pose) for that step.
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return;
      for (const actor of state.actors) {
        if (actor.def !== 'chaser:chaser') continue;
        if (actor.flags.want_dir) {
          actor.flags.blocked = actor.x === actor.flags.from_x
            && actor.y === actor.flags.from_y;
          actor.flags.want_dir = null;
        }
        if (actor.x === player.x && actor.y === player.y) {
          fx.push({ type: 'lose' });
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerChaserPack;
  }
  root.GamePackChaser = registerChaserPack;
})(typeof window !== 'undefined' ? window : globalThis);
