// Game page: renders a chosen level (rows + legend) exactly as the
// level preview does. Rendering is a view of the level data; game
// state (deterministic core, sessions, input) layers on top of this.
(async function () {
  'use strict';
  const errorBox = document.getElementById('error');
  function fail(msg) {
    // Never leave an error page hidden under the wipe cover.
    document.documentElement.classList.remove('wipe-in');
    errorBox.style.display = 'block';
    errorBox.textContent = msg;
    document.getElementById('subtitle').textContent = 'failed to load';
  }
  if (!window.PIXI) { fail('PixiJS failed to load (vendor/pixi.min.js).'); return; }

  const params = new URLSearchParams(location.search);
  const embed = params.get('embed') === '1';
  if (embed) document.body.classList.add('embed');
  const levelName = (params.get('level') || 'test-room').replace(/[^a-zA-Z0-9_-]/g, '');

  // Wipe transition (view only): arriving via a warp starts fully
  // covered from first paint (html.wipe-in, set by the inline head
  // script in game.html), then revealWipe() slides the cover away
  // once this level is ready. Plain loads never cover.
  const wipeEl = document.getElementById('wipe');
  const wipeIncoming = params.get('wipe') === '1';
  function revealWipe() {
    if (!wipeIncoming) return;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      // Removing the flag re-enables the CSS transition; the
      // reveal class then carries the cover off the far edge.
      document.documentElement.classList.remove('wipe-in');
      wipeEl.classList.add('reveal');
      setTimeout(() => {
        wipeEl.style.transition = 'none';
        wipeEl.classList.remove('reveal');
        requestAnimationFrame(() => { wipeEl.style.transition = ''; });
      }, 500);
    }));
  }

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
  // Renderer-owned world scale: a level's own tile value never changes
  // the on-screen tile size (fixed-world-scale; movement-room native).
  const rows = level.rows, legend = level.legend,
    TILE = window.GameWorldScale ? window.GameWorldScale.WORLD_TILE_PX : (level.tile || 64);
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
  // Pack-carried assets: loaded packs declare the sprite/icon names
  // they need (keys, locks, items); no hardcoded colour list here.
  // Bundled assets load from their pack folder, shared assets from
  // level-sprites/; the registry decides which URL each name gets.
  const urlByName = {};
  if (window.GameCore.assetPathsForLevel) {
    for (const a of window.GameCore.assetPathsForLevel(level)) {
      urlByName[a.name] = a.url;
    }
  }
  if (window.GameCore.assetsForLevel) {
    for (const name of window.GameCore.assetsForLevel(level)) spriteNames.add(name);
  }
  const textures = {};
  const missing = new Set();
  await Promise.all([...spriteNames].map(async (name) => {
    try {
      textures[name] = await PIXI.Assets.load(urlByName[name] || 'level-sprites/' + name);
    } catch (err) {
      missing.add(name);
    }
  }));

  // HUD art: blue digit sprites, black labels and the digit-box
  // backplate, derived from assets/published/gui by the prep script.
  const guiTextures = { digits: [], labels: {}, backplate: null };
  {
    const guiLoads = [];
    for (let d = 0; d <= 9; d++) {
      guiLoads.push(PIXI.Assets.load('gui-sprites/digit-' + d + '.png')
        .then((t) => { guiTextures.digits[d] = t; })
        .catch(() => { missing.add('digit-' + d + '.png'); }));
    }
    for (const name of ['level', 'time', 'orbs']) {
      guiLoads.push(PIXI.Assets.load('gui-sprites/label-' + name + '.png')
        .then((t) => { guiTextures.labels[name] = t; })
        .catch(() => { missing.add('label-' + name + '.png'); }));
    }
    guiLoads.push(PIXI.Assets.load('gui-sprites/backplate.png')
      .then((t) => { guiTextures.backplate = t; })
      .catch(() => { missing.add('backplate.png'); }));
    await Promise.all(guiLoads);
  }

  // Right-hand HUD column (the original game's side panel, per
  // scratchpad/full-level-ui.png): readouts stack in a reserved
  // column beside the board, so the board never sits under the UI.
  // HUD_H is the column's design height; it scales to fit the canvas.
  const HUD_W = 184;
  const HUD_H = 668;
  // Camera viewport (renderer-only): at most VIEW tiles are shown;
  // levels up to 64x64 scroll, smaller levels render whole as before.
  const VIEW = window.GameCamera
    ? window.GameCamera.viewSize(COLS, ROWS) : { w: COLS, h: ROWS };
  const app = new PIXI.Application();
  await app.init({ width: embed ? window.innerWidth
      : VIEW.w * TILE + HUD_W * Math.min(1, (VIEW.h * TILE) / HUD_H),
    height: embed ? window.innerHeight : VIEW.h * TILE, background: '#111' });
  document.getElementById('stage').appendChild(app.canvas);
  const scale = TILE / 512;
  const board = new PIXI.Container();
  app.stage.addChild(board);
  let hudReady = false;
  let hudScale = 1;
  // Embed: fixed world scale at any window size — centre the view in
  // the area left of the HUD column (letterbox), refitting on resize.
  // The canvas is never CSS-stretched to the container.
  let camPos = { x: 0, y: 0 };
  // In embed the camera frames only the tiles that fully fit the
  // window at the fixed scale (visibleView); framing the full MAX
  // view would crop its edges — and the player in them — off screen.
  // Non-embed canvas is sized to VIEW, so VIEW fits exactly there.
  function effectiveView() {
    if (!embed || !window.GameWorldScale) return VIEW;
    return window.GameWorldScale.visibleView({
      availW: Math.max(1, window.innerWidth - HUD_W * hudScale),
      availH: Math.max(1, window.innerHeight),
      cols: COLS, rows: ROWS, maxW: VIEW.w, maxH: VIEW.h });
  }
  function computeCam(player) {
    if (!window.GameCamera || !player) return camPos;
    const view = effectiveView();
    camPos = window.GameCamera.compute({ cols: COLS, rows: ROWS,
      viewW: view.w, viewH: view.h, player: player });
    return camPos;
  }
  function fitBoard() {
    if (!embed) { updateBoardTransform(); return; }
    app.renderer.resize(window.innerWidth, window.innerHeight);
    if (hudReady) layoutHud();
    // Fixed world scale: tiles are WORLD_TILE_PX on screen in every
    // level. The HUD only reserves its column width (its own sizing
    // is untouched); it never sets the board scale.
    const availW = Math.max(1, window.innerWidth - HUD_W * hudScale);
    const availH = Math.max(1, window.innerHeight);
    const view = effectiveView();
    const t = window.GameWorldScale.boardTransform({
      availW: availW, availH: availH, viewW: view.w, viewH: view.h,
      camX: camPos.x, camY: camPos.y });
    board.scale.set(t.scaleX, t.scaleY);
    board.position.set(t.x, t.y);
  }
  function updateBoardTransform() {
    // Non-embed: board at the same fixed tile size (canvas is sized
    // in TILE units, TILE === WORLD_TILE_PX), offset by the camera.
    if (embed) { fitBoard(); return; }
    board.scale.set(1, 1);
    board.position.set(-camPos.x * TILE, -camPos.y * TILE);
  }
  fitBoard();
  if (embed) window.addEventListener('resize', fitBoard);

  // Static board + dynamicTiles tracking live in view/board.js.
  // Tile defs (carrying pack sprites/glyphs) resolve via GameCore.
  const defMap = window.GameCore.levelDefMap
    ? window.GameCore.levelDefMap(level) : {};
  const dynamicTiles = window.GameBoardView.createBoardView({
    PIXI: PIXI, board: board, textures: textures, rows: rows,
    legend: legend, TILE: TILE, scale: scale, COLS: COLS, ROWS: ROWS,
    getDef: function (ch) {
      const id = defMap[ch];
      return id && window.GameCore.getTileDef
        ? window.GameCore.getTileDef(id) : null;
    },
  }).dynamicTiles;

  // Deterministic core: state comes from GameCore only; the board
  // above is a view of the level (floor under the start tile), and
  // the player sprite + marker below are a view of state — they are
  // repositioned from state.player on every step.
  let state = window.GameCore.initialState(level, levelName);
  // Peep hole (mech-60): the next room (rows above the divider) is
  // drawn black until entered in person; while peeping the shade
  // lifts and the camera pans up. View only — state stays kernel.
  const peepShade = new PIXI.Graphics();
  board.addChild(peepShade);
  let playerSprite = null;
  if (textures['jolly.png']) {
    playerSprite = new PIXI.Sprite(textures['jolly.png']);
    playerSprite.scale.set(scale);
    board.addChild(playerSprite);
  }
  // Non-player actors (patrollers etc.): one sprite each, drawn
  // with the sprite of the actor def and repositioned from state
  // on every step, like the player sprite below.
  // Non-player actors (sleepers etc.): one sprite each, drawn
  // with the sprite of the actor def and repositioned from state
  // on every step, like the player sprite below. A sleeper swaps
  // to its awake sprite once any orb has woken it.
  const actorSprites = [];
  for (const actor of state.actors || []) {
    if (actor.id === 'player') continue;
    const def = window.GameCore.getTileDef
      ? window.GameCore.getTileDef(actor.def) : null;
    const tex = def && def.sprite ? textures[def.sprite] : null;
    if (!tex) continue;
    const spr = new PIXI.Sprite(tex);
    spr.scale.set(scale);
    spr.position.set(actor.x * TILE, actor.y * TILE);
    board.addChild(spr);
    actorSprites.push({ id: actor.id, sprite: spr });
    actorSprites.push({ id: actor.id, def: actor.def, sprite: spr });
  let botSprite = null;
  if (textures['mule-bot.png']) {
    botSprite = new PIXI.Sprite(textures['mule-bot.png']);
    botSprite.scale.set(scale);
    board.addChild(botSprite);
  }
  const marker = new PIXI.Graphics();
  board.addChild(marker);
  // Revealed mimics patrol away from their placed tile, so pooled
  // sprites follow the 'N' cells in the projected grid each frame.
  const mimicPool = [];
  for (let i = 0; i < 4; i++) {
    const spr = new PIXI.Sprite(textures['mimic-revealed.png']
      || PIXI.Texture.EMPTY);
    spr.scale.set(scale);
    spr.visible = false;
    board.addChild(spr);
    mimicPool.push(spr);
  }
  // Dark room (mech-51): tiles beyond the two-tile light radius
  // are not drawn at all. The overlay blacks out every board tile
  // outside the radius; the HUD column is a separate stage child
  // and still shows. View-only: movement, orbs and the gate read
  // GameCore state exactly as in a lit room.
  const darkOverlay = new PIXI.Graphics();
  board.addChild(darkOverlay);
  // Map tile overlay (mech-55): the brief whole-level reveal is a
  // view of state.flags only; it shows while the recorded step
  // clock is inside the three-second window and play continues.
  let mapOverlay = null;
  if (textures['map-overlay.png']) {
    mapOverlay = new PIXI.Sprite(textures['map-overlay.png']);
    mapOverlay.width = COLS * TILE; mapOverlay.height = ROWS * TILE;
    mapOverlay.alpha = 0.88; mapOverlay.visible = false;
    board.addChild(mapOverlay);
  }
  // Ghost pack: replay ghosts are a view of state.flags positions,
  // redrawn from state on every step like the player sprite.
  const ghostLayer = new PIXI.Container();
  board.addChild(ghostLayer);
  // Enemy actors (mirror pack patrollers/guards) are state actors,
  // not tiles: one labelled marker per non-player actor, following
  // state on every render like the player sprite does.
  const enemySprites = [];
  for (const a of state.actors) {
    if (a.id === 'player') continue;
    const et = new PIXI.Text({ text: 'E', style: {
      fontSize: 40, fill: 0xff4444, fontWeight: 'bold',
      stroke: { color: 0x111111, width: 5 } } });
    et.anchor.set(0.5);
    board.addChild(et);
    enemySprites.push({ id: a.id, sprite: et });
  }
  // Right-hand column: grey panel like the original side panel.
  // Each readout is a label sprite over a backplate box holding
  // three blue digit sprites; values come only from GameHud helpers
  // over GameCore state. The retry message + Restart live at the
  // foot of the column at loss — never over the board.
  const hudColumn = new PIXI.Container();
  const hudBg = new PIXI.Graphics();
  hudColumn.addChild(hudBg);
  app.stage.addChild(hudColumn);
  const hudSections = [];
  const hudValues = { timer: 0, orbs: 0, level: 0, inventory: [],
    moves: 0 };
  function addHudSection(group, height) {
    hudColumn.addChild(group);
    hudSections.push({ group: group, height: height });
  }
  function insertHudSection(group, height, index) {
    hudColumn.addChild(group);
    hudSections.splice(index, 0, { group: group, height: height });
  }
  function makeReadout(labelName) {
    const group = new PIXI.Container();
    const labelTex = guiTextures.labels[labelName];
    if (labelTex) {
      const label = new PIXI.Sprite(labelTex);
      label.width = 150; label.height = 150 * labelTex.height / labelTex.width;
      label.position.set((HUD_W - 150) / 2, 0);
      group.addChild(label);
    }
    if (guiTextures.backplate) {
      const plate = new PIXI.Sprite(guiTextures.backplate);
      plate.width = 160; plate.height = 102;
      plate.position.set((HUD_W - 160) / 2, 24);
      group.addChild(plate);
    } else {
      const plateBg = new PIXI.Graphics();
      plateBg.roundRect((HUD_W - 160) / 2, 24, 160, 102, 10).fill(0x111111);
      group.addChild(plateBg);
    }
    const digitSprites = [];
    for (let i = 0; i < 3; i++) {
      if (!guiTextures.digits[0]) break;
      const s = new PIXI.Sprite(guiTextures.digits[0]);
      s.width = 36; s.height = 64;
      s.position.set(HUD_W / 2 - 57 + i * 42, 43);
      group.addChild(s);
      digitSprites.push(s);
    }
    const text = new PIXI.Text({ text: '000', style: {
      fontSize: 44, fill: 0x2f7bff, fontWeight: 'bold' } });
    text.anchor.set(0.5);
    text.position.set(HUD_W / 2, 75);
    text.visible = digitSprites.length === 0;
    group.addChild(text);
    let shown = -1;
    return { group: group, height: 138, text: text,
      set: function (value) {
        const v = Math.max(0, Math.min(999, Math.floor(value) || 0));
        if (v === shown) return;
        shown = v;
        const digits = window.GameHud.digitsFor(v);
        for (let i = 0; i < digitSprites.length; i++) {
          const tex = guiTextures.digits[digits[i]];
          if (tex && digitSprites[i].texture !== tex) digitSprites[i].texture = tex;
        }
        text.text = String(v).padStart(3, '0');
      } };
  }
  const timeReadout = makeReadout('time');
  // Held icon (still pack): shown beside the timer while held.
  const heldIcon = textures['timer-held.png']
    ? new PIXI.Sprite(textures['timer-held.png']) : null;
  if (heldIcon) {
    heldIcon.width = 36; heldIcon.height = 36;
    heldIcon.position.set(HUD_W - 44, 8);
    heldIcon.visible = false;
    timeReadout.group.addChild(heldIcon);
  }
  const hudTimer = timeReadout.text;
  // Frozen timer display (hourglass pack gui asset): shown over
  // the time readout while the level timer is frozen.
  const frozenBadge = textures['timer-frozen.png']
    ? new PIXI.Sprite(textures['timer-frozen.png']) : null;
  if (frozenBadge) {
    frozenBadge.width = 40; frozenBadge.height = 40;
    frozenBadge.position.set(HUD_W - 48, 28);
    frozenBadge.visible = false;
    timeReadout.group.addChild(frozenBadge);
  }
  addHudSection(timeReadout.group, timeReadout.height);
  const orbsReadout = makeReadout('orbs');
  insertHudSection(orbsReadout.group, orbsReadout.height, 1);
  const levelReadout = makeReadout('level');
  insertHudSection(levelReadout.group, levelReadout.height, 0);
  // Move counter (mech-79-move-door): shown only in move-door
  // rooms, where the movedoor pack maintains the movedoor:moves
  // counter; the value comes from GameCore state like every other
  // readout, and the pack's bundled counter icon labels it.
  let movesReadout = null;
  if (Object.values(defMap).includes('movedoor:door')) {
    movesReadout = makeReadout('moves');
    if (textures['move-counter.png']) {
      const icon = new PIXI.Sprite(textures['move-counter.png']);
      icon.width = 44; icon.height = 44;
      icon.position.set(HUD_W / 2 - 22, 0);
      movesReadout.group.addChild(icon);
    } else {
      const movesLabel = new PIXI.Text({ text: 'MOVES', style: {
        fontSize: 15, fill: 0x111111, fontWeight: 'bold' } });
      movesLabel.anchor.set(0.5, 0);
      movesLabel.position.set(HUD_W / 2, 2);
      movesReadout.group.addChild(movesLabel);
    }
    insertHudSection(movesReadout.group, movesReadout.height, 2);
  }
  // Inventory: no box asset exists, so the 8 slots are drawn here
  // (dark inset squares) in the column foot; held keys show their
  // colour icon from the derived key sprites.
  const inventoryGroup = new PIXI.Container();
  {
    const invLabel = new PIXI.Text({ text: 'INVENTORY', style: {
      fontSize: 15, fill: 0x111111, fontWeight: 'bold' } });
    invLabel.anchor.set(0.5, 0);
    invLabel.position.set(HUD_W / 2, 0);
    inventoryGroup.addChild(invLabel);
  }
  const inventoryIcons = [];
  for (let i = 0; i < 8; i++) {
    const slotBg = new PIXI.Graphics();
    const sx = 12 + (i % 4) * 41, sy = 22 + Math.floor(i / 4) * 41;
    slotBg.roundRect(sx, sy, 36, 36, 5).fill(0x222222)
      .stroke({ width: 2, color: 0x777777 });
    inventoryGroup.addChild(slotBg);
    const icon = new PIXI.Sprite(textures['key.png'] || PIXI.Texture.EMPTY);
    icon.width = 30; icon.height = 30;
    icon.position.set(sx + 3, sy + 3);
    icon.visible = false;
    inventoryGroup.addChild(icon);
    inventoryIcons.push(icon);
  }
  function setInventory(slots) {
    for (let i = 0; i < inventoryIcons.length; i++) {
      const color = slots[i];
      const tex = color === 'dash' && textures['dash-charge.png']
        ? textures['dash-charge.png']
        : (color && textures['key_' + color + '.png']
          ? textures['key_' + color + '.png']
          : (color ? textures['key.png'] : null));
      inventoryIcons[i].visible = !!tex;
      if (tex && inventoryIcons[i].texture !== tex) inventoryIcons[i].texture = tex;
    }
  }
  insertHudSection(inventoryGroup, 104, 3);
  const retryGroup = new PIXI.Container();
  retryGroup.visible = false;
  const retryMsg = new PIXI.Text({ text: "Time's up \u2014 you lost!", style: {
    fontSize: 17, fill: 0xa00000, fontWeight: 'bold' } });
  retryMsg.anchor.set(0.5, 0);
  retryMsg.position.set(HUD_W / 2, 0);
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
  addHudSection(retryGroup, 84);
  // Win screen (warp-and-levels, last level): stepping on the warp
  // with no next level wins the run; the message + Play again live
  // at the foot of the HUD column, never over the board.
  const winGroup = new PIXI.Container();
  winGroup.visible = false;
  const winMsg = new PIXI.Text({ text: 'You win!', style: {
    fontSize: 20, fill: 0x0a6b00, fontWeight: 'bold' } });
  winMsg.anchor.set(0.5, 0);
  winMsg.position.set(HUD_W / 2, 0);
  winGroup.addChild(winMsg);
  const winBtnBg = new PIXI.Graphics();
  winBtnBg.eventMode = 'static';
  winBtnBg.cursor = 'pointer';
  winBtnBg.on('pointertap', () => restartLevel());
  winGroup.addChild(winBtnBg);
  const winBtnText = new PIXI.Text({ text: 'Play again', style: {
    fontSize: 19, fill: 0xffffff, fontWeight: 'bold' } });
  winBtnText.anchor.set(0.5);
  winBtnText.eventMode = 'none';
  winGroup.addChild(winBtnText);
  addHudSection(winGroup, 84);
  function layoutHud() {
    const w = app.renderer.width, h = app.renderer.height;
    hudScale = Math.min(1, h / HUD_H);
    hudColumn.scale.set(hudScale);
    hudColumn.position.set(w - HUD_W * hudScale, 0);
    hudBg.clear();
    hudBg.rect(0, 0, HUD_W, h / hudScale).fill(0xbdbdbd);
    hudBg.rect(0, 0, 3, h / hudScale).fill(0x8a8a8a);
    let y = 14;
    for (const sec of hudSections) {
      // Finish sections (retry / win) take column space only while
      // shown, so the readouts keep their scale on short boards.
      if ((sec.group === retryGroup || sec.group === winGroup) &&
          !sec.group.visible) continue;
      sec.group.position.set(0, y);
      y += sec.height + 10;
    }
    retryBtnBg.clear();
    retryBtnBg.roundRect(HUD_W / 2 - 60, 26, 120, 38, 6)
      .fill(0xc00000).stroke({ width: 1, color: 0xffffff });
    retryBtnText.position.set(HUD_W / 2, 45);
    winBtnBg.clear();
    winBtnBg.roundRect(HUD_W / 2 - 60, 26, 120, 38, 6)
      .fill(0x0a6b00).stroke({ width: 1, color: 0xffffff });
    winBtnText.position.set(HUD_W / 2, 45);
  }
  layoutHud();
  hudReady = true;
  if (embed) layoutHud();
  function fmtHud(totalSeconds) {
    const v = Math.max(0, Math.floor(totalSeconds));
    return Math.floor(v / 60) + ':' + String(v % 60).padStart(2, '0');
  }
  function drawHud(elapsedS, limitS) {
    const left = limitS === null || limitS === undefined
      ? elapsedS : Math.max(0, limitS - elapsedS);
    hudValues.timer = Math.floor(left);
    timeReadout.set(left);
    hudTimer.text = String(hudValues.timer).padStart(3, '0');
  }
  // Info-tile banner: shown once, on the step that first reads a
  // tile (the info:shown counter increments); hidden once the
  // player steps off the tile. View-only: state stays in GameCore.
  let bannerCountSeen = 0;
  function renderState() {
    computeCam(state.player);
    // Peep pan: while the preview runs, shift the view up toward
    // the next room (clamped at the level edge).
    const peepFlags = state.flags || {};
    if (peepFlags['peep:active']) {
      camPos = { x: camPos.x, y: Math.max(0, camPos.y - 3),
        w: camPos.w, h: camPos.h };
    }
    updateBoardTransform();
    // Black next room until entered in person or peeped into.
    peepShade.clear();
    const dividerY = peepFlags['peep:divider_y'];
    if (typeof dividerY === 'number' && dividerY > 0
        && !peepFlags['peep:active']
        && !peepFlags['peep:entered_next']) {
      peepShade.rect(0, 0, COLS * TILE, dividerY * TILE)
        .fill(0x000000);
    }
    if (playerSprite) {
      playerSprite.position.set(state.player.x * TILE,
        state.player.y * TILE);
      // Fallen pose while the run is lost, launching pose on the
      // step a bounce launch lands, normal pose otherwise.
      const launching = state.status !== 'lost' &&
        (state.last_effects || []).indexOf('bounceLaunch') >= 0 &&
        textures['jolly-launching.png'];
      const pose = state.status === 'lost' && textures['jolly-fall.png']
        ? textures['jolly-fall.png']
        : (launching ? textures['jolly-launching.png'] : textures['jolly.png']);
      // Fallen pose while the run is lost, straining pose while the
      // player is mid-strain on a sticky tile, normal pose otherwise.
      const pActor = state.actors &&
        state.actors.find((a) => a.id === 'player');
      const straining = !!(pActor && pActor.flags &&
        pActor.flags.sticky_strained);
      const pose = state.status === 'lost' && textures['jolly-fall.png']
        ? textures['jolly-fall.png']
        : (straining && textures['jolly-straining.png']
          ? textures['jolly-straining.png'] : textures['jolly.png']);
      // Fallen pose while the run is lost, dashing pose on the step
      // a dash fired, normal pose otherwise.
      const pActor = (state.actors || []).find((a) => a.id === 'player');
      const dashed = pActor && pActor.flags
        && pActor.flags.dash_step === state.steps;
      const pose = state.status === 'lost' && textures['jolly-fall.png']
        ? textures['jolly-fall.png']
        : (dashed && textures['jolly-dashing.png']
          ? textures['jolly-dashing.png'] : textures['jolly.png']);
      // Fallen pose while the run is lost, wading pose while
      // standing on deep water, normal pose otherwise.
      const onDeep = state.terrain && state.terrain[state.player.y] &&
        state.terrain[state.player.y][state.player.x] === 'deep:water';
      const pose = state.status === 'lost' && textures['jolly-fall.png']
        ? textures['jolly-fall.png']
        : (onDeep && textures['jolly-wading.png']
          ? textures['jolly-wading.png'] : textures['jolly.png']);
        : (state.counters && state.counters['lantern:held'] > 0
          && textures['jolly-with-lantern.png']
          ? textures['jolly-with-lantern.png'] : textures['jolly.png']);
      // Fallen pose while the run is lost, peeping pose while the
      // peep preview holds Jolly on the hole, normal pose otherwise.
      const pose = state.status === 'lost' && textures['jolly-fall.png']
        ? textures['jolly-fall.png']
        : ((state.flags || {})['peep:active'] && textures['jolly-peeping.png']
          ? textures['jolly-peeping.png'] : textures['jolly.png']);
      // Fallen pose while the run is lost, thinking pose while the
      // timer is held on a still tile, normal pose otherwise.
      const pose = state.status === 'lost' && textures['jolly-fall.png']
        ? textures['jolly-fall.png']
        : (state.flags && state.flags['still:held'] && textures['jolly-still.png']
          ? textures['jolly-still.png'] : textures['jolly.png']);
      if (pose && playerSprite.texture !== pose) playerSprite.texture = pose;
    }
    for (const as of actorSprites) {
      const actor = (state.actors || []).find((a) => a.id === as.id);
      if (actor) as.sprite.position.set(actor.x * TILE, actor.y * TILE);
    // Chaser actors are a view of state.actors, like the player.
    for (const actor of state.actors || []) {
      if (actor.def !== 'chaser:chaser') continue;
      let spr = renderState._chasers && renderState._chasers.get(actor.id);
      if (!spr) {
        const tex = textures['chaser.png'];
        if (!tex) continue;
        spr = new PIXI.Sprite(tex);
        spr.scale.set(scale);
        board.addChild(spr);
        (renderState._chasers = renderState._chasers
          || new Map()).set(actor.id, spr);
      }
      spr.position.set(actor.x * TILE, actor.y * TILE);
      const tex = actor.flags && actor.flags.blocked
        ? textures['chaser-blocked.png'] : textures['chaser.png'];
      if (tex && spr.texture !== tex) spr.texture = tex;
      if (!actor) continue;
      as.sprite.position.set(actor.x * TILE, actor.y * TILE);
      if (as.def === 'sleeper:sleeper') {
        const texName = state.flags && state.flags['sleeper:awake']
          ? 'sleeper-awake.png' : 'sleeper-asleep.png';
        const tex = textures[texName];
        if (tex && as.sprite.texture !== tex) as.sprite.texture = tex;
      }
    // Thief actors are a view of state.actors, like the player: the
    // sprite follows the actor, and carrying a snatched key swaps
    // to the carrying pose so the steal is visible.
    for (const actor of state.actors || []) {
      if (actor.def !== 'thief:thief') continue;
      let spr = renderState._thieves && renderState._thieves.get(actor.id);
      if (!spr) {
        const tex0 = textures['thief.png'];
        if (!tex0) continue;
        spr = new PIXI.Sprite(tex0);
        spr.scale.set(scale);
        board.addChild(spr);
        (renderState._thieves = renderState._thieves
          || new Map()).set(actor.id, spr);
      }
      spr.position.set(actor.x * TILE, actor.y * TILE);
      const tex = actor.flags && actor.flags.carrying
        ? textures['thief-carrying-key.png'] : textures['thief.png'];
      if (tex && spr.texture !== tex) spr.texture = tex;
    if (botSprite) {
      const bot = (state.actors || []).find((a) => a.def === 'mule:bot');
      botSprite.visible = !!bot;
      if (bot) {
        botSprite.position.set(bot.x * TILE, bot.y * TILE);
        const btex = state.flags && state.flags['mule:waiting']
          && textures['mule-bot-waiting.png']
          ? textures['mule-bot-waiting.png'] : textures['mule-bot.png'];
        if (btex && botSprite.texture !== btex) botSprite.texture = btex;
      }
    }
    marker.clear();
    marker.rect(state.player.x * TILE + 2, state.player.y * TILE + 2,
      TILE - 4, TILE - 4).stroke({ width: 3, color: 0x00c8ff });
    darkOverlay.clear();
    if (state.flags && state.flags['dark:room']) {
      for (let dy = 0; dy < ROWS; dy++) {
        for (let dx = 0; dx < COLS; dx++) {
          const lit = window.GameCore.isDarkVisible
            ? window.GameCore.isDarkVisible(state.player.x, state.player.y, dx, dy)
            : Math.max(Math.abs(dx - state.player.x), Math.abs(dy - state.player.y)) <= 2;
          if (!lit) darkOverlay.rect(dx * TILE, dy * TILE, TILE, TILE).fill(0x000000);
        }
      }
    ghostLayer.removeChildren();
    for (const g of (state.flags && state.flags.ghost_positions) || []) {
      const texName = g.fading ? 'ghost-jolly-fading.png'
        : (g.kind === 'start' ? 'ghost-start.png' : 'ghost-jolly.png');
      const tex = textures[texName];
      if (!tex) continue;
      const spr = new PIXI.Sprite(tex);
      spr.scale.set(scale);
      spr.position.set(g.x * TILE, g.y * TILE);
      if (g.fading) spr.alpha = 0.45;
      ghostLayer.addChild(spr);
    }
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
    // Ice blocks move: each block sprite follows a live block
    // position from state (row-major), instead of its start tile.
    const iceBlocks = [];
    if (state.objects) {
      for (let by = 0; by < state.objects.length; by++) {
        for (let bx = 0; bx < state.objects[by].length; bx++) {
          if (state.objects[by][bx] === 'ice:ice-block') {
            iceBlocks.push({ x: bx, y: by });
          }
        }
      }
    }
    let iceIdx = 0;
    for (const dt of dynamicTiles) {
      if (dt.ch === 'I') {
        const bp = iceBlocks[iceIdx++];
        dt.sprite.visible = !!bp;
        if (bp) {
          dt.sprite.position.set(bp.x * TILE, bp.y * TILE);
          // Board sprites are added row-major, so floors east/south
          // of the origin were added after this sprite and would
          // cover it after such a slide (it looked picked up).
          if (dt.sprite.parent) dt.sprite.parent.setChildIndex(
            dt.sprite, dt.sprite.parent.children.length - 1);
        }
        continue;
      }
      if (dt.ch === 'F' || dt.ch === '~') {
        // Fire becomes scorched ('S'), shallow water an ice
        // bridge ('B'): the glyph follows the grid char.
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === dt.ch
          || gc === (dt.ch === 'F' ? 'S' : 'B');
        if (dt.sprite.visible && dt.sprite.text !== undefined) {
          dt.sprite.text = gc;
        }
        continue;
      }
      // The gate tile stays 'G' when open: its sprite shows only
      // while shut, revealing the floor base underneath. A crumbling
      // tile ('C') becomes void ('V'): the same glyph follows the
      // grid char so the hole stays visible instead of turning back
      // into plain floor.
      if (dt.ch === 'D') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = true;
        const texName = gc === 'D' ? 'orb-door-closed.png' : 'orb-door-open.png';
      if (dt.ch === 'H') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'H' || gc === 'h';
        const texName = gc === 'h' ? 'hourglass-spent.png' : 'hourglass.png';
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'C') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'C' || gc === 'V';
        // Intact, minor, major and void each have a bundled sprite
        // in the crumbling pack; the visible stage follows the
        // count of step-ons stored in the cell meta.
        const cmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const cstage = (cmeta && cmeta.crumble_stage) || 0;
        const texName = gc === 'V' ? 'void.png'
          : (cstage >= 2 ? 'crumbling-major.png'
            : (cstage === 1 ? 'crumbling-minor.png' : 'crumbling.png'));
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'B') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'B';
        // Rest vs compressed art follows the pad stage in cell
        // meta (1 compressing / 2 ready both read as compressed).
        const bmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const bstage = (bmeta && bmeta.bounce_stage) || 0;
        const texName = bstage >= 1 ? 'bounce-pad-compressed.png'
          : 'bounce-pad.png';
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'T') {
        const tmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const tdir = (tmeta && tmeta.turntable_dir) || 'north';
        const ttex = textures['turntable-' + tdir + '.png'];
        if (ttex && dt.sprite.texture !== ttex) dt.sprite.texture = ttex;
      } else if (dt.ch === 'D') {
        // Dash tile: spent face while the player holds the charge.
        dt.sprite.visible = true;
        const held = (state.inventory || []).some(
          (e) => e.item === 'dash:charge');
        const dtex = textures[held ? 'dash-tile-spent.png' : 'dash-tile.png'];
        if (dtex && dt.sprite.texture !== dtex) dt.sprite.texture = dtex;
      } else if (dt.ch === 'T') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        const tmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const tphase = (tmeta && tmeta.timed_phase) || 'unseen';
        // Dissolved: show the faint reforming ghost on its start
        // tile; otherwise the orb itself, ringed while counting.
        dt.sprite.visible = gc === 'T' || tphase === 'dissolved';
        const texName = tphase === 'dissolved'
          ? 'timed-orb-reforming.png'
          : (tphase === 'ringing' ? 'timed-orb-ringing.png'
            : 'timed-orb.png');
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'H') {
        // Hidden orb: drawn only inside light radius (Chebyshev <=2).
        const present = !!(state.grid[dt.y] && state.grid[dt.y][dt.x] === 'H');
        const lit = Math.max(Math.abs(dt.x - state.player.x), Math.abs(dt.y - state.player.y)) <= 2;
        dt.sprite.visible = present && lit;
      } else if (dt.ch === 'H') {
        // Heavy orb: the sprite follows the orb as it is pushed; a
        // locked orb (heavy:orb-locked on the scale) shows the
        // locked art instead of the loose orb art.
        let ox = -1, oy = -1, locked = false;
        if (state.objects) {
          for (let yy = 0; yy < state.objects.length && ox < 0; yy++) {
            for (let xx = 0; xx < state.objects[yy].length; xx++) {
              const id = state.objects[yy][xx];
              if (id === 'heavy:orb' || id === 'heavy:orb-locked') {
                ox = xx; oy = yy; locked = id === 'heavy:orb-locked';
                break;
              }
            }
          }
        }
        dt.sprite.visible = ox >= 0;
        if (ox >= 0) {
          dt.sprite.position.set(ox * TILE, oy * TILE);
          const tex = textures[locked ? 'scale-locked.png' : 'heavy-orb.png'];
          if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
        }
      } else if (state.meta && state.meta[dt.x + ',' + dt.y] &&
          ('switch_open' in state.meta[dt.x + ',' + dt.y] ||
           'switch_pressed' in state.meta[dt.x + ',' + dt.y])) {
        // Floor switch pack: the door sprite follows switch_open
        // and the plate sprite follows switch_pressed, both cell
        // meta written by the pack tick hook (a view of the held
        // state, never a driver of it).
        const smeta = state.meta[dt.x + ',' + dt.y];
        const texName = 'switch_open' in smeta
          ? (smeta.switch_open ? 'door-open.png' : 'door-closed.png')
          : (smeta.switch_pressed ? 'floor-switch-pressed.png'
            : 'floor-switch-unpressed.png');
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
        dt.sprite.visible = true;
      } else if (dt.ch === 'T' || dt.ch === 'a' || dt.ch === 'b') {
        // Toggle pack: the switch face and both doors swap sprites
        // in place and never disappear, so follow the live def.
        const oid = state.objects && state.objects[dt.y]
          && state.objects[dt.y][dt.x];
        const odef = oid && window.GameCore.getTileDef
          ? window.GameCore.getTileDef(oid) : null;
        const otex = odef && odef.sprite && textures[odef.sprite];
        if (otex && dt.sprite.texture !== otex) dt.sprite.texture = otex;
        dt.sprite.visible = !!oid;
      } else if (dt.ch === 'D' || dt.ch === 'S') {
        const gc2 = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = dt.ch === 'S' ? gc2 === 'S'
          : (gc2 === 'D' || gc2 === 'O');
        const tmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const texName2 = dt.ch === 'S'
          ? ((tmeta && tmeta.timer_running)
            ? 'timer-switch-running.png' : 'timer-switch-ready.png')
          : (gc2 === 'O' ? 'door-open.png' : 'door-closed.png');
        const tex2 = textures[texName2];
        if (tex2 && dt.sprite.texture !== tex2) dt.sprite.texture = tex2;
      } else if (dt.ch === 'S' || dt.ch === 'D') {
        const gc2 = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = dt.ch === 'S' ? (gc2 === 'S' || gc2 === 'B') : (gc2 === 'D' || gc2 === 'O');
        const tn = dt.ch === 'S' ? (gc2 === 'B' ? 'one-time-switch-broken.png' : 'one-time-switch-intact.png') : (gc2 === 'O' ? 'door-open.png' : 'door-closed.png');
        const tx = textures[tn];
        if (tx && dt.sprite.texture !== tx) dt.sprite.texture = tx;
      } else if (dt.ch === '1' || dt.ch === '2' || dt.ch === '3') {
        // Chain switch: lit and unlit share the order-mark sprite
        // slot; the visible stage follows the object def in state.
        const cdef = state.objects && state.objects[dt.y]
          && state.objects[dt.y][dt.x];
        const tex = textures[/-lit$/.test(cdef || '')
          ? 'chain-switch-lit.png' : 'chain-switch-unlit.png'];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
        dt.sprite.visible = true;
      } else if (dt.ch === 'D') {
        // Chain door: closed sprite blocks like wall, open sprite
        // shows the walkable doorway after the final press.
        const ddef = state.objects && state.objects[dt.y]
          && state.objects[dt.y][dt.x];
        const tex = textures[ddef === 'chain:door-open'
          ? 'door-open.png' : 'door-closed.png'];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
        dt.sprite.visible = true;
      } else if (dt.ch === 'E' || dt.ch === 'W') {
        // Weight switch: the door sprite follows whether any plate
        // is weighted (block left on it, or the player standing on
        // it); the plate sprite shows the block-weighted state.
        let weighted = false;
        for (let wy = 0; wy < state.terrain.length && !weighted; wy++) {
          for (let wx = 0; wx < state.terrain[wy].length; wx++) {
            if (state.terrain[wy][wx] !== 'weight:plate') continue;
            if (state.objects[wy][wx] === 'weight:block' ||
                (state.player.x === wx && state.player.y === wy)) {
              weighted = true; break;
            }
          }
        }
        dt.sprite.visible = true;
        const wName = dt.ch === 'E'
          ? (weighted ? 'door-open.png' : 'door-closed.png')
          : (state.objects[dt.y][dt.x] === 'weight:block'
            ? 'weight-switch-weighted.png' : 'weight-switch-empty.png');
        const wTex = textures[wName];
        if (wTex && dt.sprite.texture !== wTex) dt.sprite.texture = wTex;
      } else if ('MABDdNn'.includes(dt.ch)) {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = !!gc && 'MABDdNn'.includes(gc);
        const texName = { M: 'mirror-switch.png', A: 'toggle-switch-a.png',
          B: 'toggle-switch-b.png', D: 'door-closed.png',
          d: 'door-open.png', N: 'toggle-switch-a.png',
          n: 'toggle-switch-b.png' }[gc];
        const tex = texName && textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
        // The blocker shuffles inside its doorway strip: follow
        // its live grid position instead of its placed cell.
        // The push block moves: its sprite follows the 'B' cell in
        // the live grid and shows the on-switch art while the block
        // sits on a switch plate (terrain under the block).
        let bx = -1, by = -1;
        for (let gy = 0; gy < state.grid.length && by < 0; gy++) {
          const gx = state.grid[gy].indexOf('B');
          if (gx >= 0) { bx = gx; by = gy; }
        }
        dt.sprite.visible = bx >= 0;
        if (bx >= 0 && dt.sprite.position) {
          dt.sprite.position.set(bx * TILE, by * TILE);
        }
      } else if (dt.ch === 'M') {
        // Disguised mimic looks like an orb on its placed tile;
        // once revealed ('N') the pooled sprites take over.
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'M';
        const tex = textures['mimic-orb.png'];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'U') {
        // Guard: the tile stays 'U' while its facing cycles; the
        // visible arrow follows the facing stored in cell meta.
        const gmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const gfacing = (gmeta && gmeta.guard_facing) || 'left';
        dt.sprite.visible = !!(state.grid[dt.y]
          && state.grid[dt.y][dt.x] === 'U');
        const gtex = textures['guard-facing-' + gfacing + '.png'];
        if (gtex && dt.sprite.texture !== gtex) dt.sprite.texture = gtex;
      } else if (dt.ch === 'A') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'A' || gc === 'a';
        const texName = gc === 'a' ? 'alarm-inert.png' : 'alarm.png';
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'S') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'S' || gc === 'E';
        if (dt.sprite.text !== undefined) dt.sprite.text = gc === 'E' ? 'E' : 'S';
      } else if (dt.ch === 'F' || dt.ch === 'g' || dt.ch === 'w') {
        // Fire pack: a grass/wood/fire cell follows the grid char —
        // burning fire ('F') and burnt-out scorched floor ('H')
        // swap textures, plain flammable floor shows the base.
        const gc2 = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = true;
        const texName2 = gc2 === 'F' ? 'fire.png'
          : (gc2 === 'H' ? 'scorched.png' : 'floor_default.png');
        const tex2 = textures[texName2];
        if (tex2 && dt.sprite.texture !== tex2) dt.sprite.texture = tex2;
      } else if (dt.ch === 'S') {
        dt.sprite.visible = true;
        const smeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const texName = (smeta && smeta.sand_print)
          ? 'sand-prints.png' : 'sand.png';
      } else if (dt.ch === 'g') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'g' || gc === 'V';
        const gmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const gstage = (gmeta && gmeta.glass_stage) || 0;
        const texName = gc === 'V' ? 'void.png'
          : (gstage >= 1 ? 'glass-cracked.png' : 'glass.png');
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'M') {
        const mmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const texName = mmeta && mmeta.mud_print ? 'mud-prints.png' : 'mud.png';
        const mtex = textures[texName];
        if (mtex && dt.sprite.texture !== mtex) dt.sprite.texture = mtex;
      } else if (dt.ch === 'K') {
        // Checkpoint: lit only while it is the active respawn; the
        // active flag is the cell meta set by the checkpoint pack.
        const kmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const texName = kmeta && kmeta.checkpoint_active
          ? 'checkpoint-on.png' : 'checkpoint-off.png';
        const tex = textures[texName];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
        dt.sprite.visible = !!(state.grid[dt.y]
          && state.grid[dt.y][dt.x] === 'K');
      } else if (dt.ch === '*' && state.counters
          && typeof state.counters['lantern:radius'] === 'number') {
        // Lantern room: an orb is drawn only inside the light
        // radius (two tiles, four with the lantern); it still
        // exists and collects by walking onto it either way.
        const lanternPack = window.GamePackLantern;
        dt.sprite.visible = !!(state.grid[dt.y]
          && state.grid[dt.y][dt.x] === dt.ch)
          && lanternPack.isLit(state, dt.x, dt.y);
      } else if (dt.ch === 'F' || dt.ch === 'f') {
        // Fog (mech-53): unrevealed fog always shows fog.png and
        // hides its contents; revealed fog shows the empty tile or
        // the orb on it, and stays revealed for the attempt (the
        // reveal itself lives in cell meta via the fog pack).
        const gcF = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gcF === 'F' || gcF === 'f';
        const fmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const frevealed = !!(fmeta && fmeta.fog_revealed);
        const ftexName = !frevealed ? 'fog.png'
          : (gcF === 'f' ? 'fog-revealed-orb.png' : 'fog-revealed.png');
        const ftex = textures[ftexName];
        if (ftex && dt.sprite.texture !== ftex) dt.sprite.texture = ftex;
      } else if (dt.ch === 'M') {
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'M' || gc === 'm';
        const texName = gc === 'm' ? 'map-spent.png' : 'map.png';
      } else if (dt.ch === 'i') {
        // Info tile: fresh and spent forms share the grid char
        // 'i'; the spent look follows the cell meta (info_read),
        // like the crumbling stages above.
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'i';
        const imeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const texName = (imeta && imeta.info_read)
          ? 'info-read.png' : 'info.png';
        const tex = textures[texName];
      } else if (dt.ch === 'S') {
        // Secret wall: drawn as a wall until first walked through,
        // then the faded sprite keeps the opening known ('s').
        const gc = state.grid[dt.y] && state.grid[dt.y][dt.x];
        dt.sprite.visible = gc === 'S' || gc === 's';
        const tex = textures[gc === 's'
          ? 'secret-wall-faded.png' : 'secret-wall.png'];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
      } else if (dt.ch === 'H') {
        dt.sprite.visible = true;
        const ptex = textures[(state.flags || {})['peep:active']
          ? 'peep-hole-active.png' : 'peep-hole.png'];
        if (ptex && dt.sprite.texture !== ptex) dt.sprite.texture = ptex;
      } else if (dt.ch === 'S') {
        // Still tile: held art while the player stands on it.
        const occupied = state.player.x === dt.x && state.player.y === dt.y;
        const tex = textures[occupied ? 'still-held.png' : 'still.png'];
        if (tex && dt.sprite.texture !== tex) dt.sprite.texture = tex;
        dt.sprite.visible = true;
      } else if (dt.ch === 'D') {
        // Move door: the glyph stays 'D'; the bundled sprite
        // follows the move_open meta the movedoor pack tick hook
        // maintains (closed under fifty moves, permanently open
        // from the 50th move onward).
        const dmeta = state.meta && state.meta[dt.x + ',' + dt.y];
        const dtexName = dmeta && dmeta.move_open
          ? 'move-door-open.png' : 'move-door-closed.png';
        const dtex = textures[dtexName];
        if (dtex && dt.sprite.texture !== dtex) {
          dt.sprite.texture = dtex;
        }
        dt.sprite.visible = true;
        if (bx >= 0) {
          dt.sprite.position.set(bx * TILE, by * TILE);
          // Board sprites are added row-major, so floors east/south
          // of the origin were added after this sprite and would
          // cover it after such a push (it looked picked up).
          if (dt.sprite.parent) dt.sprite.parent.setChildIndex(
            dt.sprite, dt.sprite.parent.children.length - 1);
          const onSwitch = state.terrain[by][bx] === 'blocks:switch-plate';
          const bTex = textures[onSwitch
            ? 'push-block-on-switch.png' : 'push-block.png'];
          if (bTex && dt.sprite.texture !== bTex) dt.sprite.texture = bTex;
        }
      } else if (dt.ch === 'D') {
        // The switch gate shows only while no push block holds a
        // switch plate down.
        let held = false;
        for (let gy = 0; gy < state.height && !held; gy++) {
          for (let gx = 0; gx < state.width; gx++) {
            if (state.objects[gy][gx] === 'blocks:push-block'
                && state.terrain[gy][gx] === 'blocks:switch-plate') held = true;
          }
        }
        dt.sprite.visible = !held;
      } else if (dt.ch === 'M') {
        // The mirror block moves when pushed: its sprite follows
        // the 'M' cell in the projected grid, not its start tile.
        let mx = -1, my = -1;
        for (let gy = 0; gy < state.grid.length; gy++) {
          const gx = state.grid[gy].indexOf('M');
          if (gx >= 0) { mx = gx; my = gy; break; }
        }
        dt.sprite.visible = mx >= 0;
        if (mx >= 0 && dt.sprite.position) {
          dt.sprite.position.set(mx * TILE, my * TILE);
        }
      } else {
        dt.sprite.visible = dt.ch === 'G'
          ? !state.gate_open
          : !!(state.grid[dt.y] && state.grid[dt.y][dt.x] === dt.ch);
      }
    }
    let mimicIdx = 0;
    for (let gy = 0; gy < state.grid.length; gy++) {
      for (let gx = 0; gx < state.grid[gy].length; gx++) {
        if (state.grid[gy][gx] !== 'N' || mimicIdx >= mimicPool.length) continue;
        const spr = mimicPool[mimicIdx++];
        spr.position.set(gx * TILE, gy * TILE);
        spr.visible = true;
      }
    }
    for (; mimicIdx < mimicPool.length; mimicIdx++) mimicPool[mimicIdx].visible = false;
    if (mapOverlay) {
      mapOverlay.visible = !!(state.flags && state.flags['map_overlay_active']);
    // Bomb blocks slide: their sprites follow the live bomb cells
    // in state instead of the cell the level placed them on, and a
    // consumed bomb's sprite hides. A cracked wall ('W') needs no
    // follow: the loop above hides it once its grid char becomes
    // floor, revealing the floor-after-blast base underneath.
    const bombTiles = dynamicTiles.filter((dt) => dt.ch === 'B');
    if (bombTiles.length) {
      const bombCells = [];
      for (let by = 0; by < state.grid.length; by++) {
        for (let bx = 0; bx < state.grid[by].length; bx++) {
          if (state.grid[by][bx] === 'B') bombCells.push({ x: bx, y: by });
        }
      }
      bombTiles.forEach((dt, i) => {
        const cell = bombCells[i];
        dt.sprite.visible = !!cell;
        if (cell) dt.sprite.position.set(cell.x * TILE, cell.y * TILE);
      });
    for (const es of enemySprites) {
      const ea = state.actors.find((a) => a.id === es.id);
      if (ea) es.sprite.position.set(ea.x * TILE + TILE / 2, ea.y * TILE + TILE / 2);
      es.sprite.visible = !!ea;
    }
    retryGroup.visible = state.status === 'lost';
    // The HUD win screen is only for the last level; mid-chain a
    // win shows the level summary (its Next button) instead.
    winGroup.visible = state.status === 'won' && !state.next_level;
    const finishKey = (retryGroup.visible ? 'r' : '') +
      (winGroup.visible ? 'w' : '');
    if (finishKey !== renderState._finishKey) {
      renderState._finishKey = finishKey;
      layoutHud();
    }
    if (frozenBadge) {
      frozenBadge.visible = window.GameCore.readout(state).timer_frozen;
    }
    hudValues.orbs = window.GameHud.orbsLeft(state);
    orbsReadout.set(hudValues.orbs);
    hudValues.level = window.GameHud.levelNumber(level, state.level);
    levelReadout.set(hudValues.level);
    if (movesReadout) {
      hudValues.moves = (state.counters
        && state.counters['movedoor:moves']) || 0;
      movesReadout.set(hudValues.moves);
    }
    hudValues.inventory = window.GameHud.inventorySlots(
      window.GameCore.readout(state).inventory);
    setInventory(hudValues.inventory);
    if (heldIcon) {
      heldIcon.visible = !!(state.flags && state.flags['still:held']);
    }
    drawHud(state.elapsed_s, state.time_limit_s);
    const bannerEl = document.getElementById('info-banner');
    if (bannerEl) {
      const bShown = (state.counters && state.counters['info:shown']) || 0;
      if (bShown < bannerCountSeen) bannerCountSeen = bShown;
      if (bShown > bannerCountSeen) {
        bannerCountSeen = bShown;
        const cellMeta = state.meta &&
          state.meta[state.player.x + ',' + state.player.y];
        const text = (cellMeta && cellMeta.banner) ||
          (state.flags && state.flags['info:banner']) || '';
        if (text) {
          bannerEl.textContent = text;
          bannerEl.style.display = 'block';
        }
      }
      const pm = state.meta &&
        state.meta[state.player.x + ',' + state.player.y];
      if (!(pm && pm.banner)) bannerEl.style.display = 'none';
    }
    drawHud(typeof state.effective_elapsed_s === 'number'
      ? state.effective_elapsed_s : state.elapsed_s, state.time_limit_s);
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
    hideLevelSummary();
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
    else if (state.status === 'won') {
      // Warp: close this level's session as won, then show the
      // centre-screen level summary. Loading the next level is
      // the summary continue button's job, not this step's.
      endSession('won');
      showLevelSummary();
    }
    else flushSession(false);
  }
  // Level summary (centre of the screen): a view of the finished
  // run's GameCore state, shown only by live play (never replay).
  const summaryEl = document.getElementById('level-summary');
  function showLevelSummary() {
    const total = window.GameCore.countOrbs(level.rows);
    const left = window.GameCore.readout(state).orbs_left;
    document.getElementById('summary-level').textContent =
      window.GameHud.levelNumber(level, state.level) + ' (' + state.level + ')';
    document.getElementById('summary-orbs').textContent =
      (total - left) + ' / ' + total;
    document.getElementById('summary-steps').textContent = String(state.steps);
    document.getElementById('summary-time').textContent = fmtHud(state.elapsed_s);
    document.getElementById('summary-time-left').textContent =
      state.time_left_s === null ? '—' : fmtHud(state.time_left_s);
    document.getElementById('btn-summary-next').textContent =
      state.next_level ? 'Next level' : 'Finish';
    summaryEl.classList.add('open');
    document.getElementById('btn-summary-next').focus();
  }
  function hideLevelSummary() {
    summaryEl.classList.remove('open');
  }
  document.getElementById('btn-summary-next').addEventListener('click', () => {
    hideLevelSummary();
    if (state.next_level) wipeToNextLevel(state.next_level);
    // Last level: dismissing the summary reveals the win screen.
  });
  // Sweep the wipe across, then load the next level under the
  // cover; the new page starts covered and reveals (revealWipe).
  function wipeToNextLevel(nextId) {
    wipeEl.classList.add('cover');
    setTimeout(() => loadNextLevel(nextId, true), 480);
  }
  // Load the next level in the progression chain (same page, new
  // ?level=, fresh session on first move). Replay/fork params do
  // not carry over; creator/feature/embed do.
  function loadNextLevel(nextId, withWipe) {
    const next = new URLSearchParams(params);
    next.set('level', nextId);
    next.delete('replay'); next.delete('fork'); next.delete('t');
    if (withWipe) next.set('wipe', '1'); else next.delete('wipe');
    location.search = '?' + next.toString();
  }
  // Idle expiry: when the live clock reaches the limit, record the
  // loss as a step at exactly the limit so replay loses at the same
  // recorded moment — never from an unrecorded wall-clock read alone.
  // Effective (timer-hook adjusted) elapsed for the live clock:
  // an hourglass freeze holds the display at its collection value
  // for 10 real seconds, then it resumes from that value. Display
  // only; state advances solely through recorded step t_ms.
  function displayElapsedS(wallS) {
    const c = state.counters || {};
    if (!c['hourglass:collected']) return wallS;
    const collect = (c['hourglass:collect_ms'] || 0) / 1000;
    const offset = (c['hourglass:offset_ms'] || 0) / 1000;
    const frozen = Math.min(Math.max(wallS - collect, 0), 10);
    return wallS - offset - frozen;
  }
  function expiryTMs() {
    const c = state.counters || {};
    let extra = 0;
    if (c['hourglass:collected']) {
      extra = (c['hourglass:offset_ms'] || 0) / 1000 + 10;
    }
    return Math.round((state.time_limit_s + extra) * 1000);
  }
  function expireNow() {
    if (state.status === 'lost' || state.status === 'won' ||
        state.time_limit_s === null ||
        state.time_limit_s === undefined) return;
    applyStep({ t_ms: expiryTMs(), input: 'timeout' });
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
      // A finished run is frozen: after death (or the win) the clock
      // shows the finishing moment, never the still-running page clock.
      const finished = state.status === 'lost' || state.status === 'won';
      const elapsed = finished
        ? (typeof state.effective_elapsed_s === 'number'
          ? state.effective_elapsed_s : state.elapsed_s)
        : displayElapsedS(sessionElapsedMs() / 1000);
      drawHud(elapsed, state.time_limit_s);
      const dbg = document.getElementById('dbg-timer');
      if (dbg) dbg.textContent = elapsed.toFixed(1) +
        (finished ? 's (frozen)' : 's (live clock)');
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
    if (state.status === 'lost' || state.status === 'won') return;
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
      drawHud((typeof cur.effective_elapsed_s === 'number'
        ? cur.effective_elapsed_s : cur.elapsed_s)
        + (playheadMs - cur.t_ms) / 1000, cur.time_limit_s);
      if (replayIndex >= replayStates.length - 1 &&
          playheadMs >= cur.t_ms) { pauseReplay(); return; }
      replayTimer = requestAnimationFrame(loop);
    };
    replayTimer = requestAnimationFrame(loop);
  }
  async function loadReplay(id, tSeconds) {
    hideLevelSummary();
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
    getClock: () => {
      const fin = state.status === 'lost' || state.status === 'won';
      const el = fin
        ? (typeof state.effective_elapsed_s === 'number'
          ? state.effective_elapsed_s : state.elapsed_s)
        : displayElapsedS(sessionElapsedMs() / 1000);
      return { started: sessionStartTs !== null, status: state.status,
        elapsed_s: el, time_limit_s: state.time_limit_s,
        time_left_s: state.time_limit_s === null
          ? null : Math.max(0, state.time_limit_s - el) };
    },
    restart: restartLevel,
    getReplay: () => ({ playing: replayTimer !== null, playhead_ms: playheadMs, id: replayId, index: replayIndex,
      duration_ms: window.__replayRecords ? (window.GameReplay.stepsOf(window.__replayRecords).slice(-1)[0] || { t_ms: 0 }).t_ms : 0,
      step_times: window.__replayRecords ? window.GameReplay.stepsOf(window.__replayRecords).map((s) => s.t_ms) : [],
      steps: replayStates ? replayStates.length - 1 : 0,
      active: replayStates !== null,
      readout: document.getElementById('replay-readout').textContent,
      warning: document.getElementById('replay-warning').textContent }),
    getState: () => state,
    getProgression: () => ({ level: state.level,
      status: state.status, next_level: state.next_level }),
    getPlayerSpritePos: () => playerSprite
      ? { x: playerSprite.position.x, y: playerSprite.position.y }
      : null,
    getHud: () => ({ timer: hudValues.timer, orbs: hudValues.orbs,
      level: hudValues.level, inventory: hudValues.inventory.slice() }),
    getInfoBanner: () => {
      const el = document.getElementById('info-banner');
      return { visible: !!el && el.style.display === 'block',
        text: el ? el.textContent : '' };
    },
    isRetryBarVisible: () => retryGroup.visible,
    isWinScreenVisible: () => winGroup.visible,
    isSummaryVisible: () => summaryEl.classList.contains('open'),
    isWipeCovering: () => wipeEl.classList.contains('cover') ||
      document.documentElement.classList.contains('wipe-in'),
    getWipeTransform: () => getComputedStyle(wipeEl).transform,
    getSummary: () => ({
      level: document.getElementById('summary-level').textContent,
      orbs: document.getElementById('summary-orbs').textContent,
      steps: document.getElementById('summary-steps').textContent,
      button: document.getElementById('btn-summary-next').textContent,
    }),
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
  revealWipe();
})();
