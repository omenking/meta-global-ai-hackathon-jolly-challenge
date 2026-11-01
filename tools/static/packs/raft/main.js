// Pack: raft block (mech-86-raft-block sanity check).
// Ride across water; sinks after 10 tiles travelled. The player
// steps onto the raft from a bank; each move then travels one water
// tile (shallow or deep) with the player aboard. Stepping onto a
// bank (floor) ends the ride and leaves the raft docked on the last
// water tile. The raft itself never enters floor, void, fire or
// lava. On the 10th travelled water tile it sinks and the player
// respawns at the checkpoint (level spawn); the raft returns to its
// placed bank. While riding, counters['raft:remaining'] drives the
// conditional GUI slot under the inventory. All state advances only
// through the pure step function (tick hook over recorded t_ms
// inputs); no rule reads wall-clock time.
// UMD: browser global GamePackRaft + Node export (register fn).
(function (root) {
  'use strict';
  var BUDGET = 10;
  function isWater(id) {
    return id === 'raft:water-shallow' || id === 'raft:water-deep';
  }
  function registerRaftPack(api) {
    for (const name of ['raft-block.png', 'raft-block-sinking.png',
      'jolly-riding-raft.png', 'jolly-sinking-raft.png',
      'raft-counter.png']) {
      api.defineAsset(name, { pack: 'raft', bundled: true });
    }
    function waterBlocks(state, cell) {
      if (state.flags && state.flags['raft:riding']) return false;
      return !(state.objects[cell.y] &&
        state.objects[cell.y][cell.x] === 'raft:raft');
    }
    api.defineTile('raft:water-shallow', { layer: 'terrain',
      glyph: '~', blocks: waterBlocks });
    api.defineTile('raft:water-deep', { layer: 'terrain',
      glyph: 'D', blocks: waterBlocks });
    api.defineTile('raft:fire', { layer: 'terrain', glyph: 'F',
      blocks: function () { return true; } });
    api.defineTile('raft:lava', { layer: 'terrain', glyph: 'L',
      blocks: function () { return true; } });
    api.defineTile('raft:void', { layer: 'object', glyph: 'V',
      blocks: function () { return true; } });
    api.defineTile('raft:raft', { layer: 'object',
      sprite: 'raft-block.png', glyph: 'R' });
    api.onLevelLoad(function (state) {
      state.counters['raft:remaining'] = 0;
      state.counters['raft:sinks'] = 0;
      state.flags['raft:riding'] = false;
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] === 'raft:raft') {
            state.counters['raft:start_x'] = x;
            state.counters['raft:start_y'] = y;
          }
        }
      }
      state.counters['raft:last_x'] = state.spawn.x;
      state.counters['raft:last_y'] = state.spawn.y;
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player') ||
        state.actors[0];
      if (!player) return;
      if (!state.flags['raft:riding']) {
        if (state.objects[player.y][player.x] === 'raft:raft') {
          state.objects[player.y][player.x] = null;
          state.flags['raft:riding'] = true;
          // Boarding tile is the first travelled water tile.
          state.counters['raft:remaining'] = BUDGET - 1;
          state.counters['raft:last_x'] = player.x;
          state.counters['raft:last_y'] = player.y;
        }
        return;
      }
      const lx = state.counters['raft:last_x'];
      const ly = state.counters['raft:last_y'];
      if (player.x === lx && player.y === ly) return;
      const terr = state.terrain[player.y][player.x];
      if (terr === 'core:floor') {
        state.objects[ly][lx] = 'raft:raft';
        state.flags['raft:riding'] = false;
        state.counters['raft:remaining'] = 0;
        state.counters['raft:last_x'] = player.x;
        state.counters['raft:last_y'] = player.y;
      } else if (isWater(terr)) {
        state.counters['raft:remaining'] -= 1;
        if (state.counters['raft:remaining'] <= 0) {
          state.counters['raft:sinks'] += 1;
          const sx = state.counters['raft:start_x'];
          const sy = state.counters['raft:start_y'];
          if (typeof sx === 'number') state.objects[sy][sx] = 'raft:raft';
          state.flags['raft:riding'] = false;
          state.counters['raft:remaining'] = 0;
          state.counters['raft:last_x'] = state.spawn.x;
          state.counters['raft:last_y'] = state.spawn.y;
          fx.push({ type: 'teleport', actor: 'player',
            x: state.spawn.x, y: state.spawn.y });
        } else {
          state.counters['raft:last_x'] = player.x;
          state.counters['raft:last_y'] = player.y;
        }
      } else {
        state.counters['raft:last_x'] = player.x;
        state.counters['raft:last_y'] = player.y;
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerRaftPack;
  }
  root.GamePackRaft = registerRaftPack;
})(typeof window !== 'undefined' ? window : globalThis);
