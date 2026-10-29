// Game page: renders a chosen level (rows + legend) exactly as the
// level preview does. Rendering is a view of the level data; game
// state (deterministic core, sessions, input) layers on top of this.
(async function () {
  'use strict';
  const errorBox = document.getElementById('error');
  function fail(msg) {
    errorBox.style.display = 'block';
    errorBox.textContent = msg;
    document.getElementById('subtitle').textContent = 'failed to load';
  }
  if (!window.PIXI) { fail('PixiJS failed to load (vendor/pixi.min.js).'); return; }

  const params = new URLSearchParams(location.search);
  const levelName = (params.get('level') || 'chip1').replace(/[^a-zA-Z0-9_-]/g, '');
  let level;
  try {
    const res = await fetch('levels/' + levelName + '.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    level = await res.json();
  } catch (err) {
    fail('Could not load levels/' + levelName + '.json: ' + err.message +
      '. Run tools/prep_level_sprites.sh first.');
    return;
  }
  const rows = level.rows, legend = level.legend, TILE = level.tile || 64;
  const COLS = rows[0].length, ROWS = rows.length;

  const spriteNames = new Set();
  for (const key of Object.keys(legend)) {
    const e = legend[key];
    if (e.base) spriteNames.add(e.base);
    if (e.sprite) spriteNames.add(e.sprite);
  }
  const textures = {};
  const missing = new Set();
  await Promise.all([...spriteNames].map(async (name) => {
    try {
      textures[name] = await PIXI.Assets.load('level-sprites/' + name);
    } catch (err) {
      missing.add(name);
    }
  }));

  const app = new PIXI.Application();
  await app.init({ width: COLS * TILE, height: ROWS * TILE, background: '#111' });
  document.getElementById('stage').appendChild(app.canvas);
  const scale = TILE / 512;
  const board = new PIXI.Container();
  app.stage.addChild(board);

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

  for (let gy = 0; gy < ROWS; gy++) {
    for (let gx = 0; gx < COLS; gx++) {
      const ch = rows[gy][gx];
      const e = legend[ch];
      if (!e) { fallbackTile(gx, gy, ch); continue; }
      if (e.base) {
        if (!drawSprite(e.base, gx, gy)) { fallbackTile(gx, gy, ch); continue; }
      }
      if (e.sprite) {
        if (drawSprite(e.sprite, gx, gy) === false) fallbackTile(gx, gy, ch);
      } else if (e.text) {
        const t = new PIXI.Text({
          text: e.text,
          style: { fontSize: 40, fill: 0xffd21f, fontWeight: 'bold',
                   stroke: { color: 0x111111, width: 5 } } });
        t.anchor.set(0.5);
        t.position.set(gx * TILE + TILE / 2, gy * TILE + TILE / 2);
        board.addChild(t);
      } else if (!e.base) {
        fallbackTile(gx, gy, ch);
      }
    }
  }

  document.getElementById('subtitle').textContent =
    'level ' + levelName + ' (' + COLS + 'x' + ROWS + ', source: ' +
    (level.source || 'unknown') + ') — ' + spriteNames.size + ' sprites' +
    (missing.size ? ', ' + missing.size + ' MISSING' : ', none missing');
  document.getElementById('dbg-level').textContent = levelName;
  document.getElementById('dbg-state').textContent =
    COLS + 'x' + ROWS + ' rendered';

  document.body.dataset.ready = levelName;
  document.title = 'ready:' + levelName + ' — Game';
})();
