"""Checks for the final door (mech-100-final-door).

The mechanic lives in the pure GameCore step (packs/final-door);
driven here under Node against the teaching room. Rules: the door
checks the inventory, bot included, for at least one key of each
colour (red, gold, green, blue, silver) held at the same time; if
you hold them all it opens permanently and consumes none of them;
if any colour is missing it does nothing.

YAML test_cases coverage (keys-and-locks.yml #100):
- solution holding every colour at once: verified below.
- adversarial walking straight to the door: verified below.
- last-colour boundary: verified below (room + synthetic matrix).
- bot-held colours count: blocked-by 40 (Mule bot) -> skipped.
- restart and replay: fresh-state half verified below; the replay
  digest half is in SanityReplayTests (sanity-check task).

Run with: python -m unittest tools.test_mech_100_final_door -v
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

LEVEL_ID = "mech-100-final-door-room"
ALL_COLOURS = ["blue", "gold", "green", "red", "silver"]


class FinalDoorRoomLevelTests(unittest.TestCase):
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
        row = rows[1]
        # One colour's key sits back behind the spawn, the way you
        # came; the other four lie ahead along the corridor, the
        # final door closes the corridor, and the warp is beyond it.
        self.assertEqual(row.index("s"), 1)
        self.assertEqual(row.index("P"), 3)
        self.assertEqual(row.index("r"), 5)
        self.assertEqual(row.index("y"), 7)
        self.assertEqual(row.index("g"), 9)
        self.assertEqual(row.index("b"), 11)
        self.assertEqual(row.index("D"), 14)
        self.assertEqual(row.index("X"), 16)
        key_colours = {e.get("key_color")
                       for e in self.level["legend"].values()
                       if e.get("key_color")}
        self.assertEqual(key_colours,
                         {"red", "gold", "green", "blue", "silver"})
        self.assertEqual(self.level["legend"]["D"]["def"],
                         "final-door:closed")


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
  let s = core.initialState(level, 'mech-100-final-door-room');
  const snap = () => ({ pos: { ...s.player }, row: s.grid[1],
    status: s.status, inv: [...core.readout(s).inventory].sort(),
    door: s.objects[1][14] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const TO_DOORSTEP = Array(10).fill('right'); // (3,1) -> (13,1), 4 keys
// A: turn back for silver first, then cross with every colour.
const a = run(['left', 'left', ...Array(15).fill('right')]);
// B: walk straight to the door missing silver, press twice.
const b = run([...TO_DOORSTEP, 'right', 'right']);
// C: press missing one colour, walk the whole corridor back for
// it, return and press again holding every colour.
const c = run([...TO_DOORSTEP, 'right', ...Array(12).fill('left'),
  ...Array(15).fill('right')]);
// E: open the door, step back off it, walk through it again.
const e = run(['left', 'left', ...Array(13).fill('right'),
  'left', 'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-100-final-door-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, e: e.snaps,
  fresh: { row: core.initialState(level,
      'mech-100-final-door-room').grid[1],
    inv: core.readout(core.initialState(level,
      'mech-100-final-door-room')).inventory },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class FinalDoorMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_holding_every_colour_opens_and_keeps_keys(self):
        a = self.r["a"]
        # Standing on the opened door (14,1), then the warp wins.
        self.assertEqual(a[15]["pos"], {"x": 14, "y": 1})
        self.assertEqual(a[15]["door"], "final-door:open")
        self.assertEqual(a[15]["row"][14], "d")
        self.assertEqual(a[15]["inv"], ALL_COLOURS)
        self.assertEqual(a[17]["pos"], {"x": 16, "y": 1})
        self.assertEqual(a[17]["status"], "won")
        self.assertEqual(a[17]["inv"], ALL_COLOURS)

    def test_adversarial_straight_to_door_nothing_happens(self):
        b = self.r["b"]
        self.assertEqual(b[10]["pos"], {"x": 13, "y": 1})
        self.assertEqual(b[10]["inv"],
                         ["blue", "gold", "green", "red"])
        # Two presses: no move, no consumption, door still closed.
        self.assertEqual(b[12]["pos"], {"x": 13, "y": 1})
        self.assertEqual(b[12]["inv"], b[10]["inv"])
        self.assertEqual(b[12]["door"], "final-door:closed")
        self.assertEqual(b[12]["status"], "playing")

    def test_last_colour_boundary_then_opens_consuming_none(self):
        c = self.r["c"]
        # Press holding every colour but silver: nothing happens.
        self.assertEqual(c[11]["pos"], {"x": 13, "y": 1})
        self.assertEqual(c[11]["door"], "final-door:closed")
        self.assertEqual(c[11]["inv"],
                         ["blue", "gold", "green", "red"])
        # The whole corridor back reaches the silver key (1,1).
        self.assertEqual(c[23]["pos"], {"x": 1, "y": 1})
        self.assertEqual(c[23]["inv"], ALL_COLOURS)
        # Pressing again opens; every checked key is still held.
        self.assertEqual(c[36]["pos"], {"x": 14, "y": 1})
        self.assertEqual(c[36]["door"], "final-door:open")
        self.assertEqual(c[36]["inv"], ALL_COLOURS)
        self.assertEqual(c[38]["status"], "won")

    def test_open_door_stays_open_and_passable(self):
        e = self.r["e"]
        self.assertEqual(e[15]["pos"], {"x": 14, "y": 1})
        self.assertEqual(e[15]["door"], "final-door:open")
        self.assertEqual(e[16]["pos"], {"x": 13, "y": 1})
        self.assertEqual(e[16]["door"], "final-door:open")
        self.assertEqual(e[18]["pos"], {"x": 15, "y": 1})
        self.assertEqual(e[18]["inv"], ALL_COLOURS)

    def test_bot_held_colours_count_blocked_by_mule_bot(self):
        self.skipTest(
            "blocked-by: 40 (Mule bot): split the colours between "
            "the player slots and the mule bot slots so neither "
            "holds every colour alone, then press into the door; "
            "the mule bot (mechanic 40, enemies-and-bots.yml) is "
            "not built yet, so there is no bot inventory to split "
            "into. The door reads the single kernel inventory "
            "array, which is where bot-carried keys will live.")

    def test_restart_restores_closed_door_and_every_key(self):
        self.assertEqual(self.r["fresh"]["row"], "#s.P.r.y.g.b..D.X..#")
        self.assertEqual(self.r["fresh"]["inv"], [])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_open_door_sprite(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("final-door-open.png", js)
        self.assertIn("dt.ch === 'D'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/final-door/main.js", html)


MISSING_SCRIPT = r"""
const core = require(process.argv[1]);
const CH = { red: 'r', gold: 'y', green: 'g', blue: 'b', silver: 's' };
const COLOURS = Object.keys(CH);
function legend() {
  const l = { '.': { label: 'floor' }, '#': { label: 'wall' },
    'P': { label: 'player' }, 'X': { label: 'portal' },
    'D': { label: 'final door', def: 'final-door:closed' } };
  for (const c of COLOURS) l[CH[c]] = { label: 'key ' + c, key_color: c };
  return l;
}
function attempt(chars) {
  const row = '#P' + chars.join('') + 'D.X#';
  const level = { rows: ['#'.repeat(row.length), row,
    '#'.repeat(row.length)], legend: legend(), time_limit: 120 };
  let s = core.initialState(level, 'synthetic-room');
  const steps = chars.length + 1; // collect all placed, press door
  for (let i = 0; i < steps; i++) {
    s = core.step(s, { t_ms: (i + 1) * 100, input: 'right' });
  }
  return { pos: { ...s.player }, inv: [...core.readout(s).inventory].sort(),
    door: s.objects[1][2 + chars.length], status: s.status };
}
const missing = {};
for (const m of COLOURS) {
  missing[m] = attempt(COLOURS.filter((c) => c !== m).map((c) => CH[c]));
}
const duplicateOnly = attempt(['r', 'r', 'y', 'g', 'b']);
const allPlusDuplicate = attempt(['s', 'r', 'r', 'y', 'g', 'b']);
console.log(JSON.stringify({ missing, duplicateOnly, allPlusDuplicate }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class FinalDoorColourMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(MISSING_SCRIPT)

    def test_each_single_missing_colour_blocks_and_keeps_keys(self):
        for colour, got in self.r["missing"].items():
            self.assertEqual(got["door"], "final-door:closed", colour)
            self.assertEqual(got["status"], "playing", colour)
            self.assertEqual(len(got["inv"]), 4, colour)
            self.assertNotIn(colour, got["inv"], colour)

    def test_duplicate_of_a_held_colour_adds_nothing(self):
        got = self.r["duplicateOnly"]
        self.assertEqual(got["door"], "final-door:closed")
        self.assertEqual(got["inv"], ["blue", "gold", "green", "red", "red"])

    def test_all_colours_plus_a_duplicate_still_opens(self):
        got = self.r["allPlusDuplicate"]
        self.assertEqual(got["door"], "final-door:open")
        self.assertEqual(len(got["inv"]), 6)


if __name__ == "__main__":
    unittest.main()
