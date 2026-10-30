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

  // Orbs left, counted from the state grid exactly as
  // GameCore.readout reports it ('*' or 'O' tiles not yet collected).
  function orbsLeft(state) {
    let n = 0;
    for (const row of (state && state.grid) || []) {
      for (const ch of row) if (ch === '*' || ch === 'O') n++;
    }
    return n;
  }

  // Current level number: an explicit level_number/number in the
  // level data wins; otherwise the trailing digits of the level id
  // (chip1 -> 1); otherwise 0.
  function levelNumber(level, levelName) {
    if (level && typeof level.level_number === 'number') return level.level_number;
    if (level && typeof level.number === 'number') return level.number;
    const m = /(\d+)\s*$/.exec(String(levelName || (level && level.name) || ''));
    return m ? parseInt(m[1], 10) : 0;
  }

  const api = { digitsFor, timerSeconds, orbsLeft, levelNumber };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameHud = api;
})(typeof window !== 'undefined' ? window : globalThis);
