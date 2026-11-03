// Pack: swap tile (mech-93-swap-tile sanity check).
// A swap tile sits under a block or bot. Standing next to it and
// pressing toward it exchanges the player's tile with the block
// or bot on it: the player takes its place on the swap tile and
// it takes the player's old tile. The swap tile itself is the
// terrain under the entity, so it stays behind after the swap
// and can be reused: pressing back toward the entity from the
// swap tile swaps both back again. An entity that is not part
// of a swap pair (neither its tile nor the player's tile is a
// swap tile) simply blocks movement, like a block should. All
// state advances through the pure step function; no rule reads
// wall-clock time. Restart restores the placed entity because a
// fresh initialState rebuilds the room.
// UMD: browser global GamePackSwap + Node export (register fn).
(function (root) {
  'use strict';
  var DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  function registerSwapPack(api) {
    for (const name of ['swap-tile.png', 'swap-tile-occupied.png',
      'jolly-swapping.png']) {
      api.defineAsset(name, { pack: 'swap', bundled: true });
    }
    function pairInvolvesSwapTile(state, cell, actor) {
      if (state.terrain[cell.y][cell.x] === 'swap:floor') return true;
      return !!(state.terrain[actor.y] &&
        state.terrain[actor.y][actor.x] === 'swap:floor');
    }
    function swappable(defId, glyph) {
      return { layer: 'object', sprite: 'swap-tile-occupied.png',
        glyph: glyph,
        blocks: function (state, cell, actor) {
          if (!actor || actor.id !== 'player') return true;
          const dir = DIRS[state.last_input];
          if (!dir) return true;
          if (actor.x + dir.x !== cell.x ||
              actor.y + dir.y !== cell.y) return true;
          return !pairInvolvesSwapTile(state, cell, actor);
        },
        onEnter: function (state, cell, actor, fx) {
          if (!actor || actor.id !== 'player') return;
          const dir = DIRS[actor.dir] || DIRS[state.last_input];
          if (!dir) return;
          // The actor already stands on the entered cell, so the
          // pair check must look at the vacated tile behind it.
          const prev = { x: cell.x - dir.x, y: cell.y - dir.y };
          const prevActor = { x: prev.x, y: prev.y, id: actor.id };
          if (!pairInvolvesSwapTile(state, cell, prevActor)) return;
          fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          fx.push({ type: 'setObject', x: cell.x - dir.x,
            y: cell.y - dir.y, def: defId });
        } };
    }
    api.defineTile('swap:floor', { layer: 'terrain',
      sprite: 'swap-tile.png', glyph: 'S' });
    api.defineTile('swap:block', swappable('swap:block', 'B'));
    api.defineTile('swap:bot', swappable('swap:bot', 'M'));
    api.onLevelLoad(function (state) {
      state.chars.terrain['swap:floor'] = 'S';
      state.chars.object['swap:block'] = 'B';
      state.chars.object['swap:bot'] = 'M';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerSwapPack;
  }
  root.GamePackSwap = registerSwapPack;
})(typeof window !== 'undefined' ? window : globalThis);
