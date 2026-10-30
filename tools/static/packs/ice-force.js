// Pack: ice and force floors (pressure test d).
// Terrain effects run in kernel pipeline phase 4 after the voluntary
// move: ice keeps the actor sliding along its entry direction, force
// floors convey along their fixed direction, chains bounded by kernel.
// UMD: browser global GamePackIceForce + Node export.
(function (root) {
  'use strict';
  function registerIceForcePack(api) {
    api.defineTile('slide:ice', { layer: 'terrain',
      onEnterTerrain: function (state, cell, actor) {
        return actor.dir || null;
      } });
    const dirs = { north: 'up', south: 'down', west: 'left', east: 'right' };
    for (const name of Object.keys(dirs)) {
      api.defineTile('slide:force-' + name, { layer: 'terrain',
        forceDir: dirs[name],
        onEnterTerrain: function (state, cell) {
          return cell.def.forceDir || null;
        } });
    }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = registerIceForcePack;
  root.GamePackIceForce = registerIceForcePack;
})(typeof window !== 'undefined' ? window : globalThis);
