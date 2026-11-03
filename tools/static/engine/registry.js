// Definition registry: packs register namespaced tile/item defs,
// actor controllers, level hooks and tick hooks here. The kernel
// (engine/kernel.js) only ever talks to this registry, never to a
// specific mechanic. UMD like game-hud.js: browser global + Node export.
(function (root) {
  'use strict';
  function createRegistry() {
    const tiles = new Map(), items = new Map(), assets = new Map();
    const levelDefHooks = [], levelHooks = [], tickHooks = [], timerHooks = [], controllers = new Map();
    const beforeMoveHooks = [];
    const api = {
      defineTile: function (id, def) { tiles.set(id, Object.assign({ id: id }, def)); },
      defineItem: function (id, def) { items.set(id, Object.assign({ id: id }, def)); },
      // Packs bring their own assets: sprite/icon file names a pack
      // needs are declared here so preload/render never hardcode them.
      // A bundled asset lives in the pack folder and loads from
      // packs/<pack>/assets/<name>; anything else is shared art and
      // loads from level-sprites/<name>. The manifest in each pack
      // folder (manifest.json) lists the same files for humans.
      defineAsset: function (name, opts) {
        if (!name) return;
        assets.set(name, { pack: (opts && opts.pack) || null,
          bundled: !!(opts && opts.bundled) });
      },
      assetNames: function () { return [...assets.keys()]; },
      assetPaths: function () {
        return [...assets.entries()].map(([name, a]) => ({ name: name,
          url: a.bundled && a.pack
            ? 'packs/' + a.pack + '/assets/' + name
            : 'level-sprites/' + name }));
      },
      onLevelDefs: function (fn) { levelDefHooks.push(fn); },
      onLevelLoad: function (fn) { levelHooks.push(fn); },
      onTick: function (fn) { tickHooks.push(fn); },
      // Before-move hooks run inside step() just before the player's
      // move is attempted: fn(state, actor, dirName) may mutate the
      // (already cloned) state and returns false to veto the move.
      onBeforeMove: function (fn) { beforeMoveHooks.push(fn); },
      // Timer hooks map (previous state, input t_ms) to the
      // effective elapsed seconds the level timer should show;
      // packs use them to freeze or slow the clock deterministically
      // from recorded t_ms only (never wall-clock).
      onTimer: function (fn) { timerHooks.push(fn); },
      defineController: function (defId, fn) { controllers.set(defId, fn); },
      getTile: function (id) { return tiles.get(id) || null; },
      getItem: function (id) { return items.get(id) || null; },
      getController: function (defId) { return controllers.get(defId) || null; },
      _levelDefHooks: levelDefHooks, _levelHooks: levelHooks, _tickHooks: tickHooks,
      _beforeMoveHooks: beforeMoveHooks, _timerHooks: timerHooks,
      tileIds: function () { return [...tiles.keys()]; },
    };
    api.registerPack = function (registerFn) { registerFn(api); return api; };
    return api;
  }
  const api = { createRegistry: createRegistry };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameRegistry = api;
})(typeof window !== 'undefined' ? window : globalThis);
