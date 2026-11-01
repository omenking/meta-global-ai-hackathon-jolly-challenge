// Pack: crumbling tile (mech-5-crumbling-tile sanity check).
// A crumbling tile crumbles in stages, and the stage advances
// when the player steps on it, never when they leave it: the first
// step-on makes it minor, the second makes it major, and stepping
// onto a major tile makes it fall under the player, so the attempt
// is lost. That gives the player one backtrack: cross (minor),
// come back (major), with the major state visible as the warning
// that the next step-on is the fall. Void, the hole a fallen tile
// leaves, is likewise a hazard on entry. Restart restores every
// stage because a fresh initialState rebuilds the room. The stage
// is a count in cell meta; all state advances through the pure
// step function and no rule reads wall-clock time.
// UMD: browser global GamePackCrumbling + Node export (register fn).
(function (root) {
  'use strict';
  function registerCrumblingPack(api) {
    // Bundled assets (see manifest.json): generated placeholders from
    // tools/make_placeholder_sprites.sh until real art lands.
    for (const name of ['crumbling.png', 'crumbling-minor.png',
      'crumbling-major.png', 'void.png']) {
      api.defineAsset(name, { pack: 'crumbling', bundled: true });
    }
    api.defineTile('crumble:crumbling', { layer: 'object',
      sprite: 'crumbling.png', glyph: 'C',
      onEnter: function (state, cell, actor, fx) {
        const stage = (cell.meta && cell.meta.crumble_stage) || 0;
        if (stage >= 2) {
          fx.push({ type: 'setObject', x: cell.x, y: cell.y,
            def: 'crumble:void' });
          fx.push({ type: 'lose' });
        } else {
          fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
            key: 'crumble_stage', value: stage + 1 });
        }
      } });
    api.defineTile('crumble:void', { layer: 'object',
      sprite: 'void.png', glyph: 'V',
      // Enterable, and entering is falling. Future pushable blocks
      // still never enter void; that rule lives in the block packs
      // (blocks.yml), not in the player movement check here.
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
      } });
    // The void never appears in level rows, so give its projected
    // grid char a name here (the kernel projection falls back to it).
    api.onLevelLoad(function (state) {
      if (!state.chars.object['crumble:crumbling']) {
        state.chars.object['crumble:crumbling'] = 'C';
      }
      state.chars.object['crumble:void'] = 'V';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerCrumblingPack;
  }
  root.GamePackCrumbling = registerCrumblingPack;
})(typeof window !== 'undefined' ? window : globalThis);
