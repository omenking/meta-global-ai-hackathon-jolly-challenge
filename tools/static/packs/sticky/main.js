// Pack: sticky tile (mech-8-sticky-tile sanity check).
// A sticky tile is a floor variant that takes two inputs to leave:
// the first directional input strains in place (the player stays,
// shown straining), and the second steps off in whichever direction
// it presses. Entering the tile is a normal one-input step. The
// tile never wears out, so crossing it again later costs two inputs
// again. Enemies are not slowed: the exit rule applies only to the
// player actor, so any other actor crosses at full speed. Strain
// is the actor flag `sticky_strained`; a wall bump (a destination
// that cannot be entered at all) does not consume the strain, only
// an otherwise-legal exit attempt does. All state advances through
// the pure step function and no rule reads wall-clock time.
// UMD: browser global GamePackSticky + Node export (register fn).
(function (root) {
  'use strict';
  function registerStickyPack(api) {
    api.defineAsset('sticky.png', { pack: 'sticky', bundled: true });
    api.defineAsset('jolly-straining.png',
      { pack: 'sticky', bundled: true });
    api.defineTile('sticky:sticky', { layer: 'terrain',
      sprite: 'sticky.png', glyph: 'S',
      // Kernel move hook: returning true vetoes leaving this tile
      // for this attempt. First exit attempt strains (veto, flag
      // set); the next attempt clears the flag and is allowed.
      blocksExit: function (state, cell, actor, dir) {
        if (!actor || actor.id !== 'player') return false;
        actor.flags = actor.flags || {};
        if (actor.flags.sticky_strained) {
          actor.flags.sticky_strained = false;
          return false;
        }
        actor.flags.sticky_strained = true;
        return true;
      } });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerStickyPack;
  }
  root.GamePackSticky = registerStickyPack;
})(typeof window !== 'undefined' ? window : globalThis);
