// Pack: info tile (mech-58-info-tile sanity check).
// Stepping on the marked tile shows a one-line banner teaching
// the next mechanic in the level and does nothing else: it never
// blocks movement, collects nothing and opens nothing. Each tile
// triggers once per attempt: the first step records the banner
// (counter info:shown, cell meta info_read) and swaps the tile to
// its spent, still-walkable form; later steps are plain floor
// crossings. The banner line itself is level data (the legend
// entry's banner text), stamped into cell meta at load so the
// renderer and tests read it from state, never from the clock.
// All state advances through the pure step function; restart
// restores the untriggered tile because a fresh initialState
// rebuilds the room. UMD: browser global GamePackInfoTile +
// Node export (register fn).
(function (root) {
  'use strict';
  function registerInfoTilePack(api) {
    // Bundled assets (see manifest.json): real generated art.
    for (const name of ['info.png', 'info-read.png', 'info-banner.png']) {
      api.defineAsset(name, { pack: 'info-tile', bundled: true });
    }
    api.defineTile('info:tile', { layer: 'object',
      sprite: 'info.png', glyph: '?',
      onEnter: function (state, cell, actor, fx) {
        if (cell.meta && cell.meta.info_read) return;
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'info_read', value: 1 });
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'info:tile-read' });
        fx.push({ type: 'incCounter', key: 'info:shown', by: 1 });
      } });
    api.defineTile('info:tile-read', { layer: 'object',
      sprite: 'info-read.png', glyph: '?',
      // Spent for this attempt and still walkable: no onEnter,
      // no blocks, so crossing it again is plain floor movement.
      });
    // The spent tile never appears in level rows, so give its
    // projected grid char a name here (same char as the fresh
    // tile; the spent look follows the cell meta, like crumbling).
    // Also stamp each tile's banner line into its cell meta.
    api.onLevelLoad(function (state, level) {
      state.chars.object['info:tile-read'] = 'i';
      if (typeof state.counters['info:shown'] !== 'number') {
        state.counters['info:shown'] = 0;
      }
      const legend = (level && level.legend) || {};
      let banner = '';
      for (const ch of Object.keys(legend)) {
        const e = legend[ch] || {};
        if (e.def === 'info:tile' && e.banner) { banner = e.banner; break; }
      }
      if (!banner) return;
      state.flags['info:banner'] = banner;
      for (let y = 0; y < state.objects.length; y++) {
        for (let x = 0; x < state.objects[y].length; x++) {
          if (state.objects[y][x] === 'info:tile') {
            const k = x + ',' + y;
            state.meta[k] = Object.assign({}, state.meta[k],
              { banner: banner });
          }
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerInfoTilePack;
  }
  root.GamePackInfoTile = registerInfoTilePack;
})(typeof window !== 'undefined' ? window : globalThis);
