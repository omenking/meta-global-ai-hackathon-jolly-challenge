// Pack: power switches recipe (mech-91-power-switches-recipe).
// A level recipe, not a new object: any three wired switches — one
// floor switch (held while the player or a block stands on it, per
// mechanic 21), one weight switch (held only while a block sits on
// it, per mechanic 29) and one toggle switch (latches on each press,
// per mechanic 22) — drive one elevator gate. The HUD counter in
// state.counters['power:count'] runs 0/3 to 3/3 and the gate calls
// the elevator (opens) only while all three are on together; losing
// any one revokes the call. Push blocks (mechanic 81) hold the
// plates after the player leaves. The floor/toggle/weight/block
// packs are not on main, so this pack provides those switch tiles
// itself; counting reads only layered state (terrain/objects/
// actors) inside the pure step (onEnter, the push predicate on the
// kernel clone, and the tick hook), so no rule reads wall-clock and
// restart restores 0/3 because a fresh initialState rebuilds the
// room. UMD: browser global GamePackPowerSwitches + Node export.
(function (root) {
  'use strict';
  function switchCells(state) {
    return (state.meta && state.meta['power:switches']) || null;
  }
  function countOn(state) {
    const cells = switchCells(state);
    if (!cells) return 0;
    let n = 0;
    const f = cells.floor;
    if (f && (state.objects[f.y][f.x] === 'power:block'
        || state.actors.some((a) => a.x === f.x && a.y === f.y))) n++;
    const w = cells.weight;
    if (w && state.objects[w.y][w.x] === 'power:block') n++;
    const t = cells.toggle;
    if (t && state.objects[t.y][t.x] === 'power:toggle-on') n++;
    return n;
  }
  function registerPowerSwitchesPack(api) {
    for (const name of ['power-counter-0.png', 'power-counter-1.png',
      'power-counter-2.png', 'power-counter-3.png']) {
      api.defineAsset(name, { pack: 'power-switches', bundled: true });
    }
    api.defineTile('power:floor-plate', { layer: 'terrain', glyph: 'F' });
    api.defineTile('power:weight-plate', { layer: 'terrain', glyph: 'W' });
    api.defineTile('power:toggle-off', { layer: 'object', glyph: 'T',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'power:toggle-on' });
      } });
    api.defineTile('power:toggle-on', { layer: 'object', glyph: 'T',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'power:toggle-off' });
      } });
    api.defineTile('power:block', { layer: 'object', glyph: 'B',
      blocks: function (state, cell, actor) {
        if (!actor || actor.id !== 'player') return true;
        const dx = cell.x - actor.x, dy = cell.y - actor.y;
        if (Math.abs(dx) + Math.abs(dy) !== 1) return true;
        const bx = cell.x + dx, by = cell.y + dy;
        if (bx < 0 || by < 0 || bx >= state.width || by >= state.height) {
          return true;
        }
        if (state.objects[by][bx]) return true;
        if (state.actors.some((a) => a.id !== actor.id
            && a.x === bx && a.y === by)) return true;
        const terr = state.terrain[by][bx];
        if (terr !== 'core:floor' && terr !== 'core:spawn'
            && terr !== 'power:floor-plate'
            && terr !== 'power:weight-plate') return true;
        state.objects[cell.y][cell.x] = null;
        state.objects[by][bx] = 'power:block';
        return false;
      } });
    api.defineTile('power:elevator-gate', { layer: 'object', glyph: 'E',
      blocks: function (state) {
        return (state.counters['power:count'] || 0) < 3;
      } });
    api.onLevelLoad(function (state, level) {
      const legend = (level && level.legend) || {};
      const rows = (level && level.rows) || [];
      const cells = {};
      for (const ch of Object.keys(legend)) {
        const e = legend[ch] || {};
        let key = null;
        if (e.def === 'power:floor-plate') key = 'floor';
        else if (e.def === 'power:weight-plate') key = 'weight';
        else if (e.def === 'power:toggle-off'
            || e.def === 'power:toggle-on') key = 'toggle';
        else if (e.def === 'power:elevator-gate') key = 'gate';
        if (!key) continue;
        for (let y = 0; y < rows.length; y++) {
          const x = rows[y].indexOf(ch);
          if (x >= 0) cells[key] = { x: x, y: y };
        }
      }
      if (!cells.floor && !cells.weight && !cells.toggle) return;
      state.meta['power:switches'] = cells;
      state.counters['power:count'] = 0;
      state.flags['power:called'] = false;
      for (const key of ['floor', 'weight', 'toggle', 'gate']) {
        const c = cells[key];
        if (c) {
          state.meta[c.x + ',' + c.y] = Object.assign(
            {}, state.meta[c.x + ',' + c.y], { power_on: false });
        }
      }
      state.chars.object['power:toggle-off'] = 'T';
      state.chars.object['power:toggle-on'] = 'T';
      state.chars.object['power:block'] = 'B';
      state.chars.object['power:elevator-gate'] = 'E';
    });
    api.onTick(function (state, fx) {
      const cells = switchCells(state);
      if (!cells) return;
      const count = countOn(state);
      state.counters['power:count'] = count;
      state.flags['power:called'] = count === 3;
      const marks = [
        ['floor', cells.floor && (state.objects[cells.floor.y][cells.floor.x] === 'power:block'
          || state.actors.some((a) => a.x === cells.floor.x && a.y === cells.floor.y))],
        ['weight', cells.weight && state.objects[cells.weight.y][cells.weight.x] === 'power:block'],
        ['toggle', cells.toggle && state.objects[cells.toggle.y][cells.toggle.x] === 'power:toggle-on'],
        ['gate', count === 3],
      ];
      for (const [key, on] of marks) {
        const c = cells[key];
        if (c) fx.push({ type: 'setMeta', x: c.x, y: c.y,
          key: 'power_on', value: !!on });
      }
    });
  }
  registerPowerSwitchesPack.countOn = countOn;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerPowerSwitchesPack;
  }
  root.GamePackPowerSwitches = registerPowerSwitchesPack;
})(typeof window !== 'undefined' ? window : globalThis);
