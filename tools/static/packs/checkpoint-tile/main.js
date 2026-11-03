// Pack: checkpoint tile (mech-48-checkpoint-tile sanity check).
// Stepping on a checkpoint lights it and makes it the player's
// respawn; only the last one touched is active. The pack's hazard
// tile is lethal in the usual way when no checkpoint is active
// (the attempt is lost and restarts from the level start), but
// with an active checkpoint a hazard death teleports the player
// back to that checkpoint instead of losing: the state is never
// reset, so the timer (driven by recorded t_ms), collected orbs
// and held keys are exactly as they were at the death. Restart
// restores the room because a fresh initialState has no active
// checkpoint and no lit tiles. All state advances through the
// pure step function; no rule reads wall-clock time.
// UMD: browser global GamePackCheckpointTile + Node export.
(function (root) {
  'use strict';
  function registerCheckpointPack(api) {
    // Bundled assets (see manifest.json): real generated art.
    for (const name of ['checkpoint-off.png', 'checkpoint-on.png']) {
      api.defineAsset(name, { pack: 'checkpoint-tile', bundled: true });
    }
    api.defineTile('checkpoint:checkpoint', { layer: 'object',
      sprite: 'checkpoint-off.png', glyph: 'K',
      onEnter: function (state, cell, actor, fx) {
        // Last one touched wins: unlight every other checkpoint,
        // light this one, and remember it as the respawn. The
        // respawn lives in the actor flags so the hazard tile can
        // find it without scanning the grid.
        for (const k of Object.keys(state.meta || {})) {
          if (state.meta[k] && state.meta[k].checkpoint_active) {
            const parts = k.split(',');
            fx.push({ type: 'setMeta', x: Number(parts[0]),
              y: Number(parts[1]), key: 'checkpoint_active',
              value: false });
          }
        }
        fx.push({ type: 'setMeta', x: cell.x, y: cell.y,
          key: 'checkpoint_active', value: true });
        actor.flags.checkpoint = { x: cell.x, y: cell.y };
      } });
    api.defineTile('checkpoint:hazard', { layer: 'object',
      sprite: null, glyph: 'H',
      onEnter: function (state, cell, actor, fx) {
        const cp = actor.flags && actor.flags.checkpoint;
        if (cp) {
          fx.push({ type: 'teleport', actor: actor.id,
            x: cp.x, y: cp.y });
        } else {
          fx.push({ type: 'lose' });
        }
      } });
    // Neither tile char comes from a core legend hook, so give the
    // projected grid chars names here (kernel projection fallback).
    api.onLevelLoad(function (state) {
      state.chars.object['checkpoint:checkpoint'] = 'K';
      state.chars.object['checkpoint:hazard'] = 'H';
    });
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerCheckpointPack;
  }
  root.GamePackCheckpointTile = registerCheckpointPack;
})(typeof window !== 'undefined' ? window : globalThis);
