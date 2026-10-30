// Definition registry: packs register namespaced tile/item defs,
// actor controllers, level hooks and tick hooks here. The kernel
// (engine/kernel.js) only ever talks to this registry, never to a
// specific mechanic. UMD like game-hud.js: browser global + Node export.
(function (root) {
  'use strict';
  function createRegistry() {
    const tiles = new Map(), items = new Map(), assets = new Set();
    const levelDefHooks = [], levelHooks = [], tickHooks = [], controllers = new Map();
    const api = {
      defineTile: function (id, def) { tiles.set(id, Object.assign({ id: id }, def)); },
      defineItem: function (id, def) { items.set(id, Object.assign({ id: id }, def)); },
      // Packs bring their own assets: sprite/icon file names a pack
      // needs are declared here so preload/render never hardcode them.
      defineAsset: function (name) { if (name) assets.add(name); },
      assetNames: function () { return [...assets]; },
      onLevelDefs: function (fn) { levelDefHooks.push(fn); },
      onLevelLoad: function (fn) { levelHooks.push(fn); },
      onTick: function (fn) { tickHooks.push(fn); },
      defineController: function (defId, fn) { controllers.set(defId, fn); },
      getTile: function (id) { return tiles.get(id) || null; },
      getItem: function (id) { return items.get(id) || null; },
      getController: function (defId) { return controllers.get(defId) || null; },
      _levelDefHooks: levelDefHooks, _levelHooks: levelHooks, _tickHooks: tickHooks,
      tileIds: function () { return [...tiles.keys()]; },
    };
    api.registerPack = function (registerFn) { registerFn(api); return api; };
    return api;
  }
  const api = { createRegistry: createRegistry };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameRegistry = api;
})(typeof window !== 'undefined' ? window : globalThis);
