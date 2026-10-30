// GameCore facade: assembles registry + kernel + packs and keeps the
// long-standing public API (initialState/step/replay/stateDigest/
// readout/inputForKey + legacy char helpers for tests and game.js).
// Mechanics live in packs under tools/static/packs/ (core-chips,
// keys-locks, proof-water). The kernel in
// engine/kernel.js knows no specific tile. State is v2 layered data
// plus a derived compatibility projection (grid/player/orbs_left/
// gate_open) computed here, never stored as kernel truth.
(function (root) {
  'use strict';
  let Registry, Kernel, KeysPack, CorePack, WaterPack, ButtonsPack, IcePack, MonstersPack;
  if (typeof module !== 'undefined' && module.exports) {
    Registry = require('./engine/registry.js');
    Kernel = require('./engine/kernel.js');
    KeysPack = require('./packs/keys-locks.js');
    CorePack = require('./packs/core-chips.js');
    WaterPack = require('./packs/proof-water.js');
    ButtonsPack = require('./packs/buttons-traps.js');
    IcePack = require('./packs/ice-force.js');
    MonstersPack = require('./packs/monsters.js');
  } else {
    Registry = root.GameRegistry; Kernel = root.GameKernel;
    KeysPack = root.GamePackKeysLocks;
    CorePack = root.GamePackCoreChips;
    WaterPack = root.GamePackProofWater;
    ButtonsPack = root.GamePackButtonsTraps;
    IcePack = root.GamePackIceForce;
    MonstersPack = root.GamePackMonsters;
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

  const engine = createEngine([CorePack, KeysPack, WaterPack, ButtonsPack, IcePack, MonstersPack]);

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
    registerCorePack: CorePack, registerKeysPack: KeysPack,
    registerWaterPack: WaterPack, registerButtonsTrapsPack: ButtonsPack,
    registerIceForcePack: IcePack, registerMonstersPack: MonstersPack,
    registry: engine.registry, kernel: engine.kernel };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameCore = api;
})(typeof window !== 'undefined' ? window : globalThis);
