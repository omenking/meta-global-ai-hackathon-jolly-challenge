// GameCore facade: assembles registry + kernel + packs and keeps the
// long-standing public API (initialState/step/replay/stateDigest/
// readout/inputForKey + legacy char helpers for tests and game.js).
// Mechanics live in packs (Phase 1: built-in registration below;
// extracted to tools/static/packs/ in Phases 2-3/5). The kernel in
// engine/kernel.js knows no specific tile. State is v2 layered data
// plus a derived compatibility projection (grid/player/orbs_left/
// gate_open) computed here, never stored as kernel truth.
(function (root) {
  'use strict';
  let Registry, Kernel;
  if (typeof module !== 'undefined' && module.exports) {
    Registry = require('./engine/registry.js');
    Kernel = require('./engine/kernel.js');
  } else {
    Registry = root.GameRegistry; Kernel = root.GameKernel;
  }

  // --- Built-in pack registration (extracted in later phases) ---
  function registerCorePack(api) {
    api.defineTile('core:floor', { layer: 'terrain', sprite: 'floor_default.png' });
    api.defineTile('core:spawn', { layer: 'terrain', sprite: 'floor_default.png' });
    api.defineTile('core:wall', { layer: 'terrain', sprite: 'wall.png',
      blocks: function () { return true; } });
    api.defineTile('core:info', { layer: 'terrain',
      blocks: function () { return true; } });
    api.defineTile('core:unknown', { layer: 'terrain',
      blocks: function () { return true; } });
    api.defineTile('core:orb', { layer: 'object', sprite: 'orb.png',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
        fx.push({ type: 'incCounter', key: 'core:orbs_left', by: -1 });
      } });
    api.defineTile('core:gate', { layer: 'object', sprite: 'gate.png',
      blocks: function (state) { return (state.counters['core:orbs_left'] || 0) > 0; } });
    api.defineTile('core:warp', { layer: 'object', sprite: 'portal.png',
      onEnter: function (state, cell, actor, fx) { fx.push({ type: 'win' }); } });
    api.onLevelLoad(function (state) {
      let n = 0;
      for (const row of state.objects) for (const id of row) if (id === 'core:orb') n++;
      state.counters['core:orbs_left'] = n;
    });
    api.onLevelDefs(function (level, ch, e) {
      if (!ch) return null;
      if (ch === '.') return 'core:floor';
      if (ch === '#') return 'core:wall';
      if (ch === 'P') return 'core:spawn';
      if (ch === '*' || ch === 'O') return 'core:orb';
      if (ch === 'G') return 'core:gate';
      if (ch === 'X') return 'core:warp';
      if (ch === '?') return 'core:info';
      return null;
    });
  }
  function registerKeysPack(api) {
    api.onLevelDefs(function (level, ch, e) {
      if (!ch || !e) return null;
      if (e.key_color) {
        const color = e.key_color, itemId = 'keys:key-' + color;
        api.defineItem(itemId, { icon: 'key_' + color + '.png', readout: color });
        api.defineTile(itemId, { layer: 'object', sprite: 'key_' + color + '.png',
          blocks: function (state) { return state.inventory.length >= 8; },
          onEnter: function (state, cell, actor, fx) {
            fx.push({ type: 'giveItem', item: itemId });
            fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          } });
        return itemId;
      }
      if (e.lock_color) {
        const color = e.lock_color, tileId = 'keys:lock-' + color,
          itemId = 'keys:key-' + color;
        api.defineTile(tileId, { layer: 'object', sprite: 'wall_keyhole_' + color + '.png',
          blocks: function (state) {
            return !state.inventory.some((en) => en.item === itemId);
          },
          onEnter: function (state, cell, actor, fx) {
            fx.push({ type: 'consumeItem', item: itemId });
            fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
          } });
        return tileId;
      }
      return null;
    });
  }

  function createEngine(packRegisters) {
    const registry = Registry.createRegistry();
    for (const fn of packRegisters) registry.registerPack(fn);
    const kernel = Kernel.createKernel(registry);
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
    function project(state, maps) {
      const player = state.actors.find((a) => a.id === 'player') || state.actors[0];
      const grid = [];
      for (let y = 0; y < state.height; y++) {
        let row = '';
        for (let x = 0; x < state.width; x++) {
          const obj = state.objects[y][x];
          if (obj) row += state.chars.object[obj] || '?';
          else if (x === state.spawn.x && y === state.spawn.y) row += 'P';
          else row += state.chars.terrain[state.terrain[y][x]] || '.';
        }
        grid.push(row);
      }
      const orbs = typeof state.counters['core:orbs_left'] === 'number'
        ? state.counters['core:orbs_left']
        : state.objects.flat().filter((id) => id === 'core:orb').length;
      return Object.assign({}, state, { grid: grid,
        player: player ? { x: player.x, y: player.y } : { x: 0, y: 0 },
        orbs_left: orbs, gate_open: orbs === 0,
        key_tiles: maps ? maps.keyTiles : (state.key_tiles || {}),
        lock_tiles: maps ? maps.lockTiles : (state.lock_tiles || {}) });
    }
    function initialState(level, levelName) {
      return project(kernel.initialState(level, levelName), tileMaps(level || {}));
    }
    function step(state, input) {
      const maps = { keyTiles: state.key_tiles || {}, lockTiles: state.lock_tiles || {} };
      return project(kernel.step(state, input), maps);
    }
    function replay(level, levelName, log) {
      let s = initialState(level, levelName);
      const states = [s];
      for (const input of log || []) { s = step(s, input); states.push(s); }
      return states;
    }
    function readout(state) {
      const inv = (state.inventory || []).map((e) => {
        if (typeof e === 'string') return e;
        const def = registry.getItem(e.item);
        return def && def.readout !== undefined ? def.readout : e.item;
      });
      const orbs = typeof state.orbs_left === 'number' ? state.orbs_left
        : (state.counters || {})['core:orbs_left'];
      return { step: state.steps, position: { x: state.player.x, y: state.player.y },
        inventory: inv, orbs_left: orbs, gate_open: orbs === 0,
        status: state.status || 'playing',
        next_level: state.next_level === undefined ? null : state.next_level,
        timer: state.time_left_s === null ? state.elapsed_s : state.time_left_s,
        time_left_s: state.time_left_s, elapsed_s: state.elapsed_s,
        t_ms: state.t_ms, input: state.last_input };
    }
    return { initialState: initialState, step: step, replay: replay,
      readout: readout, kernel: kernel, registry: registry };
  }

  const engine = createEngine([registerCorePack, registerKeysPack]);

  // --- Legacy char helpers (compatibility surface for tests/game.js) ---
  function findPlayer(level) {
    const rows = (level && level.rows) || [];
    for (let y = 0; y < rows.length; y++) {
      const x = rows[y].indexOf('P');
      if (x >= 0) return { x: x, y: y };
    }
    return { x: 0, y: 0 };
  }
  function isWalkable(grid, x, y) {
    if (!Array.isArray(grid) || y < 0 || y >= grid.length) return false;
    const row = grid[y];
    if (typeof row !== 'string' || x < 0 || x >= row.length) return false;
    const ch = row[x];
    return ch === '.' || ch === 'P';
  }
  function isOrb(ch) { return ch === '*' || ch === 'O'; }
  function isWarp(ch) { return ch === 'X'; }
  function countOrbs(grid) {
    let n = 0;
    for (const row of grid || []) for (const ch of row) if (isOrb(ch)) n++;
    return n;
  }
  function isLost(state) { return !!state && state.status === 'lost'; }
  function isWon(state) { return !!state && state.status === 'won'; }
  function stateDigest(state) {
    const text = JSON.stringify(state);
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return ('0000000' + h.toString(16)).slice(-8);
  }
  const KEY_INPUTS = { w: 'up', arrowup: 'up', a: 'left', arrowleft: 'left',
    s: 'down', arrowdown: 'down', d: 'right', arrowright: 'right' };
  function inputForKey(key) {
    if (typeof key !== 'string') return null;
    return KEY_INPUTS[key.toLowerCase()] || null;
  }
  const VERSION = 'game-core-2';
  const api = { findPlayer: findPlayer, initialState: engine.initialState,
    step: engine.step, replay: engine.replay, stateDigest: stateDigest,
    inputForKey: inputForKey, isWalkable: isWalkable, isLost: isLost,
    isWon: isWon, isOrb: isOrb, isWarp: isWarp, countOrbs: countOrbs,
    DIRECTIONS: Kernel.DIRECTIONS, VERSION: VERSION, readout: engine.readout,
    DEFAULT_TIME_LIMIT_S: 120, createEngine: createEngine,
    registerCorePack: registerCorePack, registerKeysPack: registerKeysPack,
    registry: engine.registry, kernel: engine.kernel };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameCore = api;
})(typeof window !== 'undefined' ? window : globalThis);
