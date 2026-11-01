// Pack: final door (mech-100-final-door sanity check).
// The final door checks the inventory, bot included, for at least
// one key of each colour (red, gold, green, blue, silver) held at
// the same time. The bot that would carry extra keys (mule bot,
// mech 40) is unbuilt, so every held key lives in the single kernel
// inventory array; counting that array once is exactly the
// bot-inclusive check once a bot stores its keys there too.
// Holding them all opens the door permanently and consumes none of
// them: the closed tile swaps to the open tile and the player walks
// through with every key still held. Missing any colour does
// nothing at all: the closed tile blocks the step, no key is spent,
// and the corridor back stays walkable, so a player who arrives
// unprepared walks back for the missing colour and is never
// stranded. All state advances through the pure step function and
// no rule reads wall-clock time. Restart restores the door because
// a fresh initialState rebuilds the room.
// UMD: browser global GamePackFinalDoor + Node export (register fn).
(function (root) {
  'use strict';
  var COLOURS = ['red', 'gold', 'green', 'blue', 'silver'];
  function holdsEveryColour(state) {
    var held = {};
    for (var i = 0; i < (state.inventory || []).length; i++) {
      held[state.inventory[i].item] = true;
    }
    return COLOURS.every(function (colour) {
      return !!held['keys:key-' + colour];
    });
  }
  function registerFinalDoorPack(api) {
    for (const name of ['final-door-closed.png', 'final-door-open.png',
      'final-door-colour-check.png']) {
      api.defineAsset(name, { pack: 'final-door', bundled: true });
    }
    api.defineTile('final-door:closed', { layer: 'object',
      sprite: 'final-door-closed.png', glyph: 'D',
      blocks: function (state) { return !holdsEveryColour(state); },
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'final-door:open' });
      } });
    api.defineTile('final-door:open', { layer: 'object',
      sprite: 'final-door-open.png', glyph: 'd' });
    api.onLevelLoad(function (state) {
      if (!state.chars.object['final-door:closed']) {
        state.chars.object['final-door:closed'] = 'D';
      }
      state.chars.object['final-door:open'] = 'd';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerFinalDoorPack;
  }
  root.GamePackFinalDoor = registerFinalDoorPack;
})(typeof window !== 'undefined' ? window : globalThis);
