// HUD view helpers: pure functions of game state.
//
// The HUD is a view of state and never drives it: every value shown
// (timer, orbs left, level, inventory) is derived here from a
// GameCore state / readout, so live play and replay render the same
// numbers. Kept free of Pixi/DOM so Node can test it (game-core.js
// pattern).
(function (root) {
  'use strict';

  // Split a value into the 3 digits of a reference digit box:
  // floored, padded to 3, clamped to 000..999.
  function digitsFor(value) {
    let v = Math.floor(Number(value));
    if (!isFinite(v) || v < 0) v = 0;
    if (v > 999) v = 999;
    return [Math.floor(v / 100), Math.floor(v / 10) % 10, v % 10];
  }

  // Whole seconds left on the countdown, from core state only.
  function timerSeconds(state) {
    if (!state) return 0;
    if (state.time_left_s === null || state.time_left_s === undefined) {
      return Math.floor(state.elapsed_s || 0);
    }
    return Math.floor(Math.max(0, state.time_left_s));
  }

  const api = { digitsFor, timerSeconds };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameHud = api;
})(typeof window !== 'undefined' ? window : globalThis);
