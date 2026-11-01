// Pack: alarm tile (mech-38-alarm-tile sanity check).
// Stepping on the alarm rings once: every sleeper in the same
// room wakes immediately (asleep solid tile -> awake lethal tile)
// and the alarm becomes inert floor. Sleepers in other rooms
// (separated by walls) never wake: the room is the wall-bounded
// flood-fill region of floor containing the alarm. A second step
// on the inert tile does nothing. Restart restores everything
// because a fresh initialState rebuilds the room. All state
// advances through the pure step function; no wall-clock reads.
// UMD: browser global GamePackAlarm + Node export (register fn).
(function (root) {
  'use strict';
  function roomCells(state, sx, sy) {
    // Wall-bounded flood fill over floor terrain from (sx, sy).
    const seen = {}, queue = [[sx, sy]], cells = [];
    seen[sx + ',' + sy] = true;
    while (queue.length) {
      const [x, y] = queue.pop();
      cells.push({ x: x, y: y });
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nx = x + dx, ny = y + dy, k = nx + ',' + ny;
        if (seen[k] || nx < 0 || ny < 0 || nx >= state.width || ny >= state.height) continue;
        const terr = state.terrain[ny][nx];
        if (terr !== 'core:floor' && terr !== 'core:spawn') continue;
        seen[k] = true; queue.push([nx, ny]);
      }
    }
    return cells;
  }
  function registerAlarmPack(api) {
    for (const name of ['alarm.png', 'alarm-inert.png']) {
      api.defineAsset(name, { pack: 'alarm', bundled: true });
    }
    api.defineTile('alarm:tile', { layer: 'object',
      sprite: 'alarm.png', glyph: 'A',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y, def: 'alarm:inert' });
        fx.push({ type: 'incCounter', key: 'alarm:rings', by: 1 });
        for (const c of roomCells(state, cell.x, cell.y)) {
          if (state.objects[c.y][c.x] === 'alarm:sleeper-asleep') {
            fx.push({ type: 'setObject', x: c.x, y: c.y, def: 'alarm:sleeper-awake' });
          }
        }
      } });
    api.defineTile('alarm:inert', { layer: 'object',
      sprite: 'alarm-inert.png', glyph: 'a' });
    api.defineTile('alarm:sleeper-asleep', { layer: 'object', glyph: 'S',
      blocks: function () { return true; } });
    api.defineTile('alarm:sleeper-awake', { layer: 'object', glyph: 'E',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
      } });
    api.onLevelLoad(function (state) {
      state.chars.object['alarm:tile'] = 'A';
      state.chars.object['alarm:inert'] = 'a';
      state.chars.object['alarm:sleeper-asleep'] = 'S';
      state.chars.object['alarm:sleeper-awake'] = 'E';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerAlarmPack;
  }
  root.GamePackAlarm = registerAlarmPack;
})(typeof window !== 'undefined' ? window : globalThis);
