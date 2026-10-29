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

  // Game menu: levels and Test Levels come from the server listing;
  // Start launches the chosen one inside the game (same page, new
  // ?level=), which also starts its session recording.
  (async function fillMenu() {
    const levelSel = document.getElementById('menu-level');
    const testSel = document.getElementById('menu-test-level');
    function add(sel, item) {
      const o = document.createElement('option');
      o.value = item.id; o.textContent = item.name || item.id;
      if (item.id === levelName) o.selected = true;
      sel.appendChild(o);
    }
    try {
      const res = await fetch('/api/game/levels');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      for (const item of data.levels || []) {
        add(item.test ? testSel : levelSel, item);
      }
    } catch (err) {
      add(levelSel, { id: 'chip1', name: 'chip1' });
    }
    let menuChoice = levelName;
    levelSel.addEventListener('change', () => { menuChoice = levelSel.value; });
    testSel.addEventListener('change', () => { menuChoice = testSel.value; });
    document.getElementById('btn-start-level').addEventListener('click', () => {
      const chosen = menuChoice || levelSel.value || testSel.value || 'chip1';
      const next = new URLSearchParams(params);
      next.set('level', chosen);
      location.search = '?' + next.toString();
    });
  })();
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

  // Deterministic core: state comes from GameCore only; the board
  // above is a view of the level, this marker is a view of state.
  let state = window.GameCore.initialState(level, levelName);
  const marker = new PIXI.Graphics();
  board.addChild(marker);
  function renderState() {
    marker.clear();
    marker.rect(state.player.x * TILE + 2, state.player.y * TILE + 2,
      TILE - 4, TILE - 4).stroke({ width: 3, color: 0x00c8ff });
    document.getElementById('dbg-player').textContent =
      state.player.x + ', ' + state.player.y;
    document.getElementById('dbg-steps').textContent = String(state.steps);
    document.getElementById('dbg-timer').textContent =
      state.elapsed_s.toFixed(1) + 's (t_ms ' + state.t_ms + ')';
    document.getElementById('dbg-digest').textContent =
      window.GameCore.stateDigest(state);
    document.getElementById('dbg-state').textContent = JSON.stringify(state);
  }
  renderState();

  // Session recording starts with the playable build: the header is
  // flushed before any input, every step flushes, and End / pagehide
  // closes the file — no play is ever unrecorded.
  const now = new Date();
  const stamp = now.toISOString().replace(/[^0-9]/g, '').slice(0, 14);
  const sessionId = 'game-' + levelName + '-' + stamp + '-' +
    Math.random().toString(36).slice(2, 8);
  const recorder = window.GameSession.createRecorder({
    id: sessionId,
    created_at: now.toISOString(),
    created_by: params.get('creator') === 'agent' ? 'agent' : 'human',
    label: params.get('label') || '',
    level: levelName,
    level_file: 'levels/' + levelName + '.json',
    level_data: level,
    feature: params.get('feature') || null,
    task: params.get('task') || null,
  });
  document.getElementById('dbg-session').textContent =
    sessionId + ' (' + recorder.header.created_by + ')';
  function flushSession(beacon) {
    const payload = JSON.stringify({ id: sessionId, content: recorder.toJSONL() });
    if (beacon && navigator.sendBeacon) {
      navigator.sendBeacon('/api/game/sessions',
        new Blob([payload], { type: 'application/json' }));
    } else {
      fetch('/api/game/sessions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: payload, keepalive: true,
      }).catch(() => {});
    }
  }
  function endSession(result) {
    if (recorder.isEnded()) return;
    recorder.end(result || 'quit', { time_left: state.time_left_s });
    flushSession(false);
    document.getElementById('dbg-session').textContent =
      sessionId + ' — ended (' + (result || 'quit') + ')';
  }
  flushSession(false);
  document.getElementById('btn-end-session').addEventListener('click', () => endSession('quit'));
  window.addEventListener('pagehide', () => {
    if (!recorder.isEnded()) { recorder.end('quit', { time_left: state.time_left_s }); }
    flushSession(true);
  });

  window.__game = {
    getState: () => state,
    sessionId: sessionId,
    endSession: endSession,
    applyStep: (input) => {
      state = window.GameCore.step(state, input);
      recorder.recordStep(state.steps, state.t_ms, state.last_input);
      renderState();
      flushSession(false);
    },
  };

  document.getElementById('subtitle').textContent =
    'level ' + levelName + ' (' + COLS + 'x' + ROWS + ', source: ' +
    (level.source || 'unknown') + ') — ' + spriteNames.size + ' sprites' +
    (missing.size ? ', ' + missing.size + ' MISSING' : ', none missing');
  document.getElementById('dbg-level').textContent = levelName;

  document.body.dataset.ready = levelName;
  document.title = 'ready:' + levelName + ' — Game';
})();
