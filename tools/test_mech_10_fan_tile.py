"""Checks for the fan tile (mech-10-fan-tile).

The mechanic lives in the pure GameCore step (packs/fan/main.js);
driven here under Node against the teaching room. Rules: a player
on a fan tile is pushed one tile downwind every recorded second
if that tile is free, even with a wait input; the push is one
tile per second at most, blocked downwind means no push that
second, and restart (fresh state) restores the room.

Run with: python -m unittest tools.test_mech_10_fan_tile -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

LEVEL_ID = "mech-10-fan-tile-room"


class FanRoomLevelTests(unittest.TestCase):
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
        grid = "".join(rows)
        self.assertIn("P", grid)
        corridor = next(r for r in rows if ">>>>>" in r)
        self.assertEqual(corridor.count(">"), 5)
        # Safe floor left of the corridor to read the room.
        spawn = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "P"][0]
        fan_xs = [x for x, ch in enumerate(corridor) if ch == ">"]
        self.assertLess(spawn[0], min(fan_xs))
        self.assertEqual(rows[spawn[1]][spawn[0]], "P")
        # Two orbs on the far (right) side of the corridor.
        self.assertEqual(grid.count("*"), 2)
        orbs = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "*"]
        # Far side is beyond the wall divider (the first fan tile).
        self.assertTrue(all(x > min(fan_xs) for x, _ in orbs))

    def test_assets_bundled_and_present(self):
        manifest = json.loads(
            (ROOT / "tools" / "static" / "packs" / "fan" / "manifest.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "fan")
        for entry in manifest["assets"]:
            if not entry.get("bundled"):
                continue
            path = (ROOT / "tools" / "static" / "packs" / "fan" / "assets"
                    / entry["file"])
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            import struct
            w, h = struct.unpack(">II", data[16:24])
            self.assertEqual((w, h), (512, 512), entry["file"])


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function snap(s) {
  return { pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left, t_ms: s.t_ms };
}
function run(seq) {
  let s = core.initialState(level, 'mech-10-fan-tile-room');
  const snaps = [snap(s)];
  for (const inp of seq) {
    s = core.step(s, inp);
    snaps.push(snap(s));
  }
  return { snaps, finalState: s };
}
function navToFan() {
  return [
    { t_ms: 100, input: 'right' },
    { t_ms: 200, input: 'right' },
    { t_ms: 300, input: 'right' },
    { t_ms: 400, input: 'right' },
    { t_ms: 500, input: 'down' },
    { t_ms: 600, input: 'down' },
    { t_ms: 700, input: 'right' },
  ];
}
// A: solution - ride the wind across, collect both orbs, fight back.
// Ride: waits at +1s intervals push east across the corridor to
// (11,3); then up to the upper orb and across/down to the lower.
// Fight back: re-enter the corridor from the east and move west
// twice inside one recorded second to beat the next push.
const solutionSeq = [
  ...navToFan(),
  { t_ms: 1200, input: 'wait' },
  { t_ms: 2200, input: 'wait' },
  { t_ms: 3200, input: 'wait' },
  { t_ms: 4200, input: 'wait' },
  { t_ms: 5200, input: 'wait' },
  // on far floor (11,3); go up to upper orb at (9,1)
  { t_ms: 5300, input: 'up' },
  { t_ms: 5400, input: 'up' },
  { t_ms: 5500, input: 'left' },
  { t_ms: 5600, input: 'left' },
  // to lower orb at (10,5)
  { t_ms: 5700, input: 'right' },
  { t_ms: 5800, input: 'right' },
  { t_ms: 5900, input: 'down' },
  { t_ms: 6000, input: 'down' },
  { t_ms: 6100, input: 'down' },
  { t_ms: 6200, input: 'down' },
  { t_ms: 6300, input: 'left' },
  // fight the wind: back up to the corridor and dash west fast
  { t_ms: 6400, input: 'up' },
  { t_ms: 6500, input: 'up' },
  { t_ms: 6600, input: 'left' },
  { t_ms: 6700, input: 'left' },
  { t_ms: 6800, input: 'left' },
  { t_ms: 6900, input: 'left' },
  { t_ms: 7000, input: 'left' },
];
const solution = run(solutionSeq);
// B: adversarial - standing in the corridor to think.
const adv = run([
  ...navToFan(),
  { t_ms: 1200, input: 'wait' },
  { t_ms: 2200, input: 'wait' },
]);
// C: boundary - sub-second no push, one tile per second, big gap once.
const boundary = (function () {
  let s = core.initialState(level, 'mech-10-fan-tile-room');
  for (const inp of navToFan()) s = core.step(s, inp);
  const atFan = snap(s);
  const sub = snap(core.step(s, { t_ms: 900, input: 'wait' }));
  const gap = snap(core.step(s, { t_ms: 4000, input: 'wait' }));
  const nextSec = snap((function () {
    let x = core.step(s, { t_ms: 4000, input: 'wait' });
    return core.step(x, { t_ms: 5000, input: 'wait' });
  })());
  return { atFan, sub, gap, nextSec };
})();
// D: blocked - fan-east tile whose downwind cell is a wall.
const blockedLevel = {
  name: 'fan-blocked', time_limit: 120, test: true,
  legend: {
    '.': { label: 'floor', sprite: 'floor_default.png' },
    '#': { label: 'wall', sprite: 'wall.png' },
    'P': { base: 'floor_default.png', label: 'player', sprite: 'jolly.png' },
    '>': { base: 'floor_default.png', label: 'fan east', def: 'fan:fan-east' },
  },
  rows: ['#####', '#P>##', '#####'],
};
const blocked = (function () {
  let s = core.initialState(blockedLevel, 'fan-blocked');
  s = core.step(s, { t_ms: 100, input: 'right' });
  const beforeWait = snap(s);
  s = core.step(s, { t_ms: 1200, input: 'wait' });
  const afterWait = snap(s);
  s = core.step(s, { t_ms: 2200, input: 'wait' });
  const afterWait2 = snap(s);
  return { beforeWait, afterWait, afterWait2 };
})();
// E: wind directions - north fan pushes up, west fan pushes left.
const dirLevel = function (ch, rows) {
  return { name: 'fan-dir', time_limit: 120, test: true,
    legend: {
      '.': { label: 'floor', sprite: 'floor_default.png' },
      '#': { label: 'wall', sprite: 'wall.png' },
      'P': { base: 'floor_default.png', label: 'player', sprite: 'jolly.png' },
      '^': { base: 'floor_default.png', label: 'fan north', def: 'fan:fan-north' },
      '<': { base: 'floor_default.png', label: 'fan west', def: 'fan:fan-west' },
      'v': { base: 'floor_default.png', label: 'fan south', def: 'fan:fan-south' },
      '>': { base: 'floor_default.png', label: 'fan east', def: 'fan:fan-east' },
    }, rows: rows };
};
function dirCase(rows, moves, waitT) {
  const lvl = dirLevel('', rows);
  let s = core.initialState(lvl, 'fan-dir');
  for (const mv of moves) s = core.step(s, mv);
  const before = snap(s);
  s = core.step(s, { t_ms: waitT, input: 'wait' });
  return { before, after: snap(s) };
}
const northCase = dirCase(['#####', '#...#', '#.^.#', '#.P.#', '#####'],
  [{ t_ms: 100, input: 'up' }], 1200);
const westCase = dirCase(['#####', '#P<.#', '#####'],
  [{ t_ms: 100, input: 'right' }], 1200);
const southCase = (function () {
  const lvl = dirLevel('', ['#####', '#Pv.#', '#####']);
  let s = core.initialState(lvl, 'fan-dir');
  s = core.step(s, { t_ms: 100, input: 'right' });
  const before = snap(s);
  s = core.step(s, { t_ms: 1200, input: 'wait' });
  return { before, after: snap(s) };
})();
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-10-fan-tile-room');
const beforeJson = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
const fresh = core.initialState(level, 'mech-10-fan-tile-room');
console.log(JSON.stringify({
  solution: solution.snaps,
  adv: adv.snaps,
  boundary,
  blocked,
  northCase,
  westCase,
  southCase,
  pure: JSON.stringify(s0) === beforeJson,
  fresh: snap(fresh),
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class FanMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_rides_wind_across_and_collects(self):
        # YAML: solution ride and fight the wind
        snaps = self.r["solution"]
        # Nav lands on fan (6,3), each wait pushes one tile east.
        self.assertEqual(snaps[7]["pos"], {"x": 6, "y": 3})
        self.assertEqual(snaps[8]["pos"], {"x": 7, "y": 3})
        self.assertEqual(snaps[9]["pos"], {"x": 8, "y": 3})
        self.assertEqual(snaps[12]["pos"], {"x": 11, "y": 3})
        # Upper orb collected, then lower orb, then wind fought back.
        self.assertEqual(snaps[-1]["pos"], {"x": 5, "y": 3})
        self.assertEqual(snaps[-1]["orbs"], 0)

    def test_adversarial_standing_is_pushed_not_stranded(self):
        # YAML: adversarial standing to think
        adv = self.r["adv"]
        self.assertEqual(adv[7]["pos"], {"x": 6, "y": 3})
        self.assertEqual(adv[8]["pos"], {"x": 7, "y": 3})
        self.assertEqual(adv[9]["pos"], {"x": 8, "y": 3})
        self.assertEqual(adv[-1]["status"], "playing")

    def test_one_tile_per_second_and_blocked_no_push(self):
        # YAML: one tile per real second, blocked tile no push
        b = self.r["boundary"]
        self.assertEqual(b["atFan"]["pos"], {"x": 6, "y": 3})
        self.assertEqual(b["sub"]["pos"], {"x": 6, "y": 3})
        self.assertEqual(b["gap"]["pos"], {"x": 7, "y": 3})
        self.assertEqual(b["nextSec"]["pos"], {"x": 8, "y": 3})
        blk = self.r["blocked"]
        self.assertEqual(blk["beforeWait"]["pos"], {"x": 2, "y": 1})
        self.assertEqual(blk["afterWait"]["pos"], {"x": 2, "y": 1})
        self.assertEqual(blk["afterWait2"]["pos"], {"x": 2, "y": 1})

    def test_all_wind_directions_push_downwind(self):
        self.assertEqual(self.r["northCase"]["after"]["pos"], {"x": 2, "y": 1})
        self.assertEqual(self.r["westCase"]["after"]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["southCase"]["before"]["pos"], {"x": 2, "y": 1})
        self.assertEqual(self.r["southCase"]["after"]["pos"], {"x": 2, "y": 1})

    def test_step_is_pure_and_restart_restores(self):
        self.assertTrue(self.r["pure"])
        self.assertEqual(self.r["fresh"]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["fresh"]["orbs"], 2)

    def test_game_wires_in_fan_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/fan/main.js", html)
        core_js = (ROOT / "tools" / "static" / "game-core.js").read_text(encoding="utf-8")
        self.assertIn("packs/fan/main.js", core_js)
        self.assertIn("GamePackFan", core_js)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = [
  { t_ms: 100, input: 'right' },
  { t_ms: 200, input: 'right' },
  { t_ms: 300, input: 'right' },
  { t_ms: 400, input: 'right' },
  { t_ms: 500, input: 'down' },
  { t_ms: 600, input: 'down' },
  { t_ms: 700, input: 'right' },
  { t_ms: 1200, input: 'wait' },
  { t_ms: 2200, input: 'wait' },
  { t_ms: 3200, input: 'wait' },
  { t_ms: 4200, input: 'wait' },
  { t_ms: 5200, input: 'wait' },
  { t_ms: 5300, input: 'up' },
  { t_ms: 5400, input: 'up' },
  { t_ms: 5500, input: 'left' },
  { t_ms: 5600, input: 'left' },
  { t_ms: 5700, input: 'right' },
  { t_ms: 5800, input: 'right' },
  { t_ms: 5900, input: 'down' },
  { t_ms: 6000, input: 'down' },
  { t_ms: 6100, input: 'down' },
  { t_ms: 6200, input: 'down' },
  { t_ms: 6300, input: 'left' },
  { t_ms: 6400, input: 'up' },
  { t_ms: 6500, input: 'up' },
  { t_ms: 6600, input: 'left' },
  { t_ms: 6700, input: 'left' },
  { t_ms: 6800, input: 'left' },
  { t_ms: 6900, input: 'left' },
  { t_ms: 7000, input: 'left' },
];
const log = inputs;
let live = core.initialState(level, 'mech-10-fan-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-10-fan-tile-room', log);
const replayed2 = core.replay(level, 'mech-10-fan-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left },
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
        # YAML: restart and replay
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 5, "y": 3}, "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 30)


if __name__ == "__main__":
    unittest.main()
