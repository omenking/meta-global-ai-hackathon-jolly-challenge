"""Checks for the one-way door (mech-4-one-way-door).

The mechanic lives in the pure GameCore step (packs/oneway/main.js);
driven here under Node against the teaching room. Rules: a door is
walkable only in its arrow direction and a wall from the other
three sides; passing through consumes nothing and never resets;
restart (fresh state) restores the room.

YAML test_cases (movement-tiles.yml mechanic 4):
- solution through and the long way back
- adversarial return the way you came
- wall from three sides, free in the arrow direction
- restart and replay
No case is blocked-by another mechanic, so no case is skipped.

Run with: python -m unittest tools.test_mech_4_one_way_door -v
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

LEVEL_ID = "mech-4-one-way-door-room"


class OneWayRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count(">"), 1)
        self.assertGreaterEqual(grid.count("*"), 1)
        door = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == ">"]
        self.assertEqual(door, [(6, 2)])
        orbs = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "*"]
        self.assertTrue(any(x > 6 for x, _ in orbs),
                        "no orb beyond the door")
        # The long way back: the bottom row crosses the divider
        # line on plain floor, so the room never soft-locks.
        bottom = rows[-2]
        self.assertEqual(bottom[6], ".")


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-4-one-way-door-room');
  const snap = () => ({ pos: { ...s.player },
    status: s.status, orbs: core.readout(s).orbs_left,
    inv: core.readout(s).inventory, row2: s.grid[2] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
// To the door threshold (5,2), through it, and to the orb.
const toOrb = ['down', 'right', 'right', 'right', 'right',
  'right', 'right', 'up', 'right'];
const a = run(toOrb);
// Adversarial: back west onto the door, then the long loop home.
const b = run([...toOrb, 'left', 'down', 'left',
  'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left',
  'up', 'up', 'up', 'up', 'up']);
// Repeat pass: loop home, then through the door a second time.
const c = run([...toOrb, 'left', 'down',
  'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left',
  'up', 'up', 'up', 'up', 'right', 'right', 'right', 'right',
  'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-4-one-way-door-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps,
  freshRow2: core.initialState(level,
    'mech-4-one-way-door-room').grid[2],
  pure: JSON.stringify(s0) === before,
}));
"""

# Synthetic probes: every door, entered from all four sides.
PROBE_SCRIPT = r"""
const core = require(process.argv[1]);
const legend = {
  '.': { label: 'floor', sprite: 'floor_default.png' },
  '#': { label: 'wall', sprite: 'wall.png' },
  'P': { base: 'floor_default.png', label: 'player', sprite: 'jolly.png' },
  '^': { base: 'floor_default.png', label: 'door north',
    sprite: 'one-way-door-north.png', text: '^', def: 'oneway:door-north' },
  '>': { base: 'floor_default.png', label: 'door east',
    sprite: 'one-way-door-east.png', text: '>', def: 'oneway:door-east' },
  'v': { base: 'floor_default.png', label: 'door south',
    sprite: 'one-way-door-south.png', text: 'v', def: 'oneway:door-south' },
  '<': { base: 'floor_default.png', label: 'door west',
    sprite: 'one-way-door-west.png', text: '<', def: 'oneway:door-west' },
};
function probe(doorCh, start, input) {
  const rows = ['#####', '#...#', '#...#', '#...#', '#####']
    .map((r) => r.split(''));
  rows[2][2] = doorCh;
  rows[start[1]][start[0]] = 'P';
  const lvl = { name: 'probe', time_limit: 120, test: true,
    tile: 64, legend: legend,
    rows: rows.map((r) => r.join('')) };
  let s = core.initialState(lvl, 'probe');
  s = core.step(s, { t_ms: 100, input: input });
  return { x: s.player.x, y: s.player.y };
}
const doors = {
  '^': { arrow: 'up', from: [2, 3], blocked: [
    ['down', [2, 1]], ['right', [1, 2]], ['left', [3, 2]]] },
  '>': { arrow: 'right', from: [1, 2], blocked: [
    ['left', [3, 2]], ['down', [2, 1]], ['up', [2, 3]]] },
  'v': { arrow: 'down', from: [2, 1], blocked: [
    ['up', [2, 3]], ['right', [1, 2]], ['left', [3, 2]]] },
  '<': { arrow: 'left', from: [3, 2], blocked: [
    ['right', [1, 2]], ['down', [2, 1]], ['up', [2, 3]]] },
};
const out = {};
for (const ch of Object.keys(doors)) {
  const d = doors[ch];
  out[ch] = { arrow: probe(ch, d.from, d.arrow),
    blocked: d.blocked.map((b) => probe(ch, b[1], b[0])) };
}
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class OneWayMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)
        cls.p = run_core(PROBE_SCRIPT)

    def test_solution_through_and_orb(self):
        a = self.r["a"]
        # snaps[5] stands at the threshold (5,2); snaps[6] is on
        # the door (6,2); snaps[9] collects the orb at (8,1).
        self.assertEqual(a[5]["pos"], {"x": 5, "y": 2})
        self.assertEqual(a[6]["pos"], {"x": 6, "y": 2})
        self.assertEqual(a[9]["pos"], {"x": 8, "y": 1})
        self.assertEqual(a[9]["orbs"], 0)
        self.assertEqual(a[9]["status"], "playing")

    def test_adversarial_return_the_way_you_came(self):
        b = self.r["b"]
        # snaps[9] on the orb, snaps[11] east of the door at (7,2),
        # snaps[12] presses west back through the door: wall.
        self.assertEqual(b[11]["pos"], {"x": 7, "y": 2})
        self.assertEqual(b[12]["pos"], {"x": 7, "y": 2})
        self.assertEqual(b[12]["status"], "playing")

    def test_long_loop_home_resolves_the_room(self):
        b = self.r["b"]
        self.assertEqual(b[-1]["pos"], {"x": 1, "y": 1})
        self.assertEqual(b[-1]["orbs"], 0)
        self.assertEqual(b[-1]["status"], "playing")

    def test_wall_from_three_sides_free_in_arrow(self):
        for ch, res in self.p.items():
            self.assertEqual(res["arrow"], {"x": 2, "y": 2}, ch)
            for stayed in res["blocked"]:
                self.assertNotEqual(stayed, {"x": 2, "y": 2}, ch)

    def test_never_consumes_and_never_resets(self):
        c = self.r["c"]
        # Second pass through the same door still works, with an
        # empty inventory and the door glyph unchanged throughout.
        self.assertEqual(c[-1]["pos"], {"x": 6, "y": 2})
        self.assertEqual(c[-1]["inv"], [])
        self.assertEqual(c[-1]["row2"], "#.....>.....#")
        self.assertEqual(self.r["a"][9]["inv"], [])

    def test_restart_restores_the_room(self):
        self.assertEqual(self.r["freshRow2"], "#.....>.....#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_the_pack(self):
        js = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("packs/oneway/main.js", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/oneway/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'right', 'right', 'right', 'right',
  'right', 'right', 'up', 'right', 'left', 'down', 'left',
  'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left',
  'up', 'up', 'up', 'up', 'up'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-4-one-way-door-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-4-one-way-door-room', log);
const replayed2 = core.replay(level, 'mech-4-one-way-door-room',
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
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 1, "y": 1}, "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 27)


if __name__ == "__main__":
    unittest.main()
