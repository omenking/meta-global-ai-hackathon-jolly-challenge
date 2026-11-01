// Pack: teleport pair (mech-3-teleport-pair sanity check).
// Two pads share a mark (teleport:pad-a / teleport:pad-b). Stepping
// onto a pad instantly moves the player to its same-mark twin,
// keeping their direction; pads work both ways. If an object (for
// example a pushable block) sits on the twin, the teleport does not
// happen and the player stays on the pad they stepped on. Arrival
// on the twin never chains: the kernel runs the terrain hook only
// for the cell the player stepped onto, so the player must step
// off and back on to travel back. All state advances through the
// pure step function; no rule reads wall-clock time. Restart
// restores the room because a fresh initialState rebuilds it.
// UMD: browser global GamePackTeleport + Node export (register fn).
(function (root) {
  'use strict';
  function registerTeleportPack(api) {
    // Bundled assets (see manifest.json): real generated art from
    // scripts/gen-image (Muse Image), grounded on the floor/wall
    // reference sprites.
    for (const name of ['teleport-pad-a.png', 'teleport-pad-b.png']) {
      api.defineAsset(name, { pack: 'teleport', bundled: true });
    }
    function makePad(defId, sprite, glyph) {
      api.defineTile(defId, { layer: 'terrain', sprite: sprite, glyph: glyph,
        onEnterTerrain: function (state, cell, actor, fx) {
          // Twin: the other cell carrying the same pad def (same mark).
          let twin = null;
          for (let y = 0; y < state.height && !twin; y++) {
            for (let x = 0; x < state.width; x++) {
              if ((x !== cell.x || y !== cell.y)
                  && state.terrain[y][x] === defId) { twin = { x: x, y: y }; break; }
            }
          }
          if (!twin) return null;
          // A block (or any object) sitting on the twin prevents it.
          if (state.objects[twin.y][twin.x]) return null;
          fx.push({ type: 'teleport', actor: actor.id, x: twin.x, y: twin.y });
          return null;
        } });
    }
    makePad('teleport:pad-a', 'teleport-pad-a.png', 'a');
    makePad('teleport:pad-b', 'teleport-pad-b.png', 'b');
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = registerTeleportPack;
  }
  root.GamePackTeleport = registerTeleportPack;
})(typeof window !== 'undefined' ? window : globalThis);
