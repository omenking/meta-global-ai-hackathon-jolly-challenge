// Pack: crumbling tile (mech-5-crumbling-tile sanity check).
// A crumbling tile crumbles in stages, and the stage advances
// when the player leaves it, never when they step on it: leaving
// an intact tile makes it minor, leaving a minor tile makes it
// major, and leaving a major tile drops it to void behind the
// player. Every stage is safe to stand on, so the player can
// cross (minor behind), come back (major behind), and cross once
// more (void behind), with no second return. Stepping into an
// existing void is falling and loses the attempt. Restart
// restores every stage because a fresh initialState rebuilds the
// room. The stage is a count in cell meta; all state advances
// through the pure step function and no rule reads wall-clock.
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
      onExit: function (state, cell, actor, fx) {
        const stage = (cell.meta && cell.meta.crumble_stage) || 0;
        if (stage >= 2) {
          fx.push({ type: 'setObject', x: cell.x, y: cell.y,
            def: 'crumble:void' });
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
