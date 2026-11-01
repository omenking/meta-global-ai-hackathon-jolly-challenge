// Pack: sand tile (mech-45-sand-tile sanity check).
// Walking on sand leaves footprints that persist for the rest of
// the attempt so the player can retrace their route. Sand never
// slows the player (one move per tile, like floor), enemies
// ignore sand prints (no controller reads them; scent tracking
// is mud's job, mech 47), and restart clears every print because
// a fresh initialState rebuilds meta. Prints are a boolean in
// cell meta set on entry via the pure step function; no rule
// reads wall-clock time.
// UMD: browser global GamePackSandTile + Node export (register fn).
(function (root) {
  'use strict';
  function registerSandPack(api) {
    for (const name of ['sand.png', 'sand-prints.png']) {
      api.defineAsset(name, { pack: 'sand-tile', bundled: true });
    }
    api.defineTile('sand:sand', { layer: 'terrain',
      sprite: 'sand.png', glyph: 'S',
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'sand_print', value: true });
        return null;
      } });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerSandPack;
  }
  root.GamePackSandTile = registerSandPack;
})(typeof window !== 'undefined' ? window : globalThis);
