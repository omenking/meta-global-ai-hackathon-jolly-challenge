// Pack: decoy Jolly (mech-39-decoy-jolly sanity check).
// Carrying: stepping on the pickup gives the single decoy item
// (one slot, readout "decoy"). Stepping off the pickup consumes
// it and leaves decoy:decoy on the vacated tile, so deployment is
// walking through it with no new key. The decoy lasts 20 moves
// after the deployment move (ttl 21 set on exit, tick decrements
// to 20 on that same step, then one per move to removal). A decoy
// only draws the guard if a guard had line of sight to the drop
// tile at the drop moment (seen flag in cell meta): the teaching
// room's guard patrols vertically, so rushing drops it unseen
// while hesitating two steps drops it on the guard's corridor row.
// While a seen decoy stands, the guard targets the decoy tile
// instead of the player; otherwise it chases a player it can see
// and patrols when it can see neither. Guard contact (same tile
// or adjacent) loses only while the guard targets the player.
// All state advances through the pure step function; no wall-clock.
(function (root) {
  'use strict';
  function registerDecoyPack(api) {
    for (const n of ['decoy-pickup.png', 'decoy-jolly.png', 'decoy-slot.png']) {
      api.defineAsset(n, { pack: 'decoy', bundled: true });
    }
    api.defineItem('decoy:decoy-item', { icon: 'decoy-slot.png', readout: 'decoy' });
    function findDecoy(state) {
      for (let y = 0; y < state.height; y++) for (let x = 0; x < state.width; x++) {
        if (state.objects[y][x] === 'decoy:decoy') {
          const m = state.meta[x + ',' + y] || {};
          return { x: x, y: y, ttl: m.decoy_ttl || 0, seen: !!m.decoy_seen };
        }
      }
      return null;
    }
    function los(state, ax, ay, bx, by) {
      if (ax !== bx && ay !== by) return false;
      const dx = Math.sign(bx - ax), dy = Math.sign(by - ay);
      let x = ax + dx, y = ay + dy;
      while (x !== bx || y !== by) {
        if (state.terrain[y][x] === 'core:wall') return false;
        x += dx; y += dy;
      }
      return true;
    }
    function blocked(state, x, y) {
      if (x < 0 || y < 0 || x >= state.width || y >= state.height) return true;
      if (state.terrain[y][x] === 'core:wall') return true;
      if (state.objects[y][x] === 'core:gate'
          && (state.counters['core:orbs_left'] || 0) > 0) return true;
      return false;
    }
    function toward(state, actor, tx, ty) {
      const dx = tx - actor.x, dy = ty - actor.y;
      if (!dx && !dy) return null;
      const horiz = dx > 0 ? 'right' : 'left';
      const vert = dy > 0 ? 'down' : 'up';
      const first = Math.abs(dx) >= Math.abs(dy)
        ? { dir: horiz, x: actor.x + Math.sign(dx), y: actor.y }
        : { dir: vert, x: actor.x, y: actor.y + Math.sign(dy) };
      const second = first.dir === horiz
        ? { dir: vert, x: actor.x, y: actor.y + Math.sign(dy) }
        : { dir: horiz, x: actor.x + Math.sign(dx), y: actor.y };
      if ((first.dir === horiz ? dx : dy) !== 0 && !blocked(state, first.x, first.y)) return first.dir;
      if ((second.dir === horiz ? dx : dy) !== 0 && !blocked(state, second.x, second.y)) return second.dir;
      return null;
    }
    api.defineTile('decoy:pickup', { layer: 'object', sprite: 'decoy-pickup.png', glyph: 'D',
      onEnter: function (state, cell, actor, fx) {
        const carrying = (state.inventory || []).some((e) => e.item === 'decoy:decoy-item');
        if (!carrying && !findDecoy(state)) fx.push({ type: 'giveItem', item: 'decoy:decoy-item' });
      },
      onExit: function (state, cell, actor, fx) {
        const carrying = (state.inventory || []).some((e) => e.item === 'decoy:decoy-item');
        if (!carrying) return;
        const seen = state.actors.some((a) => a.def === 'decoy:guard'
          && los(state, a.x, a.y, cell.x, cell.y)) ? 1 : 0;
        fx.push({ type: 'consumeItem', item: 'decoy:decoy-item' });
        fx.push({ type: 'setObject', x: cell.x, y: cell.y, def: 'decoy:decoy' });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y, key: 'decoy_ttl', value: 21 });
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y, key: 'decoy_seen', value: seen });
      } });
    api.defineTile('decoy:decoy', { layer: 'object', sprite: 'decoy-jolly.png', glyph: 'Y' });
    api.defineController('decoy:guard', function (state, actor) {
      const player = state.actors.find((a) => a.id === 'player');
      const decoy = findDecoy(state);
      if (decoy && decoy.seen && decoy.ttl > 0) {
        return toward(state, actor, decoy.x, decoy.y);
      }
      if (player && los(state, actor.x, actor.y, player.x, player.y)) {
        return toward(state, actor, player.x, player.y);
      }
      let dir = actor.flags.patrol_dir || 'down';
      const d = dir === 'down' ? { x: actor.x, y: actor.y + 1 } : { x: actor.x, y: actor.y - 1 };
      if (blocked(state, d.x, d.y)) {
        dir = dir === 'down' ? 'up' : 'down';
        actor.flags.patrol_dir = dir;
        const d2 = dir === 'down' ? { x: actor.x, y: actor.y + 1 } : { x: actor.x, y: actor.y - 1 };
        if (blocked(state, d2.x, d2.y)) return null;
      }
      return dir;
    });
    api.onTick(function (state, fx) {
      const decoy = findDecoy(state);
      if (decoy) {
        if (decoy.ttl <= 1) {
          fx.push({ type: 'removeObject', x: decoy.x, y: decoy.y });
          fx.push({ type: 'setMeta', x: decoy.x, y: decoy.y, key: 'decoy_ttl', value: 0 });
        } else {
          fx.push({ type: 'setMeta', x: decoy.x, y: decoy.y, key: 'decoy_ttl', value: decoy.ttl - 1 });
        }
      }
      const active = decoy && decoy.seen && decoy.ttl > 1;
      if (active) return;
      const player = state.actors.find((a) => a.id === 'player');
      if (!player) return;
      for (const a of state.actors) {
        if (a.def !== 'decoy:guard') continue;
        if (Math.abs(a.x - player.x) + Math.abs(a.y - player.y) <= 1) {
          fx.push({ type: 'lose' });
          return;
        }
      }
    });
    api.onLevelLoad(function (state) {
      state.chars.object['decoy:pickup'] = 'D';
      state.chars.object['decoy:decoy'] = 'Y';
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = registerDecoyPack;
  root.GamePackDecoy = registerDecoyPack;
})(typeof window !== 'undefined' ? window : globalThis);
