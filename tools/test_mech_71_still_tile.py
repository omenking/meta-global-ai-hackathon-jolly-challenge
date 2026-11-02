"""Checks for the still tile (mech-71-still-tile).

The mechanic lives in the pure GameCore step (packs/still/main.js);
driven here under Node against the teaching room. Rules: while the
player stands on the still tile the timer holds at its value and
resumes from that value on the step off; standing beside the tile
never pauses it; restart (fresh state) restores the running clock.
Guard-dependent YAML cases are blocked-by mechanic 37 (guard),
which is not built on this branch: they are explicit skips below,
never fake passes.

Run with: python -m unittest tools.test_mech_71_still_tile -v
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

LEVEL_ID = "mech-71-still-tile-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class StillRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("S"), 1)
        self.assertEqual(grid.count("*"), 1)
        self.assertEqual(grid.count("X"), 1)
        still = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "S"]
        spawn = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "P"]
        orb = [(x, y) for y, r in enumerate(rows)
               for x, ch in enumerate(r) if ch == "*"]
        # Still tile on the main path between spawn and orb.
        self.assertEqual(spawn, [(1, 1)])
        self.assertEqual(still, [(4, 1)])
        self.assertEqual(orb, [(10, 1)])


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function snap(s) {
  return { pos: { ...s.player }, left: s.time_left_s,
    elapsed: s.elapsed_s, held: !!(s.flags && s.flags['still:held']),
    heldMs: (s.counters && s.counters['still:held_ms']) || 0,
    status: s.status, orbs: core.readout(s).orbs_left };
}
function run(pairs) {
  let s = core.initialState(level, 'mech-71-still-tile-room');
  const snaps = [snap(s)];
  for (const [t_ms, input] of pairs) {
    s = core.step(s, { t_ms, input });
    snaps.push(snap(s));
  }
  return snaps;
}
// A: onto the tile, hold over real seconds, step off, resume.
const a = run([[1000, 'right'], [2000, 'right'], [3000, 'right'],
  [8000, 'up'], [13000, 'up'], [14000, 'right'], [15000, 'right']]);
// B: stand adjacent and wait - the timer must keep running.
const b = run([[1000, 'right'], [2000, 'right'], [7000, 'up']]);
// C: full solution - hold on S, cross to the orb, exit via warp.
const c = run([[1000, 'right'], [2000, 'right'], [3000, 'right'],
  [9000, 'up'], [10000, 'right'], [11000, 'right'], [12000, 'right'],
  [13000, 'right'], [14000, 'right'], [15000, 'right'],
  [16000, 'left'], [17000, 'left'], [18000, 'left'], [19000, 'left'],
  [20000, 'down'], [21000, 'down']]);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-71-still-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 1000, input: 'right' });
console.log(JSON.stringify({ a, b, c,
  fresh: snap(core.initialState(level, 'mech-71-still-tile-room')),
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class StillMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_timer_runs_until_the_tile_is_reached(self):
        a = self.r["a"]
        self.assertEqual(a[0]["left"], 60)
        self.assertFalse(a[0]["held"])
        # Adjacent to the tile at (3,1): still running.
        self.assertEqual(a[2]["pos"], {"x": 3, "y": 1})
        self.assertEqual(a[2]["left"], 58)
        self.assertFalse(a[2]["held"])

    def test_pause_only_while_standing(self):
        # YAML: 'pause only while standing'.
        a = self.r["a"]
        self.assertEqual(a[3]["pos"], {"x": 4, "y": 1})
        self.assertTrue(a[3]["held"])
        self.assertEqual(a[3]["left"], 57)
        # Blocked pushes keep the player on the tile over 10 real
        # seconds (t 3000 -> 13000): the held value never moves.
        self.assertEqual(a[4]["pos"], {"x": 4, "y": 1})
        self.assertEqual(a[4]["left"], 57)
        self.assertEqual(a[4]["heldMs"], 5000)
        self.assertEqual(a[5]["left"], 57)
        self.assertEqual(a[5]["heldMs"], 10000)

    def test_stepping_off_resumes_from_the_held_value(self):
        a = self.r["a"]
        # The step off itself was spent on the tile: still held.
        self.assertEqual(a[6]["pos"], {"x": 5, "y": 1})
        self.assertFalse(a[6]["held"])
        self.assertEqual(a[6]["left"], 57)
        # The next second of recorded time counts again.
        self.assertEqual(a[7]["left"], 56)

    def test_standing_adjacent_never_pauses(self):
        b = self.r["b"]
        self.assertEqual(b[2]["pos"], {"x": 3, "y": 1})
        self.assertFalse(b[2]["held"])
        # Five waiting seconds beside the tile all count down.
        self.assertEqual(b[3]["left"], 53)
        self.assertEqual(b[3]["heldMs"], 0)

    def test_solution_hold_cross_and_exit(self):
        c = self.r["c"]
        self.assertEqual(c[3]["pos"], {"x": 4, "y": 1})
        self.assertTrue(c[3]["held"])
        # Six held seconds (t 3000 -> 9000) cost no time.
        self.assertEqual(c[4]["left"], 57)
        self.assertEqual(c[10]["pos"], {"x": 10, "y": 1})
        self.assertEqual(c[10]["orbs"], 0)
        self.assertEqual(c[16]["pos"], {"x": 6, "y": 3})
        self.assertEqual(c[16]["status"], "won")

    def test_player_can_always_step_off_no_stranded_state(self):
        # Non-guard half of YAML 'adversarial waiting for the guard
        # to turn': leaving the tile is always available.
        c = self.r["c"]
        self.assertEqual(c[5]["pos"], {"x": 5, "y": 1})
        self.assertEqual(c[5]["status"], "playing")

    def test_restart_restores_the_running_clock(self):
        # YAML: 'restart and replay' (restart half).
        fresh = self.r["fresh"]
        self.assertEqual(fresh["left"], 60)
        self.assertEqual(fresh["heldMs"], 0)
        self.assertFalse(fresh["held"])
        self.assertEqual(fresh["pos"], {"x": 1, "y": 1})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_assets_are_bundled_512_pngs(self):
        pack = ROOT / "tools" / "static" / "packs" / "still"
        manifest = json.loads((pack / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "still")
        self.assertEqual([a["file"] for a in manifest["assets"]],
                         ["still.png", "still-held.png",
                          "jolly-still.png", "timer-held.png"])
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"], entry["file"])
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])

    def test_game_renders_the_held_state(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'S'", js)
        self.assertIn("timer-held.png", js)
        self.assertIn("jolly-still.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/still/main.js", html)


class GuardBlockedTests(unittest.TestCase):
    """YAML cases whose check needs the guard (mechanic 37), which
    is not built on this branch: explicit skips, never fake passes."""

    @unittest.skip("blocked-by: 37 (guard) - guard pack not on this "
                   "branch; solution crossing window untestable")
    def test_solution_think_then_move(self):
        pass

    @unittest.skip("blocked-by: 37 (guard) - guard cycle cannot "
                   "advance or wait without the guard pack")
    def test_adversarial_waiting_for_the_guard_to_turn(self):
        pass

    @unittest.skip("blocked-by: 37 (guard) - guard turn cadence "
                   "needs the guard pack")
    def test_guard_turns_on_inputs_not_on_the_pause(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const log = [[1000, 'right'], [2000, 'right'], [3000, 'right'],
  [9000, 'up'], [10000, 'right'], [11000, 'right'], [12000, 'right'],
  [13000, 'right'], [14000, 'right'], [15000, 'right'],
  [16000, 'left'], [17000, 'left'], [18000, 'left'], [19000, 'left'],
  [20000, 'down'], [21000, 'down']]
  .map(([t_ms, input]) => ({ t_ms, input }));
let live = core.initialState(level, 'mech-71-still-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-71-still-tile-room', log);
const replayed2 = core.replay(level, 'mech-71-still-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status,
    left: live.time_left_s },
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
        # YAML: 'restart and replay' (replay half).
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 6, "y": 3}, "orbs": 0,
                          "status": "won", "left": 46})
        self.assertEqual(self.r["replaySteps"], 16)


if __name__ == "__main__":
    unittest.main()
