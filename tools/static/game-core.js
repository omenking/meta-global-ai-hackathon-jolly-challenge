// Deterministic game core: a pure step function.
//
// State advances ONLY through step(state, input). Every input carries
// t_ms (elapsed ms since session start, as recorded in the session
// log), so the timer at any step is a function of the recorded log —
// never of an unrecorded wall-clock read. Replaying the same initial
// level with the same ordered, timestamped log always yields the same
// states. Rendering is a view of state, never a driver of it.
//
// Movement (player-movement): a direction input moves the player
// exactly one tile when the target tile is walkable; otherwise the
// player stays. Only floor is walkable in this feature — the player
// start tile counts as floor; walls, locks, gates, orbs, keys and
// every other tile block until later features give them behaviour.
(function (root) {
  'use strict';

  function findPlayer(level) {
    const rows = (level && level.rows) || [];
    for (let y = 0; y < rows.length; y++) {
      const x = rows[y].indexOf('P');
      if (x >= 0) return { x: x, y: y };
    }
    return { x: 0, y: 0 };
  }

  const DIRECTIONS = {
    up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 },
  };

  // Only floor ('.') and the player start ('P', floor underneath) are
  // walkable; anything else — or off-grid — blocks movement.
  function isWalkable(grid, x, y) {
    if (!Array.isArray(grid) || y < 0 || y >= grid.length) return false;
    const row = grid[y];
    if (typeof row !== 'string' || x < 0 || x >= row.length) return false;
    const ch = row[x];
    return ch === '.' || ch === 'P';
  }

  function movePlayer(state, inputName) {
    const delta = DIRECTIONS[inputName];
    if (!delta) return { x: state.player.x, y: state.player.y };
    const nx = state.player.x + delta.x;
    const ny = state.player.y + delta.y;
    if (!isWalkable(state.grid, nx, ny)) {
      return { x: state.player.x, y: state.player.y };
    }
    return { x: nx, y: ny };
  }

  // time_limit (seconds) is optional in a level file; when absent the
  // clock counts up from zero and time_left stays null.
  function initialState(level, levelName) {
    const limit = (level && typeof level.time_limit === 'number')
      ? level.time_limit : null;
    return {
      level: levelName || (level && level.name) || '',
      grid: ((level && level.rows) || []).slice(),
      player: findPlayer(level || {}),
      steps: 0,
      t_ms: 0,
      elapsed_s: 0,
      time_limit_s: limit,
      time_left_s: limit,
      last_input: null,
    };
  }

  function step(state, input) {
    if (!state || typeof state !== 'object') {
      throw new Error('step needs a state object');
    }
    if (!input || typeof input.t_ms !== 'number' || !(input.t_ms >= 0)) {
      throw new Error('input must carry a non-negative t_ms');
    }
    if (input.t_ms < state.t_ms) {
      throw new Error('input t_ms must not go backwards');
    }
    const elapsed = input.t_ms / 1000;
    return {
      level: state.level,
      grid: state.grid,
      player: movePlayer(state, input.input),
      steps: state.steps + 1,
      t_ms: input.t_ms,
      elapsed_s: elapsed,
      time_limit_s: state.time_limit_s,
      time_left_s: state.time_limit_s === null
        ? null : Math.max(0, state.time_limit_s - elapsed),
      last_input: input.input === undefined ? null : input.input,
    };
  }

  function replay(level, levelName, log) {
    let state = initialState(level, levelName);
    const states = [state];
    for (const input of log || []) {
      state = step(state, input);
      states.push(state);
    }
    return states;
  }

  // Stable digest of a state, for replay comparison in the debug UI.
  function stateDigest(state) {
    const text = JSON.stringify(state);
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return ('0000000' + h.toString(16)).slice(-8);
  }

  const KEY_INPUTS = {
    w: 'up', arrowup: 'up',
    a: 'left', arrowleft: 'left',
    s: 'down', arrowdown: 'down',
    d: 'right', arrowright: 'right',
  };

  function inputForKey(key) {
    if (typeof key !== 'string') return null;
    return KEY_INPUTS[key.toLowerCase()] || null;
  }

  const api = { findPlayer, initialState, step, replay, stateDigest,
    inputForKey, isWalkable, DIRECTIONS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameCore = api;
})(typeof window !== 'undefined' ? window : globalThis);
