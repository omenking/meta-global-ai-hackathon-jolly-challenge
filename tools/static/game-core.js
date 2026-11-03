// GameCore facade: assembles registry + kernel + packs and keeps the
// long-standing public API (initialState/step/replay/stateDigest/
// readout/inputForKey + legacy char helpers for tests and game.js).
// Mechanics live in packs under tools/static/packs/ (core-chips,
// keys-locks, proof-water). The kernel in
// engine/kernel.js knows no specific tile. State is v2 layered data
// plus a derived compatibility projection (grid/player/orbs_left/
// gate_open) computed here, never stored as kernel truth.
(function (root) {
  'use strict';
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, IcePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, ConveyorPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, TeleportPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, OneWayPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, BouncePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, TurntablePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, StickyPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, DashPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, FanPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, TwinLockPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MasterKeyPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, TimedOrbPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, HiddenPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, HeavyPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack;
  let GuardedPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, BonusPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, FloorSwitchPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, TogglePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, TimerPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, OneTimePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, ChainPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, WeightPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MirrorPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, PatrollerPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, ChaserPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, SleeperPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, BlockerPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, ThiefPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MimicPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, GuardPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, AlarmPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, DecoyPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MulePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, DeepWaterPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, CurrentPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, FirePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, LavaPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, SandPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, GlassPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MudPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, CheckpointPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, IceBridgePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, DarkRoomPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, LanternPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, FogPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, EchoPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MapTilePack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, InfoPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, SecretWallPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, PeepPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, LifePreserverPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, CleatsPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MagnetPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, LanternPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, PouchPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, HourglassPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, StillPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, GhostPack;
  let MoveDoorPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, PushBlockPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, IceBlockPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack,
    BombPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, MirrorPack;
  let Registry, Kernel, KeysPack, CorePack, WaterPack, CrumblePack, RaftPack;
  if (typeof module !== 'undefined' && module.exports) {
    Registry = require('./engine/registry.js');
    Kernel = require('./engine/kernel.js');
    KeysPack = require('./packs/keys-locks/main.js');
    CorePack = require('./packs/core-chips/main.js');
    WaterPack = require('./packs/proof-water/main.js');
    CrumblePack = require('./packs/crumbling/main.js');
    IcePack = require('./packs/ice/main.js');
    ConveyorPack = require('./packs/conveyor/main.js');
    TeleportPack = require('./packs/teleport/main.js');
    OneWayPack = require('./packs/oneway/main.js');
    BouncePack = require('./packs/bounce/main.js');
    TurntablePack = require('./packs/turntable/main.js');
    StickyPack = require('./packs/sticky/main.js');
    DashPack = require('./packs/dash-tile/main.js');
    FanPack = require('./packs/fan/main.js');
    TwinLockPack = require('./packs/twin-lock/main.js');
    MasterKeyPack = require('./packs/master-key/main.js');
    TimedOrbPack = require('./packs/timed-orb/main.js');
    HiddenPack = require('./packs/hidden-orb/main.js');
    HeavyPack = require('./packs/heavy-orb/main.js');
    GuardedPack = require('./packs/guarded-orb/main.js');
    BonusPack = require('./packs/bonus-orb/main.js');
    FloorSwitchPack = require('./packs/floor-switch/main.js');
    TogglePack = require('./packs/toggle-switch/main.js');
    TimerPack = require('./packs/timer-switch/main.js');
    OneTimePack = require('./packs/one-time-switch/main.js');
    ChainPack = require('./packs/chain-switch/main.js');
    WeightPack = require('./packs/weight-switch/main.js');
    MirrorPack = require('./packs/mirror-switch/main.js');
    PatrollerPack = require('./packs/patroller/main.js');
    ChaserPack = require('./packs/chaser/main.js');
    SleeperPack = require('./packs/sleeper/main.js');
    BlockerPack = require('./packs/blocker/main.js');
    ThiefPack = require('./packs/thief/main.js');
    MimicPack = require('./packs/mimic/main.js');
    GuardPack = require('./packs/guard/main.js');
    AlarmPack = require('./packs/alarm/main.js');
    DecoyPack = require('./packs/decoy/main.js');
    MulePack = require('./packs/mule-bot/main.js');
    DeepWaterPack = require('./packs/deep-water/main.js');
    CurrentPack = require('./packs/current/main.js');
    FirePack = require('./packs/fire-tile/main.js');
    LavaPack = require('./packs/lava-tile/main.js');
    SandPack = require('./packs/sand-tile/main.js');
    GlassPack = require('./packs/glass-tile/main.js');
    MudPack = require('./packs/mud-tile/main.js');
    CheckpointPack = require('./packs/checkpoint-tile/main.js');
    IceBridgePack = require('./packs/ice-bridge/main.js');
    DarkRoomPack = require('./packs/dark-room/main.js');
    LanternPack = require('./packs/lantern/main.js');
    FogPack = require('./packs/fog/main.js');
    EchoPack = require('./packs/echo/main.js');
    MapTilePack = require('./packs/maptile/main.js');
    InfoPack = require('./packs/info-tile/main.js');
    SecretWallPack = require('./packs/secret-wall/main.js');
    PeepPack = require('./packs/peephole/main.js');
    LifePreserverPack = require('./packs/life-preserver/main.js');
    CleatsPack = require('./packs/ice-cleats/main.js');
    MagnetPack = require('./packs/magnet-glove/main.js');
    LanternPack = require('./packs/lantern-oil/main.js');
    PouchPack = require('./packs/orb-pouch/main.js');
    HourglassPack = require('./packs/hourglass/main.js');
    StillPack = require('./packs/still/main.js');
    GhostPack = require('./packs/ghost/main.js');
    MoveDoorPack = require('./packs/movedoor/main.js');
    PushBlockPack = require('./packs/push-block/main.js');
    IceBlockPack = require('./packs/ice-block/main.js');
    BombPack = require('./packs/bomb-block/main.js');
    MirrorPack = require('./packs/mirror-block/main.js');
    RaftPack = require('./packs/raft/main.js');
  } else {
    Registry = root.GameRegistry; Kernel = root.GameKernel;
    KeysPack = root.GamePackKeysLocks;
    CorePack = root.GamePackCoreChips;
    WaterPack = root.GamePackProofWater;
    CrumblePack = root.GamePackCrumbling;
    IcePack = root.GamePackIce;
    ConveyorPack = root.GamePackConveyor;
    TeleportPack = root.GamePackTeleport;
    OneWayPack = root.GamePackOneWay;
    BouncePack = root.GamePackBounce;
    TurntablePack = root.GamePackTurntable;
    StickyPack = root.GamePackSticky;
    DashPack = root.GamePackDashTile;
    FanPack = root.GamePackFan;
    TwinLockPack = root.GamePackTwinLock;
    MasterKeyPack = root.GamePackMasterKey;
    TimedOrbPack = root.GamePackTimedOrb;
    HiddenPack = root.GamePackHiddenOrb;
    HeavyPack = root.GamePackHeavyOrb;
    GuardedPack = root.GamePackGuardedOrb;
    BonusPack = root.GamePackBonusOrb;
    FloorSwitchPack = root.GamePackFloorSwitch;
    TogglePack = root.GamePackToggleSwitch;
    TimerPack = root.GamePackTimerSwitch;
    OneTimePack = root.GamePackOneTimeSwitch;
    ChainPack = root.GamePackChainSwitch;
    WeightPack = root.GamePackWeightSwitch;
    MirrorPack = root.GamePackMirrorSwitch;
    PatrollerPack = root.GamePackPatroller;
    ChaserPack = root.GamePackChaser;
    SleeperPack = root.GamePackSleeper;
    BlockerPack = root.GamePackBlocker;
    ThiefPack = root.GamePackThief;
    MimicPack = root.GamePackMimic;
    GuardPack = root.GamePackGuard;
    AlarmPack = root.GamePackAlarm;
    DecoyPack = root.GamePackDecoy;
    MulePack = root.GamePackMuleBot;
    DeepWaterPack = root.GamePackDeepWater;
    CurrentPack = root.GamePackCurrent;
    FirePack = root.GamePackFireTile;
    LavaPack = root.GamePackLavaTile;
    SandPack = root.GamePackSandTile;
    GlassPack = root.GamePackGlassTile;
    MudPack = root.GamePackMudTile;
    CheckpointPack = root.GamePackCheckpointTile;
    IceBridgePack = root.GamePackIceBridge;
    DarkRoomPack = root.GamePackDarkRoom;
    LanternPack = root.GamePackLantern;
    FogPack = root.GamePackFog;
    EchoPack = root.GamePackEcho;
    MapTilePack = root.GamePackMapTile;
    InfoPack = root.GamePackInfoTile;
    SecretWallPack = root.GamePackSecretWall;
    PeepPack = root.GamePackPeepHole;
    LifePreserverPack = root.GamePackLifePreserver;
    CleatsPack = root.GamePackIceCleats;
    MagnetPack = root.GamePackMagnetGlove;
    LanternPack = root.GamePackLanternOil;
    PouchPack = root.GamePackOrbPouch;
    HourglassPack = root.GamePackHourglass;
    StillPack = root.GamePackStill;
    GhostPack = root.GamePackGhost;
    MoveDoorPack = root.GamePackMoveDoor;
    PushBlockPack = root.GamePackPushBlock;
    IceBlockPack = root.GamePackIceBlock;
    BombPack = root.GamePackBombBlock;
    MirrorPack = root.GamePackMirrorBlock;
    RaftPack = root.GamePackRaft;
  }

  function createEngine(packRegisters) {
    const registry = Registry.createRegistry();
    for (const fn of packRegisters) registry.registerPack(fn);
    const kernel = Kernel.createKernel(registry);
    function tileMaps(level) {
      const keyTiles = {}, lockTiles = {};
      const legend = (level && level.legend) || {};
      for (const ch of Object.keys(legend)) {
        const e = legend[ch] || {};
        if (e.key_color) keyTiles[ch] = e.key_color;
        if (e.lock_color) lockTiles[ch] = e.lock_color;
      }
      return { keyTiles: keyTiles, lockTiles: lockTiles };
    }
    function project(state, maps) {
      const player = state.actors.find((a) => a.id === 'player') || state.actors[0];
      const grid = [];
      for (let y = 0; y < state.height; y++) {
        let row = '';
        for (let x = 0; x < state.width; x++) {
          const obj = state.objects[y][x];
          if (obj) row += state.chars.object[obj] || '?';
          else if (x === state.spawn.x && y === state.spawn.y) row += 'P';
          else row += state.chars.terrain[state.terrain[y][x]] || '.';
        }
        grid.push(row);
      }
      const pouch = typeof state.counters['pouch:held'] === 'number';
      const orbs = pouch ? state.counters['pouch:held']
        : (typeof state.counters['core:orbs_left'] === 'number'
        ? state.counters['core:orbs_left']
        : state.objects.flat().filter((id) => id === 'core:orb').length);
      const gateOpen = pouch
        ? (state.counters['pouch:spent'] || 0) >= (state.counters['pouch:gate_cost'] || 2)
        : orbs === 0;
      return Object.assign({}, state, { grid: grid,
        player: player ? { x: player.x, y: player.y } : { x: 0, y: 0 },
        orbs_left: orbs, gate_open: gateOpen,
        key_tiles: maps ? maps.keyTiles : (state.key_tiles || {}),
        lock_tiles: maps ? maps.lockTiles : (state.lock_tiles || {}) });
    }
    function initialState(level, levelName) {
      return project(kernel.initialState(level, levelName), tileMaps(level || {}));
    }
    function step(state, input) {
      const maps = { keyTiles: state.key_tiles || {}, lockTiles: state.lock_tiles || {} };
      return project(kernel.step(state, input), maps);
    }
    function replay(level, levelName, log) {
      let s = initialState(level, levelName);
      const states = [s];
      for (const input of log || []) { s = step(s, input); states.push(s); }
      return states;
    }
    function readout(state) {
      const inv = (state.inventory || []).map((e) => {
        if (typeof e === 'string') return e;
        const def = registry.getItem(e.item);
        return def && def.readout !== undefined ? def.readout : e.item;
      });
      const orbs = typeof state.orbs_left === 'number' ? state.orbs_left
        : (state.counters || {})['core:orbs_left'];
      return { step: state.steps, position: { x: state.player.x, y: state.player.y },
        inventory: inv, orbs_left: orbs,
        gate_open: typeof state.gate_open === 'boolean' ? state.gate_open : orbs === 0,
        status: state.status || 'playing',
        next_level: state.next_level === undefined ? null : state.next_level,
        timer: state.time_left_s === null ? state.elapsed_s : state.time_left_s,
        time_left_s: state.time_left_s, elapsed_s: state.elapsed_s,
        effective_elapsed_s: state.effective_elapsed_s,
        timer_frozen: !!((state.counters || {})['hourglass:collected']
          && state.t_ms - (state.counters || {})['hourglass:collect_ms'] >= 0
          && state.t_ms - (state.counters || {})['hourglass:collect_ms'] < 10000),
        t_ms: state.t_ms, input: state.last_input };
        t_ms: state.t_ms, input: state.last_input,
        raft_riding: !!(state.flags && state.flags['raft:riding']),
        raft_remaining: (state.counters && typeof state.counters['raft:remaining'] === 'number') ? state.counters['raft:remaining'] : null };
    }
    // Pack-carried assets: probing a level registers its pack defs,
    // whose declared sprite/icon names are what the page preloads.
    function assetsForLevel(level) {
      try { kernel.initialState(level, (level && level.name) || ''); } catch (e) { /* defs registered before any throw */ }
      return registry.assetNames();
    }
    // Same probe, with load URLs: bundled assets resolve into their
    // pack folder, shared assets into level-sprites/.
    function assetPathsForLevel(level) {
      try { kernel.initialState(level, (level && level.name) || ''); } catch (e) { /* defs registered before any throw */ }
      return registry.assetPaths();
    }
    function levelDefMap(level) {
      const probe = kernel.initialState(level, (level && level.name) || '');
      const map = {};
      const rows = (level && level.rows) || [];
      for (let y = 0; y < rows.length; y++) {
        for (let x = 0; x < rows[y].length; x++) {
          const ch = rows[y][x];
          if (!map[ch]) map[ch] = probe.objects[y][x] || probe.terrain[y][x];
        }
      }
      return map;
    }
    return { initialState: initialState, step: step, replay: replay,
      readout: readout, kernel: kernel, registry: registry,
      assetsForLevel: assetsForLevel, assetPathsForLevel: assetPathsForLevel,
      levelDefMap: levelDefMap,
      getTileDef: function (id) { return registry.getTile(id); } };
  }

  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, IcePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, ConveyorPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, TeleportPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, OneWayPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, BouncePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, TurntablePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, StickyPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, DashPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, FanPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, TwinLockPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MasterKeyPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, TimedOrbPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, HiddenPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, HeavyPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, GuardedPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, BonusPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, FloorSwitchPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, TogglePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, TimerPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, OneTimePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, ChainPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, WeightPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MirrorPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, PatrollerPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, ChaserPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, SleeperPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, BlockerPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, ThiefPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MimicPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, GuardPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, AlarmPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, DecoyPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MulePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, DeepWaterPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, CurrentPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, FirePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, LavaPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, SandPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, GlassPack, CrumblePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MudPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, CheckpointPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, IceBridgePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, DarkRoomPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, LanternPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, FogPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, EchoPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MapTilePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, InfoPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, SecretWallPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, PeepPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, LifePreserverPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, CleatsPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MagnetPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, LanternPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, PouchPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, HourglassPack]);
  // Still registers first: its tick holds elapsed_s while the
  // player stands on a still tile, and the core expiry check must
  // read the held value, not the raw recorded elapsed time.
  const engine = createEngine([StillPack, CorePack, KeysPack, WaterPack, CrumblePack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, GhostPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack,
    MoveDoorPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, PushBlockPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, IceBlockPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, BombPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, MirrorPack]);
  const engine = createEngine([CorePack, KeysPack, WaterPack, CrumblePack, RaftPack]);

  // --- Legacy char helpers (compatibility surface for tests/game.js) ---
  function findPlayer(level) {
    const rows = (level && level.rows) || [];
    for (let y = 0; y < rows.length; y++) {
      const x = rows[y].indexOf('P');
      if (x >= 0) return { x: x, y: y };
    }
    return { x: 0, y: 0 };
  }
  function isWalkable(grid, x, y) {
    if (!Array.isArray(grid) || y < 0 || y >= grid.length) return false;
    const row = grid[y];
    if (typeof row !== 'string' || x < 0 || x >= row.length) return false;
    const ch = row[x];
    return ch === '.' || ch === 'P';
  }
  function isOrb(ch) { return ch === '*' || ch === 'O'; }
  function isWarp(ch) { return ch === 'X'; }
  function countOrbs(grid) {
    let n = 0;
    for (const row of grid || []) for (const ch of row) if (isOrb(ch)) n++;
    return n;
  }
  function isLost(state) { return !!state && state.status === 'lost'; }
  function isWon(state) { return !!state && state.status === 'won'; }
  function stateDigest(state) {
    const text = JSON.stringify(state);
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return ('0000000' + h.toString(16)).slice(-8);
  }
  const KEY_INPUTS = { w: 'up', arrowup: 'up', a: 'left', arrowleft: 'left',
    s: 'down', arrowdown: 'down', d: 'right', arrowright: 'right' };
  function inputForKey(key) {
    if (typeof key !== 'string') return null;
    return KEY_INPUTS[key.toLowerCase()] || null;
  }
  const VERSION = 'game-core-2';
  const api = { findPlayer: findPlayer, initialState: engine.initialState,
    step: engine.step, replay: engine.replay, stateDigest: stateDigest,
    inputForKey: inputForKey, isWalkable: isWalkable, isLost: isLost,
    isWon: isWon, isOrb: isOrb, isWarp: isWarp, countOrbs: countOrbs,
    DIRECTIONS: Kernel.DIRECTIONS, VERSION: VERSION, readout: engine.readout,
    DEFAULT_TIME_LIMIT_S: 120, createEngine: createEngine,
    assetsForLevel: engine.assetsForLevel,
    assetPathsForLevel: engine.assetPathsForLevel,
    levelDefMap: engine.levelDefMap,
    getTileDef: engine.getTileDef,
    registerCorePack: CorePack, registerKeysPack: KeysPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack,
    registerIcePack: IcePack,
    registerConveyorPack: ConveyorPack,
    registerTeleportPack: TeleportPack,
    registerOneWayPack: OneWayPack,
    registerBouncePack: BouncePack,
    registerTurntablePack: TurntablePack,
    registerStickyPack: StickyPack,
    registerDashPack: DashPack,
    registerFanPack: FanPack,
    registerTwinLockPack: TwinLockPack,
    registerMasterKeyPack: MasterKeyPack,
      registerTimedOrbPack: TimedOrbPack,
    registerHiddenOrbPack: HiddenPack,
    registerGuardedOrbPack: GuardedPack,
    registerBonusOrbPack: BonusPack,
    registerFloorSwitchPack: FloorSwitchPack,
    registerTogglePack: TogglePack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerTimerSwitchPack: TimerPack,
    registerOneTimeSwitchPack: OneTimePack,
    registerChainSwitchPack: ChainPack,
    registerWeightSwitchPack: WeightPack,
    registerMirrorPack: MirrorPack,
    registerPatrollerPack: PatrollerPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerChaserPack: ChaserPack,
    registerSleeperPack: SleeperPack,
    registerBlockerPack: BlockerPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerThiefPack: ThiefPack,
    registerMimicPack: MimicPack,
    registerGuardPack: GuardPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerAlarmPack: AlarmPack,
    registerMuleBotPack: MulePack,
    registerDeepWaterPack: DeepWaterPack,
    registerCurrentPack: CurrentPack,
    registerFirePack: FirePack,
    registerLavaPack: LavaPack,
    registerSandPack: SandPack,
    registerGlassPack: GlassPack,
    registerMudTilePack: MudPack,
    registerCheckpointPack: CheckpointPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerIceBridgePack: IceBridgePack,
    registerDarkRoomPack: DarkRoomPack,
    DARK_LIGHT_RADIUS: DarkRoomPack.LIGHT_RADIUS,
    isDarkVisible: DarkRoomPack.isVisible,
    isDarkStateVisible: DarkRoomPack.isStateVisible,
    registerLanternPack: LanternPack,
    registerFogPack: FogPack, isFogRevealed: FogPack.isRevealed,
    registerEchoPack: EchoPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerMapTilePack: MapTilePack,
    registerInfoTilePack: InfoPack,
    registerSecretWallPack: SecretWallPack,
    registerPeepHolePack: PeepPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerLifePreserverPack: LifePreserverPack,
    registerIceCleatsPack: CleatsPack,
    registerMagnetPack: MagnetPack,
    registerLanternOilPack: LanternPack,
    registerOrbPouchPack: PouchPack,
    registerHourglassPack: HourglassPack,
    registerStillPack: StillPack,
    registerGhostPack: GhostPack,
    registerMoveDoorPack: MoveDoorPack,
    registerPushBlockPack: PushBlockPack,
    registerIceBlockPack: IceBlockPack,
    registerBombPack: BombPack,
    registerWaterPack: WaterPack, registerCrumblingPack: CrumblePack, registerMirrorPack: MirrorPack,
    registerRaftPack: RaftPack,
    registry: engine.registry, kernel: engine.kernel };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameCore = api;
})(typeof window !== 'undefined' ? window : globalThis);
