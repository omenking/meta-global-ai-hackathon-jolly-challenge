"""Checks for the chain switch (mech-28-chain-switch).

The mechanic lives in the pure GameCore step (packs/chain-switch);
driven here under Node against the teaching room. Rules: switches
carry order marks 1, 2, 3; pressing them in order lights each in
turn and the last press opens the linked door; pressing out of
order resets every lit switch at once; restart (fresh state)
restores every switch unlit and the door closed.

Run with: python -m unittest tools.test_mech_28_chain_switch -v
"""
import json
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

LEVEL_ID = "mech-28-chain-switch-room"
PACK = ROOT / "tools" / "static" / "packs" / "chain-switch"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class ChainRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id)
        self.assertTrue(by_id[LEVEL_ID]["test"])

    def test_rows_rectangular_and_legend_covers_tiles(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_teaching_moment_layout(self):
        rows = self.level["rows"]

        def at(ch):
            return [(x, y) for y, r in enumerate(rows)
                    for x, c in enumerate(r) if c == ch]

        spawn = at("P")[0]
        sw = {n: at(str(n))[0] for n in (1, 2, 3)}
        # Order marks are carried by the tiles themselves.
        for n in (1, 2, 3):
            entry = self.level["legend"][str(n)]
            self.assertEqual(entry["def"], f"chain:switch-{n}")
            self.assertEqual(entry["text"], str(n))
        # The nearest switch to the spawn is the last in the order,
        # so the naive first press is the trap the room teaches.
        def dist(p):
            return abs(p[0] - spawn[0]) + abs(p[1] - spawn[1])

        self.assertEqual(min(sw, key=lambda n: dist(sw[n])), 3)
        # An info tile sits beside the first switch.
        info = at("?")[0]
        self.assertEqual(abs(info[0] - sw[1][0]) + abs(info[1] - sw[1][1]), 1)
        # The door is in the divider and the exit is beyond it.
        door = at("D")[0]
        self.assertEqual(self.level["legend"]["D"]["def"], "chain:door")
        self.assertGreater(at("X")[0][0], door[0])


class ChainPackAssetTests(unittest.TestCase):
    def test_manifest_mirrors_yaml_assets_and_files_exist(self):
        manifest = json.loads((PACK / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "chain-switch")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["chain-switch-unlit.png", "chain-switch-lit.png",
                          "door-closed.png", "door-open.png"])
        for entry in bundled:
            path = PACK / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])
            self.assertTrue(entry["shows"])


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const SW = { 1: [9, 3], 2: [4, 5], 3: [3, 1] };
const DOOR = [10, 4], EXIT = [13, 4];
function snap(s) {
  const lit = [];
  s.objects.forEach((row) => row.forEach((id) => {
    const m = /^chain:switch-(\d+)-lit$/.exec(id || '');
    if (m) lit.push(Number(m[1]));
  }));
  return { pos: { ...s.player }, status: s.status,
    progress: s.counters['chain:progress'] || 0,
    total: s.counters['chain:total'] || 0, lit: lit.sort(),
    door: s.objects[DOOR[1]][DOOR[0]] };
}
function passable(s, x, y) {
  if (x < 0 || y < 0 || x >= s.width || y >= s.height) return false;
  const terr = s.terrain[y][x];
  if (terr === 'core:wall' || terr === 'core:info'
      || terr === 'core:unknown') return false;
  if (s.objects[y][x] === 'chain:door') return false;
  return true;
}
function goTo(s, tx, ty, log) {
  const key = (x, y) => x + ',' + y;
  const prev = new Map(), dist = new Map([[key(s.player.x, s.player.y), 0]]);
  const q = [[s.player.x, s.player.y]];
  while (q.length) {
    const [x, y] = q.shift();
    if (x === tx && y === ty) break;
    for (const [name, dx, dy] of [['up', 0, -1], ['down', 0, 1],
        ['left', -1, 0], ['right', 1, 0]]) {
      const nx = x + dx, ny = y + dy, k = key(nx, ny);
      if (!dist.has(k) && (passable(s, nx, ny)
          || (nx === tx && ny === ty))) {
        dist.set(k, dist.get(key(x, y)) + 1);
        prev.set(k, { from: key(x, y), name });
        q.push([nx, ny]);
      }
    }
  }
  const path = [];
  let k = key(tx, ty);
  if (!dist.has(k)) throw new Error('no path to ' + k);
  while (prev.has(k)) { path.unshift(prev.get(k).name); k = prev.get(k).from; }
  for (const input of path) {
    const stepIn = { t_ms: (log.length + 1) * 100, input };
    log.push(stepIn);
    s = core.step(s, stepIn);
  }
  return s;
}
function pressSeq(orders) {
  const log = [];
  let s = core.initialState(level, 'mech-28-chain-switch-room');
  const snaps = [snap(s)];
  for (const n of orders) {
    s = goTo(s, SW[n][0], SW[n][1], log);
    snaps.push(snap(s));
  }
  return { snaps, state: s, log };
}
// Solution: press in marked order, then walk through the door.
const sol = pressSeq([1, 2, 3]);
{
  var solLog = sol.log.slice();
  var solFinal = goTo(sol.state, EXIT[0], EXIT[1], solLog);
  var solFinalSnap = snap(solFinal);
}
// Adversarial: nearest switch (3) first, then the corrected order.
const adv = pressSeq([3, 1, 2, 3]);
// Boundary reset: light 1 and 2, re-press 1; and 1 then skip to 3.
const resetA = pressSeq([1, 2, 1]);
const resetB = pressSeq([1, 3]);
// Boundary door: after 1 and 2 the door still blocks entry.
const partial = pressSeq([1, 2]);
let blockedPos = null, blockedSnap = null;
{
  const log = partial.log.slice();
  let s = goTo(partial.state, DOOR[0] - 1, DOOR[1], log);
  const before = { ...s.player };
  s = core.step(s, { t_ms: (log.length + 1) * 100, input: 'right' });
  blockedPos = { before, after: { ...s.player } };
  blockedSnap = snap(s);
}
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-28-chain-switch-room');
const beforeJson = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, solFinal: solFinalSnap, adv: adv.snaps,
  resetA: resetA.snaps, resetB: resetB.snaps,
  partial: partial.snaps, blockedPos, blockedSnap,
  fresh: snap(core.initialState(level, 'mech-28-chain-switch-room')),
  pure: JSON.stringify(s0) === beforeJson,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class ChainMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_press_in_marked_order(self):
        sol = self.r["sol"]
        self.assertEqual(sol[0]["progress"], 0)
        self.assertEqual(sol[0]["total"], 3)
        self.assertEqual(sol[1]["lit"], [1])
        self.assertEqual(sol[2]["lit"], [1, 2])
        self.assertEqual(sol[3]["lit"], [1, 2, 3])
        self.assertEqual(sol[3]["progress"], 3)
        self.assertEqual(sol[3]["door"], "chain:door-open")
        self.assertEqual(self.r["solFinal"]["status"], "won")
        self.assertEqual(self.r["solFinal"]["pos"], {"x": 13, "y": 4})

    def test_adversarial_nearest_switch_first(self):
        adv = self.r["adv"]
        # Pressing the nearest switch (3) first lights nothing.
        self.assertEqual(adv[1]["progress"], 0)
        self.assertEqual(adv[1]["lit"], [])
        self.assertEqual(adv[1]["status"], "playing")
        # The corrected order then succeeds; never stranded.
        self.assertEqual(adv[4]["lit"], [1, 2, 3])
        self.assertEqual(adv[4]["door"], "chain:door-open")
        self.assertTrue(all(s["status"] == "playing" for s in adv))

    def test_boundary_out_of_order_resets_all(self):
        # Light the first two, then press out of order: all unlit.
        self.assertEqual(self.r["resetA"][2]["lit"], [1, 2])
        self.assertEqual(self.r["resetA"][3]["lit"], [])
        self.assertEqual(self.r["resetA"][3]["progress"], 0)
        # Skipping ahead to the last switch resets the lit first one.
        self.assertEqual(self.r["resetB"][1]["lit"], [1])
        self.assertEqual(self.r["resetB"][2]["lit"], [])
        self.assertEqual(self.r["resetB"][2]["progress"], 0)

    def test_boundary_door_only_at_the_last_one(self):
        partial = self.r["partial"]
        self.assertEqual(partial[2]["progress"], 2)
        self.assertEqual(partial[2]["door"], "chain:door")
        # Walking into the still-closed door does not move the player.
        self.assertEqual(self.r["blockedPos"]["before"],
                         self.r["blockedPos"]["after"])
        self.assertEqual(self.r["blockedSnap"]["door"], "chain:door")

    def test_restart_restores_every_switch_and_door(self):
        self.assertEqual(self.r["fresh"]["progress"], 0)
        self.assertEqual(self.r["fresh"]["lit"], [])
        self.assertEqual(self.r["fresh"]["door"], "chain:door")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_lit_and_open_states(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("chain-switch-lit.png", js)
        self.assertIn("door-open.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/chain-switch/main.js", html)
        board = (ROOT / "tools" / "static" / "view" / "board.js").read_text(
            encoding="utf-8")
        self.assertIn("chain:switch-", board)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const SW = { 1: [9, 3], 2: [4, 5], 3: [3, 1] };
function passable(s, x, y) {
  if (x < 0 || y < 0 || x >= s.width || y >= s.height) return false;
  const terr = s.terrain[y][x];
  if (terr === 'core:wall' || terr === 'core:info'
      || terr === 'core:unknown') return false;
  if (s.objects[y][x] === 'chain:door') return false;
  return true;
}
function goTo(s, tx, ty, log) {
  const key = (x, y) => x + ',' + y;
  const prev = new Map(), dist = new Map([[key(s.player.x, s.player.y), 0]]);
  const q = [[s.player.x, s.player.y]];
  while (q.length) {
    const [x, y] = q.shift();
    if (x === tx && y === ty) break;
    for (const [name, dx, dy] of [['up', 0, -1], ['down', 0, 1],
        ['left', -1, 0], ['right', 1, 0]]) {
      const nx = x + dx, ny = y + dy, k = key(nx, ny);
      if (!dist.has(k) && (passable(s, nx, ny)
          || (nx === tx && ny === ty))) {
        dist.set(k, dist.get(key(x, y)) + 1);
        prev.set(k, { from: key(x, y), name });
        q.push([nx, ny]);
      }
    }
  }
  const path = [];
  let k = key(tx, ty);
  while (prev.has(k)) { path.unshift(prev.get(k).name); k = prev.get(k).from; }
  for (const input of path) {
    const stepIn = { t_ms: (log.length + 1) * 100, input };
    log.push(stepIn);
    s = core.step(s, stepIn);
  }
  return s;
}
const log = [];
let live = core.initialState(level, 'mech-28-chain-switch-room');
// Naive nearest-first press, then the corrected in-order run.
live = goTo(live, 3, 1, log);
live = goTo(live, 9, 3, log);
live = goTo(live, 4, 5, log);
live = goTo(live, 3, 1, log);
live = goTo(live, 13, 4, log);
const replayed = core.replay(level, 'mech-28-chain-switch-room', log);
const replayed2 = core.replay(level, 'mech-28-chain-switch-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    progress: live.counters['chain:progress'] || 0 },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 13, "y": 4}, "status": "won",
                          "progress": 3})
        self.assertGreater(self.r["replaySteps"], 10)


if __name__ == "__main__":
    unittest.main()
