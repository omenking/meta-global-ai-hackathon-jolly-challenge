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
  const embed = params.get('embed') === '1';
  if (embed) document.body.classList.add('embed');
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
  spriteNames.add('jolly-fall.png');
  const textures = {};
  const missing = new Set();
  await Promise.all([...spriteNames].map(async (name) => {
    try {
      textures[name] = await PIXI.Assets.load('level-sprites/' + name);
    } catch (err) {
      missing.add(name);
    }
  }));

  // Compact in-GUI bar above the playzone (like TIME in the
  // full-level reference): the board never sits under the UI.
  const HUD_H = 52;
  const app = new PIXI.Application();
  await app.init({ width: embed ? window.innerWidth : COLS * TILE,
    height: embed ? window.innerHeight : HUD_H + ROWS * TILE, background: '#111' });
  document.getElementById('stage').appendChild(app.canvas);
  const scale = TILE / 512;
  const board = new PIXI.Container();
  if (!embed) board.position.set(0, HUD_H);
  app.stage.addChild(board);
  // Embed: keep the board's true aspect ratio at any window size —
  // scale to fit and centre (letterbox), refitting on resize. The
  // canvas is never CSS-stretched to the container.
  let hudReady = false;
  function fitBoard() {
    if (!embed) return;
    app.renderer.resize(window.innerWidth, window.innerHeight);
    const availH = Math.max(1, window.innerHeight - HUD_H);
    const fit = Math.min(window.innerWidth / (COLS * TILE),
      availH / (ROWS * TILE));
    board.scale.set(fit);
    board.position.set((window.innerWidth - COLS * TILE * fit) / 2,
      HUD_H + (availH - ROWS * TILE * fit) / 2);
    if (hudReady) layoutHud();
  }
  fitBoard();
  if (embed) window.addEventListener('resize', fitBoard);

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
  // Compact bar above the playzone: TIME always; at loss the
  // retry message and Restart button join it — never over the board.
  const hudBar = new PIXI.Container();
  const hudBg = new PIXI.Graphics();
  hudBar.addChild(hudBg);
  const hudTimer = new PIXI.Text({ text: 'TIME 2:00', style: {
    fontSize: 24, fill: 0xffffff, fontWeight: 'bold',
    stroke: { color: 0x111111, width: 4 } } });
  hudTimer.position.set(12, 12);
  hudBar.addChild(hudTimer);
  const retryGroup = new PIXI.Container();
  retryGroup.visible = false;
  const retryMsg = new PIXI.Text({ text: "Time's up \u2014 you lost!", style: {
    fontSize: 20, fill: 0xff8080, fontWeight: 'bold' } });
  retryMsg.anchor.set(1, 0);
  retryGroup.addChild(retryMsg);
  const retryBtnBg = new PIXI.Graphics();
  retryBtnBg.eventMode = 'static';
  retryBtnBg.cursor = 'pointer';
  retryBtnBg.on('pointertap', () => restartLevel());
  retryGroup.addChild(retryBtnBg);
  const retryBtnText = new PIXI.Text({ text: 'Restart', style: {
    fontSize: 19, fill: 0xffffff, fontWeight: 'bold' } });
  retryBtnText.anchor.set(0.5);
  retryBtnText.eventMode = 'none';
  retryGroup.addChild(retryBtnText);
  hudBar.addChild(retryGroup);
  app.stage.addChild(hudBar);
  function layoutHud() {
    const w = app.renderer.width;
    hudBg.clear();
    hudBg.rect(0, 0, w, HUD_H).fill(0x181818);
    hudBg.rect(0, HUD_H - 2, w, 2).fill(0x444444);
    retryBtnBg.clear();
    retryBtnBg.roundRect(w - 132, 8, 120, 36, 6)
      .fill(0xc00000).stroke({ width: 1, color: 0xffffff });
    retryBtnText.position.set(w - 72, 26);
    retryMsg.position.set(w - 148, 14);
  }
  layoutHud();
  hudReady = true;
  function fmtHud(totalSeconds) {
    const v = Math.max(0, Math.floor(totalSeconds));
    return Math.floor(v / 60) + ':' + String(v % 60).padStart(2, '0');
  }
  function drawHud(elapsedS, limitS) {
    hudTimer.text = 'TIME ' + (limitS === null ? fmtHud(elapsedS)
      : fmtHud(limitS - elapsedS));
  }
  function renderState() {
    if (playerSprite) {
      playerSprite.position.set(state.player.x * TILE,
        state.player.y * TILE);
      // Fallen pose while the run is lost, normal pose otherwise.
      const pose = state.status === 'lost' && textures['jolly-fall.png']
        ? textures['jolly-fall.png'] : textures['jolly.png'];
      if (pose && playerSprite.texture !== pose) playerSprite.texture = pose;
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
    const statusEl = document.getElementById('dbg-status');
    if (statusEl) statusEl.textContent = state.status || 'playing';
    retryGroup.visible = state.status === 'lost';
    drawHud(state.elapsed_s, state.time_limit_s);
  }
  renderState();

  // Session recording starts with the playable build: the header is
  // flushed before any input, every step flushes, and End / pagehide
  // closes the file — no play is ever unrecorded.
  let now = new Date();
  const stamp = now.toISOString().replace(/[^0-9]/g, '').slice(0, 14);
  let sessionId = forkSeed ? forkSeed.id :
    'game-' + levelName + '-' + stamp + '-' +
    Math.random().toString(36).slice(2, 8);
  // No session exists until the first move: refreshes and idle
  // viewing must not create junk session files, and the session
  // clock starts at that first move, not at page load.
  let recorder = null;
  function ensureRecorder() {
    if (recorder) return recorder;
    recorder = window.GameSession.createRecorder({
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
    }
    document.getElementById('dbg-session').textContent =
      sessionId + ' (' + recorder.header.created_by + ')' +
      (forkSeed ? ' forked from ' + forkSeed.header.forked_from : '');
    return recorder;
  }
  if (forkSeed) {
    state = window.GameReplay.buildStates(
      window.GameCore, level, levelName, forkSeed.records).slice(-1)[0] || state;
    renderState();
  }
  document.getElementById('dbg-session').textContent =
    'no session yet — move to start one';
  function flushSession(beacon) {
    if (!recorder) return;
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
    if (!recorder || recorder.isEnded()) return;
    recorder.end(result || 'quit', { time_left: state.time_left_s });
    flushSession(false);
    document.getElementById('dbg-session').textContent =
      sessionId + ' — ended (' + (result || 'quit') + ')';
  }
  document.getElementById('btn-end-session').addEventListener('click', () => endSession('quit'));
  // Restart: restore the initial state (position, orbs, keys and
  // timer all live in GameCore.initialState) and start a new
  // recorded session on the next move. The old session is closed
  // first (as 'lost' if it already expired, else 'quit').
  function restartLevel() {
    if (window.__replayActive) return;
    if (recorder && !recorder.isEnded()) endSession('quit');
    recorder = null;
    forkSeed = null;
    inputLog.length = 0;
    now = new Date();
    sessionId = 'game-' + levelName + '-' +
      now.toISOString().replace(/[^0-9]/g, '').slice(0, 14) + '-' +
      Math.random().toString(36).slice(2, 8);
    sessionStartTs = null;
    state = window.GameCore.initialState(level, levelName);
    document.getElementById('dbg-input').textContent = '\u2014';
    document.getElementById('dbg-replay').textContent = '\u2014';
    document.getElementById('dbg-session').textContent =
      'no session yet \u2014 move to start one';
    renderState();
  }
  window.addEventListener('pagehide', () => {
    if (!recorder) return;
    if (!recorder.isEnded()) { recorder.end('quit', { time_left: state.time_left_s }); }
    flushSession(true);
  });

  const inputLog = forkSeed
    ? window.GameReplay.stepsOf(forkSeed.records).map((s) => ({ t_ms: s.t_ms, input: s.input }))
    : [];
  function applyStep(input) {
    ensureRecorder();
    state = window.GameCore.step(state, input);
    inputLog.push({ t_ms: state.t_ms, input: state.last_input });
    recorder.recordStep(state.steps, state.t_ms, state.last_input);
    document.getElementById('dbg-input').textContent =
      String(state.last_input) + ' @ t_ms ' + state.t_ms;
    renderState();
    // End (and flush) a lost run in one write, so the session file
    // cannot land without its lost end line.
    if (state.status === 'lost') endSession('lost');
    else flushSession(false);
  }
  // Idle expiry: when the live clock reaches the limit, record the
  // loss as a step at exactly the limit so replay loses at the same
  // recorded moment — never from an unrecorded wall-clock read alone.
  function expireNow() {
    if (state.status === 'lost' || state.time_limit_s === null ||
        state.time_limit_s === undefined) return;
    applyStep({ t_ms: Math.round(state.time_limit_s * 1000), input: 'timeout' });
  }

  // Keyboard: WASD/arrows register an input, advance the pure step
  // function (which moves the player one tile on floor) with the
  // recorded elapsed t_ms, and show in the debug readout.
  const startedAt = performance.now();
  let sessionStartTs = null;
  function sessionElapsedMs() {
    return forkBaseMs + (sessionStartTs === null
      ? 0 : performance.now() - sessionStartTs);
  }
  // Forked sessions continue the recorded clock: new inputs must carry
  // t_ms at or after the last forked step, never a restarted clock.
  const forkBaseMs = forkSeed
    ? (window.GameReplay.stepsOf(forkSeed.records).slice(-1)[0] || { t_ms: 0 }).t_ms
    : 0;
  (function clockLoop() {
    if (!window.__replayActive) {
      const elapsed = sessionElapsedMs() / 1000;
      drawHud(elapsed, state.time_limit_s);
      const dbg = document.getElementById('dbg-timer');
      if (dbg) dbg.textContent = elapsed.toFixed(1) + 's (live clock)';
      if (sessionStartTs !== null && state.status !== 'lost' &&
          state.time_limit_s !== null && state.time_limit_s !== undefined &&
          elapsed >= state.time_limit_s) {
        expireNow();
      }
    }
    requestAnimationFrame(clockLoop);
  })();
  document.addEventListener('keydown', (ev) => {
    if (/INPUT|TEXTAREA|SELECT/.test(ev.target.tagName)) return;
    if (window.__replayActive) {
      if (ev.key === ' ') { ev.preventDefault(); if (replayTimer) pauseReplay(); else playReplay(); }
      else if (ev.key === 'ArrowLeft') { ev.preventDefault(); pauseReplay(); showReplay(replayIndex - (ev.shiftKey ? 10 : 1)); }
      else if (ev.key === 'ArrowRight') { ev.preventDefault(); pauseReplay(); showReplay(replayIndex + (ev.shiftKey ? 10 : 1)); }
      else if (ev.key === 'Home') { ev.preventDefault(); showReplay(0); }
      else if (ev.key === 'End') { ev.preventDefault(); showReplay(1e9); }
      return;
    }
    if (ev.key === 'r' || ev.key === 'R') {
      ev.preventDefault();
      restartLevel();
      return;
    }
    if (state.status === 'lost') return;
    const input = window.GameCore.inputForKey(ev.key);
    if (!input) return;
    ev.preventDefault();
    if (sessionStartTs === null) sessionStartTs = performance.now();
    applyStep({ t_ms: Math.round(sessionElapsedMs()), input: input });
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
    if (!window.__keepPlayhead) playheadMs = replayStates[replayIndex].t_ms;
  }
  // Continuous time playback: a playhead advances with the wall
  // clock (scaled by viewer speed); steps land exactly at their
  // recorded t_ms and the sprite interpolates between tiles, so
  // time — and the timeline — moves smoothly, not step-by-step.
  let playheadMs = 0, lastFrameTs = 0;
  function pauseReplay() {
    if (replayTimer) { cancelAnimationFrame(replayTimer); replayTimer = null; }
    renderState();
  }
  let replaySpeed = 1;
  function playReplay() {
    pauseReplay();
    if (!replayStates) return;
    if (replayIndex >= replayStates.length - 1) showReplay(0);
    else if (playheadMs < replayStates[replayIndex].t_ms ||
             playheadMs > (replayStates[replayIndex + 1] || {}).t_ms) {
      playheadMs = replayStates[replayIndex].t_ms;
    }
    lastFrameTs = performance.now();
    const loop = (ts) => {
      if (!replayStates) { replayTimer = null; return; }
      playheadMs += (ts - lastFrameTs) * replaySpeed;
      lastFrameTs = ts;
      window.__keepPlayhead = true;
      while (replayIndex < replayStates.length - 1 &&
             replayStates[replayIndex + 1].t_ms <= playheadMs) {
        showReplay(replayIndex + 1);
      }
      window.__keepPlayhead = false;
      const cur = replayStates[replayIndex];
      drawHud(cur.elapsed_s + (playheadMs - cur.t_ms) / 1000, cur.time_limit_s);
      if (replayIndex >= replayStates.length - 1 &&
          playheadMs >= cur.t_ms) { pauseReplay(); return; }
      replayTimer = requestAnimationFrame(loop);
    };
    replayTimer = requestAnimationFrame(loop);
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

  async function forkFromReplay() {
    if (!replayId) { fail('Load a session replay before forking.'); return null; }
    const newId = 'game-' + levelName + '-fork' + replayIndex + '-' +
      Math.random().toString(36).slice(2, 8);
    const res = await fetch('/api/game/sessions/' + encodeURIComponent(replayId) + '/fork', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fork_step: replayIndex, forked_by: actor, id: newId }) });
    if (!res.ok) { fail('Fork failed'); return null; }
    return newId;
  }
  window.__game = {
    loadReplay: loadReplay, playReplay: playReplay, pauseReplay: pauseReplay,
    setReplaySpeed: (s) => { replaySpeed = Number(s) || 1; },
    showReplay: showReplay, forkFromReplay: forkFromReplay,
    togglePlay: () => { if (replayTimer) pauseReplay(); else playReplay(); },
    seekTime: (seconds) => { if (window.__replayRecords) { pauseReplay(); showReplay(window.GameReplay.stepIndexAtTime(window.__replayRecords, seconds)); } },
    getClock: () => ({ started: sessionStartTs !== null, status: state.status, elapsed_s: sessionElapsedMs() / 1000, time_limit_s: state.time_limit_s, time_left_s: Math.max(0, state.time_limit_s - sessionElapsedMs() / 1000) }),
    restart: restartLevel,
    getReplay: () => ({ playing: replayTimer !== null, playhead_ms: playheadMs, id: replayId, index: replayIndex,
      duration_ms: window.__replayRecords ? (window.GameReplay.stepsOf(window.__replayRecords).slice(-1)[0] || { t_ms: 0 }).t_ms : 0,
      step_times: window.__replayRecords ? window.GameReplay.stepsOf(window.__replayRecords).map((s) => s.t_ms) : [],
      steps: replayStates ? replayStates.length - 1 : 0,
      active: replayStates !== null,
      readout: document.getElementById('replay-readout').textContent,
      warning: document.getElementById('replay-warning').textContent }),
    getState: () => state,
    getPlayerSpritePos: () => playerSprite
      ? { x: playerSprite.position.x, y: playerSprite.position.y }
      : null,
    isRetryBarVisible: () => retryGroup.visible,
    getPlayerPose: () => (playerSprite && textures['jolly-fall.png'] &&
      playerSprite.texture === textures['jolly-fall.png']) ? 'fallen' : 'normal',
    get sessionId() { return sessionId; },
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
