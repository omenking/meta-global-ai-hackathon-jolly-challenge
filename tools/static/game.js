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
  const levelName = (params.get('level') || 'test-room').replace(/[^a-zA-Z0-9_-]/g, '');

  // Game menu: only Test Levels are offered for test play (review
  // fix). The full chip1 level is preserved in levels/ and in the
  // Level Preview, outside this menu; an explicit ?level= still
  // loads it. Start launches the chosen Test Level inside the game
  // (same page, new ?level=), starting its session recording.
  (async function fillMenu() {
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
        if (!item.test) continue;
        add(testSel, item);
      }
    } catch (err) {
      add(testSel, { id: 'test-room', name: 'test-room' });
    }
    let menuChoice = levelName;
    testSel.addEventListener('change', () => { menuChoice = testSel.value; });
    document.getElementById('btn-start-level').addEventListener('click', () => {
      const chosen = menuChoice || testSel.value || 'test-room';
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
  let forkSeed = null;
  if (params.get('fork')) {
    try {
      const fres = await fetch('/api/game/sessions/' + encodeURIComponent(params.get('fork')));
      if (fres.ok) {
        const fdata = await fres.json();
        forkSeed = { id: params.get('fork'), records: fdata.records,
                     header: fdata.records[0] };
      }
    } catch (err) { /* fall through to a fresh session */ }
  }
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
      if (e.sprite && ch !== 'P') {
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
  // above is a view of the level (floor under the start tile), and
  // the player sprite + marker below are a view of state — they are
  // repositioned from state.player on every step.
  let state = window.GameCore.initialState(level, levelName);
  let playerSprite = null;
  if (textures['jolly.png']) {
    playerSprite = new PIXI.Sprite(textures['jolly.png']);
    playerSprite.scale.set(scale);
    board.addChild(playerSprite);
  }
  const marker = new PIXI.Graphics();
  board.addChild(marker);
  function renderState() {
    if (playerSprite) {
      playerSprite.position.set(state.player.x * TILE,
        state.player.y * TILE);
    }
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
  const sessionId = forkSeed ? forkSeed.id :
    'game-' + levelName + '-' + stamp + '-' +
    Math.random().toString(36).slice(2, 8);
  const recorder = window.GameSession.createRecorder({
    id: sessionId,
    created_at: now.toISOString(),
    created_by: forkSeed ? forkSeed.header.created_by : (params.get('creator') === 'agent' ? 'agent' : 'human'),
    label: params.get('label') || '',
    level: levelName,
    level_file: 'levels/' + levelName + '.json',
    level_data: level,
    feature: params.get('feature') || (forkSeed ? forkSeed.header.feature : null),
    task: params.get('task') || null,
    engine_version: window.GameCore.VERSION,
    forked_by: forkSeed ? forkSeed.header.forked_by : null,
    forked_from: forkSeed ? forkSeed.header.forked_from : null,
    fork_step: forkSeed ? forkSeed.header.fork_step : null,
  });
  if (forkSeed) {
    const fsteps = window.GameReplay.stepsOf(forkSeed.records);
    for (const s of fsteps) recorder.recordStep(s.n, s.t_ms, s.input);
    state = window.GameReplay.buildStates(
      window.GameCore, level, levelName, forkSeed.records).slice(-1)[0] || state;
    renderState();
  }
  document.getElementById('dbg-session').textContent =
    sessionId + ' (' + recorder.header.created_by + ')' +
    (forkSeed ? ' forked from ' + forkSeed.header.forked_from : '');
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

  const inputLog = forkSeed
    ? window.GameReplay.stepsOf(forkSeed.records).map((s) => ({ t_ms: s.t_ms, input: s.input }))
    : [];
  function applyStep(input) {
    state = window.GameCore.step(state, input);
    inputLog.push({ t_ms: state.t_ms, input: state.last_input });
    recorder.recordStep(state.steps, state.t_ms, state.last_input);
    document.getElementById('dbg-input').textContent =
      String(state.last_input) + ' @ t_ms ' + state.t_ms;
    renderState();
    flushSession(false);
  }

  // Keyboard: WASD/arrows register an input, advance the pure step
  // function (which moves the player one tile on floor) with the
  // recorded elapsed t_ms, and show in the debug readout.
  const startedAt = performance.now();
  document.addEventListener('keydown', (ev) => {
    if (/INPUT|TEXTAREA|SELECT/.test(ev.target.tagName)) return;
    const input = window.GameCore.inputForKey(ev.key);
    if (!input) return;
    ev.preventDefault();
    applyStep({ t_ms: Math.round(performance.now() - startedAt), input: input });
  });
  document.getElementById('btn-replay').addEventListener('click', () => {
    const states = window.GameCore.replay(level, levelName, inputLog);
    const finalDigest = window.GameCore.stateDigest(states[states.length - 1]);
    const liveDigest = window.GameCore.stateDigest(state);
    document.getElementById('dbg-replay').textContent =
      finalDigest === liveDigest
        ? 'match ' + finalDigest + ' (' + inputLog.length + ' inputs)'
        : 'MISMATCH replay ' + finalDigest + ' vs live ' + liveDigest;
  });

  // --- Sessions menu, replay player, annotations, forks ---
  let replayId = null, replayStates = null, replayIndex = 0, replayTimer = null;
  const actor = params.get('creator') === 'agent' ? 'agent' : 'human';
  function replayActive() { return replayStates !== null; }
  function showReplay(index) {
    if (!replayStates) return;
    replayIndex = Math.max(0, Math.min(index, replayStates.length - 1));
    state = replayStates[replayIndex];
    renderState();
    const r = window.GameCore.readout(state);
    document.getElementById('replay-readout').textContent =
      'step ' + r.step + ' pos ' + r.position.x + ',' + r.position.y +
      ' inventory ' + JSON.stringify(r.inventory) + ' orbs_left ' + r.orbs_left +
      ' timer ' + Number(r.timer).toFixed(1) + 's input ' + String(r.input) +
      ' — deep link ?replay=' + replayId + '&t=' + (r.t_ms / 1000);
    document.getElementById('replay-scrub').max = String(replayStates.length - 1);
    document.getElementById('replay-scrub').value = String(replayIndex);
  }
  function pauseReplay() {
    if (replayTimer) { clearTimeout(replayTimer); replayTimer = null; }
  }
  function playReplay() {
    pauseReplay();
    const speed = Number(document.getElementById('replay-speed').value || 1);
    const tick = () => {
      if (!replayStates || replayIndex >= replayStates.length - 1) { pauseReplay(); return; }
      const next = replayIndex + 1;
      replayTimer = setTimeout(() => { showReplay(next); tick(); },
        window.GameReplay.delayMs(
          window.__replayRecords || [], next, speed));
    };
    tick();
  }
  async function loadReplay(id, tSeconds) {
    const res = await fetch('/api/game/sessions/' + encodeURIComponent(id));
    if (!res.ok) { fail('Could not load session ' + id); return; }
    const data = await res.json();
    const header = data.records[0];
    if (header.level && header.level !== levelName) {
      const next = new URLSearchParams(params);
      next.set('level', header.level); next.set('replay', id);
      if (tSeconds !== undefined) next.set('t', String(tSeconds));
      location.search = '?' + next.toString(); return;
    }
    const warns = window.GameReplay.warnings(header, null,
      window.GameCore.VERSION, null, window.GameSession.levelHash, level);
    const warnBox = document.getElementById('replay-warning');
    warnBox.style.display = warns.length ? 'block' : 'none';
    warnBox.textContent = warns.join('; ');
    replayId = id; window.__replayRecords = data.records; window.__replayActive = true;
    replayStates = window.GameReplay.buildStates(
      window.GameCore, level, levelName, data.records);
    const idx = tSeconds === undefined ? 0
      : window.GameReplay.stepIndexAtTime(data.records, tSeconds);
    showReplay(idx);
  }
  async function refreshSessions() {
    const q = new URLSearchParams();
    const map = { 'filter-q': 'q', 'filter-level': 'level',
      'filter-creator': 'creator', 'filter-feature': 'feature',
      'filter-date': 'date', 'filter-result': 'result', 'filter-label': 'label' };
    for (const [el, key] of Object.entries(map)) {
      const v = document.getElementById(el).value.trim();
      if (v) q.set(key, v);
    }
    const res = await fetch('/api/game/sessions?' + q.toString());
    const data = await res.json();
    const list = document.getElementById('sessions-list');
    list.innerHTML = '';
    for (const s of data.sessions || []) {
      const li = document.createElement('li');
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = s.id + ' (' + s.level + ', ' +
        s.created_by + ', ' + (s.result || 'open') + ')' +
        (s.labels && s.labels.length ? ' [' + s.labels.join(',') + ']' : '');
      b.addEventListener('click', () => loadReplay(s.id));
      li.appendChild(b); list.appendChild(li);
    }
  }
  document.getElementById('btn-filter-sessions').addEventListener('click', refreshSessions);
  document.getElementById('btn-replay-play').addEventListener('click', playReplay);
  document.getElementById('btn-replay-pause').addEventListener('click', pauseReplay);
  document.getElementById('btn-step-back').addEventListener('click', () => { pauseReplay(); showReplay(replayIndex - 1); });
  document.getElementById('btn-step-fwd').addEventListener('click', () => { pauseReplay(); showReplay(replayIndex + 1); });
  document.getElementById('replay-scrub').addEventListener('input', (ev) => { pauseReplay(); showReplay(Number(ev.target.value)); });
  document.getElementById('btn-annotate').addEventListener('click', async () => {
    const target = replayId || sessionId;
    const res = await fetch('/api/game/sessions/' + encodeURIComponent(target) + '/annotations', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ author: actor,
        body: document.getElementById('annotate-body').value,
        labels: document.getElementById('annotate-labels').value }) });
    document.getElementById('annotate-status').textContent =
      res.ok ? 'annotation added to ' + target : 'annotation failed';
    if (res.ok) refreshSessions();
  });
  document.getElementById('btn-fork').addEventListener('click', async () => {
    if (!replayId) { fail('Load a session replay before forking.'); return; }
    const newId = 'game-' + levelName + '-fork' + replayIndex + '-' +
      Math.random().toString(36).slice(2, 8);
    const res = await fetch('/api/game/sessions/' + encodeURIComponent(replayId) + '/fork', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fork_step: replayIndex, forked_by: actor, id: newId }) });
    if (!res.ok) { fail('Fork failed'); return; }
    const next = new URLSearchParams(params);
    next.set('level', levelName); next.set('fork', newId);
    next.delete('replay'); next.delete('t');
    location.search = '?' + next.toString();
  });
  refreshSessions();
  if (params.get('replay')) {
    loadReplay(params.get('replay'),
      params.get('t') === null ? undefined : Number(params.get('t')));
  }

  window.__game = {
    getState: () => state,
    getPlayerSpritePos: () => playerSprite
      ? { x: playerSprite.position.x, y: playerSprite.position.y }
      : null,
    sessionId: sessionId,
    endSession: endSession,
    applyStep: applyStep,
    getLog: () => inputLog.slice(),
  };

  document.getElementById('subtitle').textContent =
    'level ' + levelName + ' (' + COLS + 'x' + ROWS + ', source: ' +
    (level.source || 'unknown') + ') — ' + spriteNames.size + ' sprites' +
    (missing.size ? ', ' + missing.size + ' MISSING' : ', none missing');
  document.getElementById('dbg-level').textContent = levelName;

  document.body.dataset.ready = levelName;
  document.title = 'ready:' + levelName + ' — Game';
})();
