// Pack: patrolling monster (pressure test c).
// beast:monster is an actor spawned from the level legend (actor:
// "beast:monster"). Its controller is a deterministic wall-bounce
// patrol: one tile per step, reversing at walls. Contact with the
// player loses (tick hook). Monsters move in the move phase only;
// they do not pick up objects.
// UMD: browser global GamePackMonsters + Node export.
(function (root) {
  'use strict';
  function registerMonstersPack(api) {
    api.defineController('beast:monster', function (state, actor) {
      let dir = actor.flags.dir || 'right';
      const delta = dir === 'right' ? 1 : -1;
      const nx = actor.x + delta;
      if (nx < 0 || nx >= state.width
          || state.terrain[actor.y][nx] === 'core:wall') {
        dir = dir === 'right' ? 'left' : 'right';
      }
      actor.flags.dir = dir;
      return dir;
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return;
      for (const a of state.actors) {
        if (a.id !== 'player' && a.x === player.x && a.y === player.y) {
          fx.push({ type: 'lose' });
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = registerMonstersPack;
  root.GamePackMonsters = registerMonstersPack;
})(typeof window !== 'undefined' ? window : globalThis);
