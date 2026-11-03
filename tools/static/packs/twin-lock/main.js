// Pack: twin lock (mech-11-twin-lock sanity check).
// A twin lock needs two keys of its colour at once. Pressing into
// it holding exactly one matching key shows it still needs one
// more (the lock swaps to its needs-one form), consumes nothing,
// and leaves the player where they pressed from. Pressing holding
// two matching keys consumes both and the lock dissolves to floor
// (its object is removed, the player steps through). Wrong-colour
// keys never count. Restart restores it because a fresh
// initialState rebuilds the room. All state advances through the
// pure step function; no rule reads wall-clock time.
// UMD: browser global GamePackTwinLock + Node export.
(function (root) {
  'use strict';
  var DIRS = { up: {x:0,y:-1}, down: {x:0,y:1}, left: {x:-1,y:0}, right: {x:1,y:0} };
  function registerTwinLockPack(api) {
    for (const name of ['twin-lock.png', 'twin-lock-needs-one.png', 'matching-key.png']) {
      api.defineAsset(name, { pack: 'twin-lock', bundled: true });
    }
    function makeTwin(color, needsOne) {
      const itemId = 'keys:key-' + color;
      const warnId = 'twin:lock-' + color + '-needs-one';
      return {
        layer: 'object',
        sprite: needsOne ? 'twin-lock-needs-one.png' : 'twin-lock.png',
        glyph: needsOne ? 't' : 'T',
        onEnter: function (state, cell, actor, fx) {
          const count = (state.inventory || []).filter((e) => e.item === itemId).length;
          if (count >= 2) {
            fx.push({ type: 'consumeItem', item: itemId });
            fx.push({ type: 'consumeItem', item: itemId });
            fx.push({ type: 'removeObject', x: cell.x, y: cell.y });
            return;
          }
          if (count === 1 && !needsOne) {
            fx.push({ type: 'setObject', x: cell.x, y: cell.y, def: warnId });
            fx.push({ type: 'setMeta', x: cell.x, y: cell.y, key: 'twin_needs_one', value: true });
          }
          const d = DIRS[actor.dir] || { x: 0, y: 0 };
          fx.push({ type: 'teleport', actor: actor.id, x: cell.x - d.x, y: cell.y - d.y });
        }
      };
    }
    api.onLevelDefs(function (level, ch, e) {
      if (!ch || !e || !e.twin_lock_color) return null;
      const color = e.twin_lock_color;
      api.defineTile('twin:lock-' + color, makeTwin(color, false));
      api.defineTile('twin:lock-' + color + '-needs-one', makeTwin(color, true));
      return 'twin:lock-' + color;
    });
    api.onLevelLoad(function (state) {
      for (const id of Object.keys(state.chars.object)) { /* keep kernel chars */ }
      // Ensure projected chars for both forms (level char T + warn t).
      for (const y of state.objects) for (const id of y) {
        if (id && id.indexOf('twin:lock-') === 0 && !id.endsWith('-needs-one')) {
          if (!state.chars.object[id]) state.chars.object[id] = 'T';
          state.chars.object[id + '-needs-one'] = 't';
        }
      }
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = registerTwinLockPack;
  root.GamePackTwinLock = registerTwinLockPack;
})(typeof window !== 'undefined' ? window : globalThis);
