// Pack: weight switch (mech-29-weight-switch sanity check).
// The plate is active only while a block sits on it, or while the
// player stands on it: the linked door is open exactly while some
// plate cell is weighted (a block left on it, or the player present),
// and removing the weight closes it. Standing on the plate therefore
// opens the door but cannot leave it held; a block left behind is
// the permanent hold the floor switch cannot give. Pushing blocks
// onto the plate is mechanic 81 (blocks.yml); this pack owns the
// plate, door and block tiles and the door rule, which reads only
// layered state (terrain/objects/actors), so stepping stays pure
// and deterministic with no wall-clock reads. Restart restores the
// plate empty and the door closed because a fresh initialState
// rebuilds the room. UMD: browser global GamePackWeightSwitch +
// Node export (register fn).
(function (root) {
  'use strict';
  function isWeighted(state) {
    for (let y = 0; y < state.height; y++) {
      for (let x = 0; x < state.width; x++) {
        if (state.terrain[y][x] !== 'weight:plate') continue;
        if (state.objects[y][x] === 'weight:block') return true;
        for (const a of state.actors) {
          if (a.x === x && a.y === y) return true;
        }
      }
    }
    return false;
  }
  function registerWeightSwitchPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image for every YAML assets entry of mechanic 29.
    for (const name of ['weight-switch-empty.png',
      'weight-switch-weighted.png', 'door-closed.png', 'door-open.png',
      'jolly-on-weight-switch.png', 'push-block.png',
      'heavy-block.png']) {
      api.defineAsset(name, { pack: 'weight-switch', bundled: true });
    }
    api.defineTile('weight:plate', { layer: 'terrain',
      sprite: 'weight-switch-empty.png', glyph: 'W' });
    api.defineTile('weight:door', { layer: 'object',
      sprite: 'door-closed.png', glyph: 'E',
      blocks: function (state) { return !isWeighted(state); } });
    // A block left on the plate is the permanent hold. Until push
    // block (mech 81) lands it cannot be pushed; it blocks movement
    // like a wall fixture wherever a level places it.
    api.defineTile('weight:block', { layer: 'object',
      sprite: 'push-block.png', glyph: 'B',
      blocks: function () { return true; } });
  }
  registerWeightSwitchPack.isWeighted = isWeighted;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerWeightSwitchPack;
  }
  root.GamePackWeightSwitch = registerWeightSwitchPack;
})(typeof window !== 'undefined' ? window : globalThis);
