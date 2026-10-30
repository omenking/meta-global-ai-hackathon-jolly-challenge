// Deterministic kernel: layered grid, generic state containers and
// the fixed step pipeline. Knows no specific tile, item or mechanic:
// every rule arrives through registry definitions and pack hooks.
// State advances only via step(state, input{t_ms}); rendering is a
// view of state. UMD like game-hud.js.
(function (root) {
  'use strict';
  const DIRECTIONS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 },
    left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
  const DEFAULT_TIME_LIMIT_S = 120;
  const INVENTORY_CAP = 8;

  function cloneState(s) {
    return { v: 2, level: s.level, width: s.width, height: s.height,
      terrain: s.terrain.map((r) => r.slice()), objects: s.objects.map((r) => r.slice()),
      meta: JSON.parse(JSON.stringify(s.meta || {})), links: JSON.parse(JSON.stringify(s.links || {})),
      chars: JSON.parse(JSON.stringify(s.chars)), spawn: { x: s.spawn.x, y: s.spawn.y },
      actors: s.actors.map((a) => ({ id: a.id, def: a.def, x: a.x, y: a.y,
        dir: a.dir, flags: Object.assign({}, a.flags) })),
      inventory: (s.inventory || []).map((e) => ({ item: e.item })),
      counters: Object.assign({}, s.counters), flags: Object.assign({}, s.flags),
      steps: s.steps, t_ms: s.t_ms, elapsed_s: s.elapsed_s,
      time_limit_s: s.time_limit_s, time_left_s: s.time_left_s,
      status: s.status, next_level: s.next_level, last_input: s.last_input,
      last_effects: [] };
  }
  function key(x, y) { return x + ',' + y; }
  function cellMeta(state, x, y) {
    return state.meta[key(x, y)] || {};
  }

  function createKernel(registry) {
    function tileAt(state, layer, x, y) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) return null;
      const id = state[layer][y][x];
      return id ? registry.getTile(id) : null;
    }
    function resolveDef(level, ch) {
      const legend = level.legend || {};
      const e = legend[ch] || {};
      if (e.def) return e.def;
      for (const fn of registry._levelDefHooks) {
        const id = fn(level, ch, e);
        if (id) return id;
      }
      return null;
    }
    function initialState(level, levelName) {
      const rows = (level && level.rows) || [];
      for (const fn of registry._levelDefHooks) fn(level, null, null);
      const height = rows.length, width = height ? rows[0].length : 0;
      const terrain = [], objects = [], links = {}, chars = { terrain: {}, object: {} };
      const spawns = [];
      let spawn = { x: 0, y: 0 };
      for (let y = 0; y < height; y++) {
        terrain.push([]); objects.push([]);
        for (let x = 0; x < width; x++) {
          const ch = rows[y][x];
          const legendEntry = level.legend && level.legend[ch];
          if (legendEntry && legendEntry.actor) {
            // Generic actor spawn (monsters etc.): floor underneath.
            const terrId = legendEntry.terrain || 'core:floor';
            terrain[y].push(terrId); objects[y].push(null);
            chars.terrain[terrId] = chars.terrain[terrId] || '.';
            spawns.push({ id: 'actor-' + spawns.length, def: legendEntry.actor,
              x: x, y: y, dir: 'right', flags: { dir: 'right' } });
            continue;
          }
          let defId = resolveDef(level, ch);
          if (!defId) defId = 'core:unknown';
          let def = registry.getTile(defId);
          if (!def) throw new Error('unregistered tile def ' + defId);
          if (defId === 'core:spawn' || (level.legend && level.legend[ch] && level.legend[ch].spawn)) {
            spawn = { x: x, y: y };
            defId = (level.legend && level.legend[ch] && level.legend[ch].terrain) || 'core:floor';
            def = registry.getTile(defId);
            terrain[y].push(defId); objects[y].push(null);
            chars.terrain[defId] = chars.terrain[defId] || '.';
            continue;
          }
          if (def.layer === 'terrain') {
            terrain[y].push(defId); objects[y].push(null);
            chars.terrain[defId] = chars.terrain[defId] || ch;
          } else {
            const terrId = (level.legend && level.legend[ch] && level.legend[ch].terrain) || 'core:floor';
            terrain[y].push(terrId); objects[y].push(defId);
            chars.terrain[terrId] = chars.terrain[terrId] || '.';
            chars.object[defId] = chars.object[defId] || ch;
            const link = level.legend && level.legend[ch] && level.legend[ch].link;
            if (link) (links[link] = links[link] || []).push({ x: x, y: y });
          }
        }
      }
      const limit = (level && typeof level.time_limit === 'number')
        ? level.time_limit : DEFAULT_TIME_LIMIT_S;
      const state = { v: 2, level: levelName || (level && level.name) || '',
        width: width, height: height, terrain: terrain, objects: objects,
        meta: {}, links: links, chars: chars, spawn: spawn,
        actors: [{ id: 'player', def: 'core:player', x: spawn.x, y: spawn.y,
          dir: null, flags: {} }].concat(spawns),
        inventory: [], counters: {}, flags: {}, steps: 0, t_ms: 0, elapsed_s: 0,
        time_limit_s: limit, time_left_s: limit, status: 'playing',
        next_level: (level && typeof level.next === 'string' && level.next) ? level.next : null,
        last_input: null, last_effects: [] };
      for (const fn of registry._levelHooks) fn(state, level);
      return state;
    }

    function hasItem(state, itemId) {
      return (state.inventory || []).some((e) => e.item === itemId);
    }
    function canEnter(state, actor, x, y) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) return false;
      const terr = tileAt(state, 'terrain', x, y);
      if (terr && terr.blocks && terr.blocks(state,
        { x: x, y: y, def: terr, meta: cellMeta(state, x, y) }, actor)) return false;
      const obj = tileAt(state, 'objects', x, y);
      if (obj && obj.blocks && obj.blocks(state,
        { x: x, y: y, def: obj, meta: cellMeta(state, x, y) }, actor)) return false;
      return true;
    }
    function applyEffects(state, effects) {
      let win = false, lose = false;
      for (const fx of effects || []) {
        state.last_effects.push(fx.type);
        if (fx.type === 'removeObject') state.objects[fx.y][fx.x] = null;
        else if (fx.type === 'setObject') state.objects[fx.y][fx.x] = fx.def;
        else if (fx.type === 'giveItem') {
          if (state.inventory.length < INVENTORY_CAP) state.inventory.push({ item: fx.item });
        } else if (fx.type === 'consumeItem') {
          const i = state.inventory.findIndex((e) => e.item === fx.item);
          if (i >= 0) state.inventory.splice(i, 1);
        } else if (fx.type === 'incCounter') {
          state.counters[fx.key] = (state.counters[fx.key] || 0) + (fx.by || 0);
        } else if (fx.type === 'setMeta') {
          const k = key(fx.x, fx.y);
          state.meta[k] = Object.assign({}, state.meta[k]);
          state.meta[k][fx.key] = fx.value;
        } else if (fx.type === 'teleport') {
          const a = state.actors.find((ac) => ac.id === fx.actor);
          if (a) { a.x = fx.x; a.y = fx.y; }
        } else if (fx.type === 'win') win = true;
        else if (fx.type === 'lose') lose = true;
      }
      return { win: win, lose: lose };
    }

    // One voluntary/forced move attempt; returns entered cell or null.
    function tryMove(state, actor, dirName) {
      const d = DIRECTIONS[dirName];
      if (!d) return null;
      const nx = actor.x + d.x, ny = actor.y + d.y;
      if (!canEnter(state, actor, nx, ny)) return null;
      actor.x = nx; actor.y = ny; actor.dir = dirName;
      return { x: nx, y: ny };
    }

    function step(state, input) {
      if (!state || typeof state !== 'object') throw new Error('step needs a state object');
      if (!input || typeof input.t_ms !== 'number' || !(input.t_ms >= 0)) {
        throw new Error('input must carry a non-negative t_ms');
      }
      if (input.t_ms < state.t_ms) throw new Error('input t_ms must not go backwards');
      const next = cloneState(state);
      const elapsed = input.t_ms / 1000;
      next.t_ms = input.t_ms; next.elapsed_s = elapsed;
      next.time_left_s = next.time_limit_s === null ? null
        : Math.max(0, next.time_limit_s - elapsed);
      next.steps = state.steps + 1;
      next.last_input = input.input === undefined ? null : input.input;
      const expired = next.time_limit_s !== null && next.time_limit_s !== undefined
        && elapsed >= next.time_limit_s;
      const finished = state.status === 'won' || state.status === 'lost';
      if (finished) return next;
      if (expired) {
        // Kernel owns the clock only; whether expiry loses is a pack
        // rule delivered through tick hooks (core pack: lose).
        const tickFx = [];
        for (const fn of registry._tickHooks) fn(next, tickFx);
        const v = applyEffects(next, tickFx);
        if (v.lose) next.status = 'lost';
        return next;
      }

      const effects = [];
      const player = next.actors.find((a) => a.id === 'player') || next.actors[0];
      // Phase 2 intent + phase 3 move (player from input; other actors
      // via registered deterministic controllers).
      const intents = [];
      if (player && DIRECTIONS[input.input]) intents.push({ actor: player, dir: input.input });
      for (const actor of next.actors) {
        if (player && actor.id === player.id) continue;
        const ctrl = registry.getController(actor.def);
        if (ctrl) { const dir = ctrl(next, actor); if (dir) intents.push({ actor: actor, dir: dir }); }
      }
      // Terrain/object phases below are scoped to the player actor;
      // other actors move in phase 3 only (contact rules are pack
      // tick hooks). Track the player's cells separately.
      let entered = null, vacated = null;
      for (const intent of intents) {
        const from = { x: intent.actor.x, y: intent.actor.y };
        const dest = tryMove(next, intent.actor, intent.dir);
        if (dest && player && intent.actor.id === player.id) {
          vacated = from; entered = dest;
        }
      }
      // Phase 4 terrain effects (forced moves, bounded chain).
      let actor = player;
      if (entered && actor) {
        let guard = next.width * next.height + 1;
        let cur = entered;
        while (cur && guard-- > 0) {
          const terr = tileAt(next, 'terrain', cur.x, cur.y);
          if (!terr || !terr.onEnterTerrain) break;
          const forced = terr.onEnterTerrain(next,
            { x: cur.x, y: cur.y, def: terr, meta: cellMeta(next, cur.x, cur.y) }, actor, effects);
          if (!forced) break;
          cur = tryMove(next, actor, forced);
          if (cur) entered = cur;
        }
      }
      // Phase 5 object interaction.
      if (entered && actor) {
        const obj = tileAt(next, 'objects', entered.x, entered.y);
        if (obj && obj.onEnter) obj.onEnter(next,
          { x: entered.x, y: entered.y, def: obj, meta: cellMeta(next, entered.x, entered.y) },
          actor, effects);
      }
      if (vacated && actor && (!entered || vacated.x !== actor.x || vacated.y !== actor.y)) {
        const prev = tileAt(next, 'objects', vacated.x, vacated.y);
        if (prev && prev.onExit) prev.onExit(next,
          { x: vacated.x, y: vacated.y, def: prev, meta: cellMeta(next, vacated.x, vacated.y) },
          actor, effects);
      }
      // Phase 6 effects + phase 7 tick hooks.
      let verdict = applyEffects(next, effects);
      const tickFx = [];
      for (const fn of registry._tickHooks) fn(next, tickFx);
      const tickVerdict = applyEffects(next, tickFx);
      verdict = { win: verdict.win || tickVerdict.win, lose: verdict.lose || tickVerdict.lose };
      // Phase 8 arbitration: lose wins unless already won previously.
      if (verdict.lose) next.status = 'lost';
      else if (verdict.win) next.status = 'won';
      return next;
    }

    function replay(level, levelName, log) {
      let s = initialState(level, levelName);
      const states = [s];
      for (const input of log || []) { s = step(s, input); states.push(s); }
      return states;
    }
    return { initialState: initialState, step: step, replay: replay,
      tileAt: tileAt, hasItem: hasItem, canEnter: canEnter,
      DIRECTIONS: DIRECTIONS, DEFAULT_TIME_LIMIT_S: DEFAULT_TIME_LIMIT_S,
      INVENTORY_CAP: INVENTORY_CAP };
  }
  const api = { createKernel: createKernel, DIRECTIONS: DIRECTIONS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameKernel = api;
})(typeof window !== 'undefined' ? window : globalThis);
