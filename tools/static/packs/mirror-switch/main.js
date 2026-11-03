// Pack: mirror switch (mech-30-mirror-switch sanity check).
// One press on the mirror inverts every switch in the room at once:
// each toggle flips A<->B exactly once and doors follow the toggles
// (open only when every toggle is A), so the mirror is a room reset
// with consequences, not a door opener itself. A single toggle press
// flips only that toggle (and the doors that follow it). Broken
// one-time switches (mirror:onetime-broken) are never flipped.
// All state advances through the pure step function; no wall-clock.
// UMD: browser global GamePackMirrorSwitch + Node export.
(function (root) {
  'use strict';
  function registerMirrorPack(api) {
    for (const name of ['mirror-switch.png', 'toggle-switch-a.png',
      'toggle-switch-b.png', 'door-closed.png', 'door-open.png']) {
      api.defineAsset(name, { pack: 'mirror-switch', bundled: true });
    }
    function scan(state) {
      const toggles = [], doors = [];
      for (let y = 0; y < state.objects.length; y++) {
        for (let x = 0; x < state.objects[y].length; x++) {
          const id = state.objects[y][x];
          if (id === 'mirror:toggle-a' || id === 'mirror:toggle-b') {
            toggles.push({ x: x, y: y, id: id });
          } else if (id === 'mirror:door-closed' ||
              id === 'mirror:door-open') {
            doors.push({ x: x, y: y, id: id });
          }
        }
      }
      return { toggles: toggles, doors: doors };
    }
    function doorFx(state, fx, postToggleIds) {
      const allA = postToggleIds.length > 0 &&
        postToggleIds.every((id) => id === 'mirror:toggle-a');
      const want = allA ? 'mirror:door-open' : 'mirror:door-closed';
      for (const d of scan(state).doors) {
        if (d.id !== want) {
          fx.push({ type: 'setObject', x: d.x, y: d.y, def: want });
        }
      }
    }
    api.defineTile('mirror:mirror', { layer: 'object',
      sprite: 'mirror-switch.png', glyph: 'M',
      onEnter: function (state, cell, actor, fx) {
        const found = scan(state);
        const post = [];
        for (const t of found.toggles) {
          const flipped = t.id === 'mirror:toggle-a'
            ? 'mirror:toggle-b' : 'mirror:toggle-a';
          post.push(flipped);
          fx.push({ type: 'setObject', x: t.x, y: t.y, def: flipped });
        }
        doorFx(state, fx, post);
      } });
    function toggleDef(id, sprite, glyph) {
      return { layer: 'object', sprite: sprite, glyph: glyph,
        onEnter: function (state, cell, actor, fx) {
          const flipped = id === 'mirror:toggle-a'
            ? 'mirror:toggle-b' : 'mirror:toggle-a';
          fx.push({ type: 'setObject', x: cell.x, y: cell.y,
            def: flipped });
          const post = scan(state).toggles.map((t) =>
            (t.x === cell.x && t.y === cell.y) ? flipped : t.id);
          doorFx(state, fx, post);
        } };
    }
    api.defineTile('mirror:toggle-a',
      toggleDef('mirror:toggle-a', 'toggle-switch-a.png', 'A'));
    api.defineTile('mirror:toggle-b',
      toggleDef('mirror:toggle-b', 'toggle-switch-b.png', 'B'));
    api.defineTile('mirror:door-closed', { layer: 'object',
      sprite: 'door-closed.png', glyph: 'D',
      blocks: function () { return true; } });
    api.defineTile('mirror:door-open', { layer: 'object',
      sprite: 'door-open.png', glyph: 'd' });
    api.defineTile('mirror:onetime', { layer: 'object',
      sprite: 'toggle-switch-a.png', glyph: 'N',
      onEnter: function (state, cell, actor, fx) {
        fx.push({ type: 'setObject', x: cell.x, y: cell.y,
          def: 'mirror:onetime-broken' });
      } });
    api.defineTile('mirror:onetime-broken', { layer: 'object',
      sprite: 'toggle-switch-b.png', glyph: 'n' });
    api.onLevelLoad(function (state) {
      state.chars.object['mirror:toggle-a'] =
        state.chars.object['mirror:toggle-a'] || 'A';
      state.chars.object['mirror:toggle-b'] =
        state.chars.object['mirror:toggle-b'] || 'B';
      state.chars.object['mirror:door-closed'] =
        state.chars.object['mirror:door-closed'] || 'D';
      state.chars.object['mirror:door-open'] = 'd';
      state.chars.object['mirror:onetime'] =
        state.chars.object['mirror:onetime'] || 'N';
      state.chars.object['mirror:onetime-broken'] = 'n';
      state.chars.object['mirror:mirror'] =
        state.chars.object['mirror:mirror'] || 'M';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMirrorPack;
  }
  root.GamePackMirrorSwitch = registerMirrorPack;
})(typeof window !== 'undefined' ? window : globalThis);
