// Board view: builds the static Pixi board for a level (terrain and
// object sprites from rows + legend) and tracks dynamic tiles whose
// sprites follow game state. Extracted from game.js (Phase 5b) with
// no behaviour change; game.js keeps HUD/input/session/render wiring.
// Browser global GameBoardView (classic script, no build step).
(function (root) {
  'use strict';
  function createBoardView(deps) {
    const PIXI = deps.PIXI, board = deps.board, textures = deps.textures;
    const rows = deps.rows, legend = deps.legend, TILE = deps.TILE,
      scale = deps.scale, COLS = deps.COLS, ROWS = deps.ROWS;
    function fallbackTile(gx, gy, ch) {
      const g = new PIXI.Graphics();
      g.rect(gx * TILE, gy * TILE, TILE, TILE).fill(0xff00ff);
      const t = new PIXI.Text({
        text: ch, style: { fontSize: 28, fill: 0x000000, fontWeight: 'bold' } });
      t.anchor.set(0.5);
      t.position.set(gx * TILE + TILE / 2, gy * TILE + TILE / 2);
      board.addChild(g, t);
    }
    function drawSprite(name, gx, gy) {
      const tex = textures[name];
      if (!tex) return false;
      const s = new PIXI.Sprite(tex);
      s.scale.set(scale);
      s.position.set(gx * TILE, gy * TILE);
      board.addChild(s);
      return s;
    }
    // Key/lock/orb/pack-object tiles are dynamic: their sprites follow
    // state (a picked key/flipper, dissolved lock or collected orb
    // turns to floor).
    const dynamicTiles = [];
    for (let gy = 0; gy < ROWS; gy++) {
      for (let gx = 0; gx < COLS; gx++) {
        const ch = rows[gy][gx];
        const e = legend[ch];
        if (!e) { fallbackTile(gx, gy, ch); continue; }
        const isDynamic = !!(e.key_color || e.lock_color || e.def)
          || ch === '*' || ch === 'O' || ch === 'G';
        if (e.base) {
          if (!drawSprite(e.base, gx, gy)) { fallbackTile(gx, gy, ch); continue; }
        } else if (e.lock_color) {
          // Floor under a lock, revealed when it dissolves.
          drawSprite('floor_default.png', gx, gy);
        }
        if (e.sprite && ch !== 'P') {
          const spr = drawSprite(e.sprite, gx, gy);
          if (spr === false) fallbackTile(gx, gy, ch);
          else if (isDynamic && spr) dynamicTiles.push({ x: gx, y: gy, ch: ch, sprite: spr });
        } else if (e.text) {
          const t = new PIXI.Text({
            text: e.text,
            style: { fontSize: 40, fill: 0xffd21f, fontWeight: 'bold',
                     stroke: { color: 0x111111, width: 5 } } });
          t.anchor.set(0.5);
          t.position.set(gx * TILE + TILE / 2, gy * TILE + TILE / 2);
          board.addChild(t);
          if (isDynamic) dynamicTiles.push({ x: gx, y: gy, ch: ch, sprite: t });
        } else if (!e.base) {
          fallbackTile(gx, gy, ch);
        }
      }
    }
    return { dynamicTiles: dynamicTiles };
  }
  const api = { createBoardView: createBoardView };
  root.GameBoardView = api;
})(typeof window !== 'undefined' ? window : globalThis);
