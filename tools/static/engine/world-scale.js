// World scale: one fixed on-screen tile size for every level.
// Renderer-only (like camera.js): the kernel and game state never know
// it exists. Before the camera, movement-room rendered at its native
// 64px tile; that is the pinned reference (WORLD_TILE_PX). A level's
// own `tile` value and its size never change the on-screen scale:
// small levels letterbox, large levels show a scrolling window, and
// the camera only translates the board — it never rescales it.
// UMD: browser global GameWorldScale + Node export.
(function (root) {
  'use strict';
  const WORLD_TILE_PX = 64;
  // Board transform for an available area. Scale is always uniform
  // (scaleX === scaleY === 1 at WORLD_TILE_PX per tile), so tiles stay
  // square and sprites keep their source aspect. The visible view is
  // centred in the area; the camera offset shifts it by whole tiles.
  function boardTransform(opts) {
    const tilePx = WORLD_TILE_PX;
    const x = (opts.availW - opts.viewW * tilePx) / 2 - (opts.camX || 0) * tilePx;
    const y = (opts.availH - opts.viewH * tilePx) / 2 - (opts.camY || 0) * tilePx;
    return { scaleX: 1, scaleY: 1, tilePx: tilePx, x: x, y: y };
  }
  // The view the camera may frame in embed: only tiles that fully
  // fit the available area at WORLD_TILE_PX, capped by the level and
  // by the camera's MAX view. Framing more than fits puts the player
  // in the cropped part of the view at the level's edges.
  function visibleView(opts) {
    const fitW = Math.max(1, Math.floor(opts.availW / WORLD_TILE_PX));
    const fitH = Math.max(1, Math.floor(opts.availH / WORLD_TILE_PX));
    return { w: Math.min(opts.cols, opts.maxW, fitW),
             h: Math.min(opts.rows, opts.maxH, fitH) };
  }
  const api = { WORLD_TILE_PX: WORLD_TILE_PX, boardTransform: boardTransform,
    visibleView: visibleView };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameWorldScale = api;
})(typeof window !== 'undefined' ? window : globalThis);
