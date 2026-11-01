// Pack: floor switch (mech-21-floor-switch sanity check).
// A floor switch plate (terrain) holds its linked door open only
// while occupied: the door is open while you, a bot (any non-player
// actor) or a push block (blocks:push-block, mechanic 81) stands on
// a linked plate. Step off and it closes on the next move: the open
// flag survives the step-off move itself and clears at the end of
// the following move, so hurrying from a far plate arrives after it
// has closed, while stepping off a plate beside the door carries
// you through. The flag lives in state.flags and is advanced only
// by the pack tick hook inside the pure step function; no rule
// reads wall-clock. Restart restores the closed door because a
// fresh initialState rebuilds the room. Per-cell meta
// (switch_pressed / switch_open) is a view of that flag state for
// rendering and tests, never a driver of it.
// UMD: browser global GamePackFloorSwitch + Node export (register fn).
(function (root) {
  'use strict';
  function cellOccupied(state, x, y) {
    if (state.actors.some((a) => a.x === x && a.y === y)) return true;
    // A push block left on the plate holds it exactly as an actor
    // does (mechanic 81; the check is a pure read of the object
    // grid, so it composes when that pack is present).
    return state.objects[y][x] === 'blocks:push-block';
  }
  function linkOpen(state, link) {
    return !!(state.flags && state.flags['switch:open:' + link]);
  }
  function registerFloorSwitchPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image (Muse Image), one file per YAML asset entry.
    for (const name of ['floor-switch-unpressed.png',
      'floor-switch-pressed.png', 'door-closed.png', 'door-open.png',
      'jolly-on-plate.png', 'push-block.png']) {
      api.defineAsset(name, { pack: 'floor-switch', bundled: true });
    }
    api.defineTile('switch:plate', { layer: 'terrain',
      sprite: 'floor-switch-unpressed.png', glyph: 'S' });
    api.defineTile('switch:door', { layer: 'object',
      sprite: 'door-closed.png', glyph: 'D',
      blocks: function (state, cell) {
        const map = (state.meta && state.meta['switch:doorlink']) || {};
        const link = map[cell.x + ',' + cell.y];
        if (!link) return true;
        return !linkOpen(state, link);
      } });
    api.onLevelLoad(function (state, level) {
      const legend = (level && level.legend) || {};
      const rows = (level && level.rows) || [];
      const links = {}, doorlink = {};
      for (const ch of Object.keys(legend)) {
        const e = legend[ch] || {};
        if (!e.link) continue;
        if (e.def !== 'switch:plate' && e.def !== 'switch:door') continue;
        const entry = links[e.link] || (links[e.link] = { plates: [], doors: [] });
        for (let y = 0; y < rows.length; y++) {
          for (let x = 0; x < rows[y].length; x++) {
            if (rows[y][x] !== ch) continue;
            if (e.def === 'switch:plate') entry.plates.push([x, y]);
            else { entry.doors.push([x, y]); doorlink[x + ',' + y] = e.link; }
          }
        }
      }
      if (!Object.keys(links).length) return;
      state.meta['switch:links'] = links;
      state.meta['switch:doorlink'] = doorlink;
      for (const link of Object.keys(links)) {
        state.flags['switch:open:' + link] = false;
        state.flags['switch:occ:' + link] = false;
        for (const [x, y] of links[link].plates) {
          state.meta[x + ',' + y] = { switch_pressed: false };
        }
        for (const [x, y] of links[link].doors) {
          state.meta[x + ',' + y] = { switch_open: false };
        }
      }
    });
    api.onTick(function (state, fx) {
      const links = (state.meta && state.meta['switch:links']) || {};
      for (const link of Object.keys(links)) {
        const entry = links[link];
        const occupied = entry.plates.some(([x, y]) => cellOccupied(state, x, y));
        // Held while occupied; stepping off closes it on the next
        // move, not in the same step off it.
        const open = occupied || !!state.flags['switch:occ:' + link];
        state.flags['switch:open:' + link] = open;
        state.flags['switch:occ:' + link] = occupied;
        for (const [x, y] of entry.plates) {
          fx.push({ type: 'setMeta', x: x, y: y,
            key: 'switch_pressed', value: cellOccupied(state, x, y) });
        }
        for (const [x, y] of entry.doors) {
          fx.push({ type: 'setMeta', x: x, y: y,
            key: 'switch_open', value: open });
        }
      }
    });
    // Render/readout helper: true while the named link's door is
    // held open. Pure read of state, never a driver of it.
    api.floorSwitchDoorOpen = linkOpen;
  }
  registerFloorSwitchPack.doorOpen = linkOpen;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerFloorSwitchPack;
  }
  root.GamePackFloorSwitch = registerFloorSwitchPack;
})(typeof window !== 'undefined' ? window : globalThis);
