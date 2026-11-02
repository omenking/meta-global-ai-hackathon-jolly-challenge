"""Checks for the dark room (mech-51-dark-room).

The mechanic lives in the dark-room pack: a level with
"dark_room": true stamps state.flags['dark:room'], and only
tiles within two tiles of Jolly (Chebyshev) are drawn; the HUD
still shows. Movement itself is unchanged kernel behaviour, so
dark floor is walkable and dark walls still block. Driven here
under Node against the teaching room.

Run with: python -m unittest tools.test_mech_51_dark_room -v
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

LEVEL_ID = "mech-51-dark-room-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class DarkRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        self.assertTrue(self.level["dark_room"])
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
        self.assertEqual(grid.count("*"), 2)
        spawn = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "P"][0]
        self.assertEqual(spawn, (1, 1))
        orbs = sorted((x, y) for y, r in enumerate(rows)
                      for x, ch in enumerate(r) if ch == "*")
        # One orb on the entrance corridor, one hidden orb south.
        self.assertIn((5, 1), orbs)
        self.assertIn((7, 6), orbs)
        # Hidden orb is outside the two-tile entrance light and
        # stays hidden from every tile of the corridor (y == 1).
        for ox, oy in orbs:
            if (ox, oy) == (7, 6):
                self.assertGreater(max(abs(ox - spawn[0]),
                                     abs(oy - spawn[1])), 2)
        gate = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "G"]
        self.assertEqual(gate, [(11, 1)])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-51-dark-room-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left, dark: !!(s.flags && s.flags['dark:room']),
    timer: core.readout(s).time_left_s });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const R = (n) => Array(n).fill('right'), L = (n) => Array(n).fill('left');
const D = (n) => Array(n).fill('down'), U = (n) => Array(n).fill('up');
// Solution: corridor, dive south to the hidden orb, back, exit.
const sol = run([...R(6), ...D(5), ...U(5), ...R(5)]);
// Adversarial: visible floor straight to the gate, then recover.
const adv = run([...R(10), ...L(3), ...D(5), ...U(5), ...R(5)]);
// Boundary probes from spawn (1,1) and after one step east.
const s0 = core.initialState(level, 'mech-51-dark-room-room');
const s1 = core.step(s0, { t_ms: 100, input: 'right' });
const vis = (s, x, y) => core.isDarkStateVisible(s, x, y);
// Dark movement: south into unseen floor works, north wall blocks.
const darkMove = run([...D(2), 'up', 'up', 'up']);
// Purity: stepping must not mutate the state it was given.
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, adv: adv.snaps, darkMove: darkMove.snaps,
  radius: core.DARK_LIGHT_RADIUS,
  atSpawn: { two: vis(s0, 3, 1), three: vis(s0, 4, 1),
    diag: vis(s0, 3, 3), hiddenOrb: vis(s0, 7, 6),
    corridorSeesHidden: vis({ ...s0, player: { x: 10, y: 1 },
      flags: s0.flags }, 7, 6) },
  afterMove: { pos: { ...s1.player }, two: vis(s1, 4, 1), three: vis(s1, 5, 1) },
  fresh: { pos: { ...core.initialState(level,
    'mech-51-dark-room-room').player },
    orbs: core.readout(core.initialState(level,
      'mech-51-dark-room-room')).orbs_left },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class DarkRoomMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_search_beyond_the_entrance_light(self):
        sol = self.r["sol"]
        self.assertEqual(sol[0]["orbs"], 2)
        self.assertTrue(sol[0]["dark"])
        # Hidden orb collected at the bottom of the dive (step 11).
        self.assertEqual(sol[11]["pos"], {"x": 7, "y": 6})
        self.assertEqual(sol[11]["orbs"], 0)
        self.assertEqual(sol[-1]["pos"], {"x": 12, "y": 1})
        self.assertEqual(sol[-1]["status"], "won")

    def test_adversarial_follow_only_the_visible_floor(self):
        adv = self.r["adv"]
        # Ten rights: nine moves land at (10,1); the tenth pushes
        # the shut gate and the player stays, one orb short.
        self.assertEqual(adv[10]["pos"], {"x": 10, "y": 1})
        self.assertEqual(adv[10]["orbs"], 1)
        self.assertEqual(adv[10]["status"], "playing")
        # Never stranded: backtrack, search south, exit and win.
        self.assertEqual(adv[-1]["pos"], {"x": 12, "y": 1})
        self.assertEqual(adv[-1]["status"], "won")
        self.assertTrue(all(s["status"] == "playing"
                            for s in adv[:-1]))

    def test_radius_boundary_at_two_tiles(self):
        self.assertEqual(self.r["radius"], 2)
        at = self.r["atSpawn"]
        self.assertTrue(at["two"])
        self.assertFalse(at["three"])
        self.assertTrue(at["diag"])
        self.assertFalse(at["hiddenOrb"])
        self.assertFalse(at["corridorSeesHidden"])
        moved = self.r["afterMove"]
        self.assertEqual(moved["pos"], {"x": 2, "y": 1})
        self.assertTrue(moved["two"])
        self.assertFalse(moved["three"])

    def test_dark_tiles_still_walkable_or_wall(self):
        dm = self.r["darkMove"]
        self.assertEqual(dm[2]["pos"], {"x": 1, "y": 3})
        self.assertEqual(dm[2]["status"], "playing")
        # Two ups return to spawn; the third hits the border wall.
        self.assertEqual(dm[5]["pos"], {"x": 1, "y": 1})
        self.assertEqual(dm[5]["status"], "playing")

    def test_hud_still_shows_in_the_dark(self):
        # Readout (orbs + timer) is state, not board: it answers
        # in the dark exactly as in a lit room.
        self.assertEqual(self.r["sol"][0]["orbs"], 2)
        self.assertIsNotNone(self.r["sol"][0]["timer"])
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dark:room", js)
        self.assertIn("darkOverlay", js)
        # HUD readouts are built independently of the overlay.
        self.assertIn("makeReadout('time')", js)
        self.assertIn("makeReadout('orbs')", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/dark-room/main.js", html)

    def test_restart_restores_the_room(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1}, "orbs": 2})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = [...Array(6).fill('right'), ...Array(5).fill('down'),
  ...Array(5).fill('up'), ...Array(5).fill('right')];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-51-dark-room-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-51-dark-room-room', log);
const replayed2 = core.replay(level, 'mech-51-dark-room-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
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
                         {"pos": {"x": 12, "y": 1},
                          "status": "won", "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 21)


if __name__ == "__main__":
    unittest.main()
