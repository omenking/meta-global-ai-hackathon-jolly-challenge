// Camera: pure viewport math for levels larger than the screen.
// Renderer-only: the kernel and game state never know it exists.
// Supports levels up to 64x64 (human decision 2026-10-30); levels at
// or under the viewport clamp to origin and render as before.
// UMD: browser global GameCamera + Node export.
(function (root) {
  'use strict';
  const MAX_VIEW_W = 17, MAX_VIEW_H = 16;
  function viewSize(cols, rows) {
    return { w: Math.min(cols, MAX_VIEW_W), h: Math.min(rows, MAX_VIEW_H) };
  }
  // Top-left tile of the viewport, centred on the player and clamped
  // to level bounds. Pure function of (level size, view size, player).
  function compute(opts) {
    const view = viewSize(opts.cols, opts.rows);
    const vw = opts.viewW || view.w, vh = opts.viewH || view.h;
    const maxX = Math.max(0, opts.cols - vw), maxY = Math.max(0, opts.rows - vh);
    const cx = opts.player.x - Math.floor(vw / 2);
    const cy = opts.player.y - Math.floor(vh / 2);
    return { x: Math.max(0, Math.min(maxX, cx)),
      y: Math.max(0, Math.min(maxY, cy)), w: vw, h: vh };
  }
  const api = { compute: compute, viewSize: viewSize,
    MAX_VIEW_W: MAX_VIEW_W, MAX_VIEW_H: MAX_VIEW_H };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameCamera = api;
})(typeof window !== 'undefined' ? window : globalThis);
