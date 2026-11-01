// Pack: mule bot (mech-40-mule-bot sanity check).
// A follower that carries 4 extra inventory slots. The bot is a
// generic actor (legend actor "mule:bot"); it follows the exact
// path the player walked, one tile behind, via a tick hook that
// teleports it to the player's previous path tile each step.
// Moving backwards into it therefore swaps tiles (the bot moves
// to the tile the player just vacated), so it never blocks.
// If its next path tile is a hazard (water, void, or mule:hazard)
// it waits and catches up one tile per step when that tile can
// be entered. Inventory stays the kernel's single ordered list:
// the first 4 entries are the player's slots, the next 4 are the
// bot's (the second HUD row); the kernel cap of 8 is the total.
// Path history lives in flags as a replaced (never mutated)
// array, so step stays pure; no wall-clock reads.
// UMD: browser global GamePackMuleBot + Node export.
(function (root) {
  'use strict';
  function isHazard(state, x, y) {
    var terr = state.terrain[y] && state.terrain[y][x];
    var obj = state.objects[y] && state.objects[y][x];
    return terr === 'water:water' || terr === 'mule:hazard'
      || obj === 'crumble:void';
  }
  function registerMuleBotPack(api) {
    for (const name of ['mule-bot.png', 'mule-bot-waiting.png',
      'mule-slots.png']) {
      api.defineAsset(name, { pack: 'mule-bot', bundled: true });
    }
    api.defineTile('mule:hazard', { layer: 'terrain',
      sprite: 'mule-bot-waiting.png', glyph: 'H',
      onEnterTerrain: function (state, cell, actor, fx) {
        fx.push({ type: 'lose' });
        return null;
      } });
    api.defineController('mule:bot', function () { return null; });
    api.onLevelLoad(function (state) {
      var bot = state.actors.find(function (a) { return a.def === 'mule:bot'; });
      if (!bot) return;
      var player = state.actors.find(function (a) { return a.id === 'player'; });
      state.flags['mule:path'] = [{ x: bot.x, y: bot.y },
        { x: player.x, y: player.y }];
      state.flags['mule:bot_idx'] = 0;
      state.flags['mule:waiting'] = false;
      state.counters['mule:player_slots'] = 0;
      state.counters['mule:bot_slots'] = 0;
    });
    api.onTick(function (state, fx) {
      var bot = state.actors.find(function (a) { return a.def === 'mule:bot'; });
      if (!bot) return;
      var player = state.actors.find(function (a) { return a.id === 'player'; });
      var path = state.flags['mule:path'];
      if (!Array.isArray(path) || !path.length) {
        path = [{ x: bot.x, y: bot.y }, { x: player.x, y: player.y }];
        state.flags['mule:bot_idx'] = 0;
      }
      var last = path[path.length - 1];
      if (last.x !== player.x || last.y !== player.y) {
        path = path.concat([{ x: player.x, y: player.y }]);
      }
      state.flags['mule:path'] = path;
      var idx = state.flags['mule:bot_idx'] || 0;
      var nextPos = path[idx + 1];
      var waiting = false;
      if (nextPos) {
        if (isHazard(state, nextPos.x, nextPos.y)) {
          waiting = true;
        } else {
          fx.push({ type: 'teleport', actor: bot.id,
            x: nextPos.x, y: nextPos.y });
          state.flags['mule:bot_idx'] = idx + 1;
        }
      }
      state.flags['mule:waiting'] = waiting;
      var n = (state.inventory || []).length;
      state.counters['mule:player_slots'] = Math.min(4, n);
      state.counters['mule:bot_slots'] = Math.max(0, n - 4);
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerMuleBotPack;
  }
  root.GamePackMuleBot = registerMuleBotPack;
})(typeof window !== 'undefined' ? window : globalThis);
