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

  function charAt(grid, x, y) {
    if (!Array.isArray(grid) || y < 0 || y >= grid.length) return null;
    const row = grid[y];
    if (typeof row !== 'string' || x < 0 || x >= row.length) return null;
    return row[x];
  }

  function setTile(grid, x, y, ch) {
    const next = (grid || []).slice();
    if (y < 0 || y >= next.length) return next;
    const row = next[y];
    next[y] = row.slice(0, x) + ch + row.slice(x + 1);
    return next;
  }

  // Key/lock colours come from the level legend (key_color /
  // lock_color per tile char), so mechanics are data-driven.
  function tileMaps(level) {
    const keyTiles = {}, lockTiles = {};
    const legend = (level && level.legend) || {};
    for (const ch of Object.keys(legend)) {
      const e = legend[ch] || {};
      if (e.key_color) keyTiles[ch] = e.key_color;
      if (e.lock_color) lockTiles[ch] = e.lock_color;
    }
    return { keyTiles: keyTiles, lockTiles: lockTiles };
  }

  // Resolve one directional press into player/grid/inventory.
  // Walking onto a key moves the player, appends its colour to the
  // inventory in held order and turns the tile to floor.
  function resolveMove(state, inputName) {
    const stay = { player: { x: state.player.x, y: state.player.y },
      grid: state.grid, inventory: (state.inventory || []).slice() };
    const delta = DIRECTIONS[inputName];
    if (!delta) return stay;
    const nx = state.player.x + delta.x;
    const ny = state.player.y + delta.y;
    const ch = charAt(state.grid, nx, ny);
    if (ch === null) return stay;
    const keyColor = (state.key_tiles || {})[ch];
    if (keyColor) {
      // Full inventory (8): the key stays on the floor and the
      // player does not step onto it.
      if (stay.inventory.length >= 8) return stay;
      return { player: { x: nx, y: ny },
        grid: setTile(state.grid, nx, ny, '.'),
        inventory: stay.inventory.concat([keyColor]) };
    }
    if (isWalkable(state.grid, nx, ny)) {
      return { player: { x: nx, y: ny }, grid: state.grid,
        inventory: stay.inventory };
    }
    return stay;
  }

  function movePlayer(state, inputName) {
    return resolveMove(state, inputName).player;
  }

  // Countdown timer: scoped by its max time. A level may set
  // time_limit (seconds); when absent the fixed default is 2 minutes.
  const DEFAULT_TIME_LIMIT_S = 120;
  function initialState(level, levelName) {
    const limit = (level && typeof level.time_limit === 'number')
      ? level.time_limit : DEFAULT_TIME_LIMIT_S;
    const maps = tileMaps(level || {});
    return {
      level: levelName || (level && level.name) || '',
      grid: ((level && level.rows) || []).slice(),
      inventory: [],
      key_tiles: maps.keyTiles,
      lock_tiles: maps.lockTiles,
      player: findPlayer(level || {}),
      steps: 0,
      t_ms: 0,
      elapsed_s: 0,
      time_limit_s: limit,
      time_left_s: limit,
      status: 'playing',
      last_input: null,
    };
  }

  // The run is lost the moment recorded elapsed time reaches the
  // limit. Expiry is a pure function of t_ms, so a timeout loss
  // replays as a loss at exactly the same recorded moment.
  function isLost(state) {
    return !!state && state.status === 'lost';
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
    const expired = state.time_limit_s !== null &&
      state.time_limit_s !== undefined && elapsed >= state.time_limit_s;
    const lost = expired || state.status === 'lost';
    // No movement on or after expiry, and a lost run stays frozen.
    const moved = lost
      ? { player: { x: state.player.x, y: state.player.y },
          grid: state.grid, inventory: (state.inventory || []).slice() }
      : resolveMove(state, input.input);
    return {
      level: state.level,
      grid: moved.grid,
      inventory: moved.inventory,
      key_tiles: state.key_tiles || {},
      lock_tiles: state.lock_tiles || {},
      player: moved.player,
      steps: state.steps + 1,
      t_ms: input.t_ms,
      elapsed_s: elapsed,
      time_limit_s: state.time_limit_s,
      time_left_s: state.time_limit_s === null
        ? null : Math.max(0, state.time_limit_s - elapsed),
      status: lost ? 'lost' : 'playing',
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

  const VERSION = 'game-core-1';
  function readout(state) {
    let orbs = 0;
    for (const row of state.grid || []) for (const ch of row) if (ch === '*' || ch === 'O') orbs++;
    return { step: state.steps, position: { x: state.player.x, y: state.player.y },
      inventory: (state.inventory || []).slice(),
      orbs_left: orbs, status: state.status || 'playing',
      timer: state.time_left_s === null ? state.elapsed_s : state.time_left_s,
      time_left_s: state.time_left_s,
      elapsed_s: state.elapsed_s, t_ms: state.t_ms, input: state.last_input };
  }
  const api = { findPlayer, initialState, step, replay, stateDigest,
    inputForKey, isWalkable, isLost, DIRECTIONS, VERSION, readout, DEFAULT_TIME_LIMIT_S };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameCore = api;
})(typeof window !== 'undefined' ? window : globalThis);
