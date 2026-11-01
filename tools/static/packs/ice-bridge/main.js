// Pack: ice bridge (mech-50-ice-bridge sanity check).
// An ice bridge is not placed directly: in the full game it forms
// when an ice block (mech 82, unbuilt) is pushed into shallow water.
// This pack provides the bridge itself plus the shallow water it
// spans, so the teaching room starts already bridged, exactly as its
// teaching moment describes. Shallow water alone cannot be entered
// (it is not lethal: melting through returns the player to the room
// start, the checkpoint fallback until mech 48 lands), but a bridge
// tile over it can. Walking across without a stopped move is safe;
// ending a full move on the same bridge tile you started it on (a
// wait or a blocked push) melts that tile, you fall, and you return
// to the room start. A bridge tile next to fire also melts; fire
// spread itself is mech 43 (unbuilt), so this pack only reacts to an
// adjacent fire def if one is ever registered. All state advances
// through the pure step function (tick hook + recorded t_ms); no
// rule reads wall-clock time. Restart restores the bridge because a
// fresh initialState rebuilds the room.
// UMD: browser global GamePackIceBridge + Node export (register fn).
(function (root) {
  'use strict';
  function registerIceBridgePack(api) {
    for (const name of ['ice-bridge.png', 'ice-bridge-melting.png']) {
      api.defineAsset(name, { pack: 'ice-bridge', bundled: true });
    }
    api.defineTile('icebridge:shallow', { layer: 'terrain', glyph: '~',
      sprite: 'ice-bridge.png',
      // Shallow water carries no one on its own; a bridge object
      // over this cell is what makes the cell enterable.
      blocks: function (state, cell) {
        return state.objects[cell.y][cell.x] !== 'icebridge:bridge'
          && state.objects[cell.y][cell.x] !== 'icebridge:melting';
      } });
    api.defineTile('icebridge:bridge', { layer: 'object',
      sprite: 'ice-bridge.png', glyph: 'I' });
    // Melting is the visible state of a bridge in the move where the
    // player stands still on it; the fall happens in that same move,
    // so this def carries the art for the melt moment and any future
    // staged render, while the tick rule below does the falling.
    api.defineTile('icebridge:melting', { layer: 'object',
      sprite: 'ice-bridge-melting.png', glyph: 'M' });
    api.onLevelLoad(function (state) {
      if (!state.chars.terrain['icebridge:shallow']) {
        state.chars.terrain['icebridge:shallow'] = '~';
      }
      if (!state.chars.object['icebridge:bridge']) {
        state.chars.object['icebridge:bridge'] = 'I';
      }
      state.chars.object['icebridge:melting'] = 'M';
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return;
      // Fire adjacency: any bridge next to a fire cell melts. Fire
      // spread (mech 43) is unbuilt, so in practice no fire def is
      // registered yet; this reacts to the def id if one appears.
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] !== 'icebridge:bridge') continue;
          const near = [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]]
            .some(([nx, ny]) => nx >= 0 && ny >= 0
              && nx < state.width && ny < state.height
              && (((state.objects[ny][nx] || '') + '').includes('fire')
                || ((state.terrain[ny][nx] || '') + '').includes('fire')));
          if (near) fx.push({ type: 'removeObject', x: x, y: y });
        }
      }
      // Standing still: the player ended this move on the same
      // bridge tile they started it on (wait or blocked push).
      const here = player.x + ',' + player.y;
      const last = state.flags['icebridge:last_pos'];
      const onBridge = state.objects[player.y][player.x] === 'icebridge:bridge';
      if (onBridge && last === here) {
        fx.push({ type: 'removeObject', x: player.x, y: player.y });
        fx.push({ type: 'teleport', actor: 'player',
          x: state.spawn.x, y: state.spawn.y });
        state.flags['icebridge:last_pos'] =
          state.spawn.x + ',' + state.spawn.y;
      } else {
        state.flags['icebridge:last_pos'] = here;
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerIceBridgePack;
  }
  root.GamePackIceBridge = registerIceBridgePack;
})(typeof window !== 'undefined' ? window : globalThis);
