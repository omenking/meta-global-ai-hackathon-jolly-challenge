// Pack: Twin Jolly (mech-92-twin-jolly sanity check).
// A level mode, not a tile: two Jollys share one input. The first
// Jolly is the kernel player; the second spawns from a legend entry
// with actor twin:second and is driven by a deterministic controller
// that repeats the recorded input (state.last_input). Each step both
// try to move and a blocked one stays (kernel canEnter). Orbs and
// keys are shared counters/inventory: the kernel fires onEnter for
// the player, and the tick hook below fires the same onEnter for the
// twin so either Jolly collects exactly once. If either Jolly stands
// on the hazard or touches another actor, the level is lost for
// both. Both Jollys must hold twin exits with no orbs left to win.
// All state advances through the pure step function; no rule reads
// wall-clock time. UMD: browser global GamePackTwin + Node export.
(function (root) {
  'use strict';
  function registerTwinPack(api) {
    api.defineAsset('jolly-twin.png', { pack: 'twin', bundled: true });
    api.defineAsset('twin-mode.png', { pack: 'twin', bundled: true });
    api.defineTile('twin:hazard', { layer: 'terrain', glyph: 'H',
      sprite: 'void.png',
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
        return null;
      } });
    api.defineTile('twin:exit', { layer: 'object', glyph: 'E',
      sprite: 'portal.png' });
    api.defineController('twin:second', function (state) {
      const dir = state.last_input;
      return (dir === 'up' || dir === 'down' || dir === 'left'
        || dir === 'right') ? dir : null;
    });
    api.onTick(function (state, fx) {
      const twin = (state.actors || []).find(
        (a) => a.def === 'twin:second');
      if (!twin) return;
      const heroes = (state.actors || []).filter(
        (a) => a.id === 'player' || a.def === 'twin:second');
      const foes = (state.actors || []).filter(
        (a) => a.id !== 'player' && a.def !== 'twin:second');
      for (const hero of heroes) {
        if (state.terrain[hero.y][hero.x] === 'twin:hazard'
            || state.objects[hero.y][hero.x] === 'twin:hazard') {
          fx.push({ type: 'lose' });
          return;
        }
        if (foes.some((f) => f.x === hero.x && f.y === hero.y)) {
          fx.push({ type: 'lose' });
          return;
        }
      }
      // Shared collection for the twin: fire the stood-on object's
      // own onEnter (orb, key, lock) so counts stay shared and once.
      const objId = state.objects[twin.y][twin.x];
      if (objId && objId !== 'twin:exit') {
        const def = api.getTile(objId);
        if (def && def.onEnter) {
          def.onEnter(state,
            { x: twin.x, y: twin.y, def: def, meta: {} }, twin, fx);
        }
      }
      const pending = fx.reduce((n, e) => n + (
        e.type === 'incCounter' && e.key === 'core:orbs_left'
          ? (e.by || 0) : 0), 0);
      const orbsLeft = (state.counters['core:orbs_left'] || 0) + pending;
      const bothOut = heroes.length === 2 && heroes.every(
        (h) => state.objects[h.y][h.x] === 'twin:exit')
        && (heroes[0].x !== heroes[1].x || heroes[0].y !== heroes[1].y);
      if (bothOut && orbsLeft === 0) fx.push({ type: 'win' });
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerTwinPack;
  }
  root.GamePackTwin = registerTwinPack;
})(typeof window !== 'undefined' ? window : globalThis);
