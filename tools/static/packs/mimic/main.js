// Pack: mimic orb (mech-36-mimic-orb sanity check).
// A mimic orb is identical to a real orb until the player comes
// within one tile (Manhattan distance <= 1), when it reveals and
// starts a small three-tile vertical patrol (anchor, anchor+1,
// anchor+2, ping-pong), lethal on touch. Before it reveals,
// stepping on it collects nothing: its onEnter is deliberately
// empty and it never counts toward core:orbs_left. The reveal
// and the patrol advance only in the tick hook of the pure step
// function; no rule reads wall-clock time. Restart restores the
// disguise because a fresh initialState rebuilds the room.
// UMD: browser global GamePackMimic + Node export (register fn).
(function (root) {
  'use strict';
  var SPAN = 2; // patrol offsets 0..2: a three-tile patrol
  function registerMimicPack(api) {
    for (const name of ['mimic-orb.png', 'mimic-revealed.png']) {
      api.defineAsset(name, { pack: 'mimic', bundled: true });
    }
    api.defineTile('mimic:orb', { layer: 'object',
      sprite: 'mimic-orb.png', glyph: 'M',
      // Before reveal, stepping on it collects nothing.
      onEnter: function (state, cell, actor, fx) {} });
    api.defineTile('mimic:revealed', { layer: 'object',
      sprite: 'mimic-revealed.png', glyph: 'N',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
      } });
    api.onLevelLoad(function (state) {
      state.chars.object['mimic:orb'] = 'M';
      state.chars.object['mimic:revealed'] = 'N';
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          if (state.objects[y][x] === 'mimic:orb') {
            state.meta[x + ',' + y] = { mimic_ax: x, mimic_ay: y,
              mimic_off: 0, mimic_dir: 1, mimic_revealed: false };
          }
        }
      }
    });
    api.onTick(function (state, fx) {
      const player = state.actors.find((a) => a.id === 'player')
        || state.actors[0];
      if (!player) return;
      const mimics = [];
      for (let y = 0; y < state.height; y++) {
        for (let x = 0; x < state.width; x++) {
          const id = state.objects[y][x];
          if (id === 'mimic:orb' || id === 'mimic:revealed') {
            mimics.push({ x: x, y: y, id: id,
              meta: state.meta[x + ',' + y] || {} });
          }
        }
      }
      for (const m of mimics) {
        const dist = Math.abs(player.x - m.x) + Math.abs(player.y - m.y);
        if (m.id === 'mimic:orb') {
          // Reveals exactly when the player first comes within
          // one tile, never earlier.
          if (dist <= 1) {
            fx.push({ type: 'setObject', x: m.x, y: m.y,
              def: 'mimic:revealed' });
            fx.push({ type: 'setMeta', x: m.x, y: m.y,
              key: 'mimic_revealed', value: true });
            // Revealing under the player's feet is a touch.
            if (dist === 0) fx.push({ type: 'lose' });
          }
          continue;
        }
        // Revealed: lethal on touch, checked before and after
        // this step's patrol move.
        if (dist === 0) { fx.push({ type: 'lose' }); continue; }
        const ax = typeof m.meta.mimic_ax === 'number' ? m.meta.mimic_ax : m.x;
        const ay = typeof m.meta.mimic_ay === 'number' ? m.meta.mimic_ay : m.y;
        let off = typeof m.meta.mimic_off === 'number' ? m.meta.mimic_off : 0;
        let dir = m.meta.mimic_dir === -1 ? -1 : 1;
        let nextOff = off + dir;
        if (nextOff > SPAN || nextOff < 0) { dir = -dir; nextOff = off + dir; }
        const tx = ax, ty = ay + nextOff;
        const blocked = tx < 0 || ty < 0 || tx >= state.width
          || ty >= state.height
          || state.terrain[ty][tx] === 'core:wall'
          || (state.objects[ty][tx] && !(tx === m.x && ty === m.y));
        if (blocked) {
          dir = -dir; nextOff = off + dir;
          if (nextOff < 0 || nextOff > SPAN) continue;
        }
        const nx = ax, ny = ay + nextOff;
        if (state.objects[ny][nx] && !(nx === m.x && ny === m.y)) continue;
        fx.push({ type: 'setObject', x: m.x, y: m.y, def: null });
        fx.push({ type: 'setObject', x: nx, y: ny, def: 'mimic:revealed' });
        fx.push({ type: 'setMeta', x: nx, y: ny, key: 'mimic_ax', value: ax });
        fx.push({ type: 'setMeta', x: nx, y: ny, key: 'mimic_ay', value: ay });
        fx.push({ type: 'setMeta', x: nx, y: ny, key: 'mimic_off', value: nextOff });
        fx.push({ type: 'setMeta', x: nx, y: ny, key: 'mimic_dir', value: dir });
        fx.push({ type: 'setMeta', x: nx, y: ny, key: 'mimic_revealed', value: true });
        if (player.x === nx && player.y === ny) fx.push({ type: 'lose' });
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMimicPack;
  }
  root.GamePackMimic = registerMimicPack;
})(typeof window !== 'undefined' ? window : globalThis);
