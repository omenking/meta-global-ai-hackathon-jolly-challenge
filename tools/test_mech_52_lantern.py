"""Checks for the lantern (mech-52-lantern).

The mechanic lives in the pure GameCore step (packs/lantern);
driven here under Node against the teaching room. Rules: pickup
widens the light radius from two tiles to four for that room
only, leaving the room (exit tile E) ends it, waiting never
shrinks it because time does not consume it, and restart (fresh
state) restores the uncollected lantern and the two-tile radius.

Run with: python -m unittest tools.test_mech_52_lantern -v
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

LEVEL_ID = "mech-52-lantern-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "lantern" / "main.js"


class LanternRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("L"), 1)
        self.assertEqual(grid.count("E"), 1)
        self.assertEqual(grid.count("*"), 1)
        # Lantern near the entrance, orb down the search lane.
        self.assertEqual(rows[1].index("L"), 3)
        self.assertEqual(rows[1].index("*"), 9)
        # Exit halfway through, gate and portal in the next room.
        self.assertEqual(rows[4].index("E"), 5)
        self.assertEqual(rows[6].index("G"), 5)
        self.assertEqual(rows[7].index("X"), 5)


def run_core(script):
    out = subprocess.run(
        ["node", "-e", script, str(CORE), str(LEVEL), str(PACK)],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const pack = require(process.argv[3]);
function snap(s) {
  return { pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    radius: pack.lightRadius(s), held: pack.hasLantern(s),
    litOrb: pack.isLit(s, 9, 1),
    inv: core.readout(s).inventory };
}
function run(seq, waits) {
  let s = core.initialState(level, 'mech-52-lantern-room');
  const snaps = [snap(s)];
  seq.forEach((input, i) => {
    const t = waits ? waits[i] : (i + 1) * 100;
    s = core.step(s, { t_ms: t, input });
    snaps.push(snap(s));
  });
  return { snaps, final: s };
}
// Solution: pick up lantern, search at four tiles, collect orb,
// then leave through E, gate, portal.
const solution = run(['right','right','right','right','right','right',
  'right','right','left','left','left','left',
  'down','down','down','down','down','down']);
// Adversarial: pick up lantern, leave by E before searching.
const naive = run(['right','right','right','right',
  'down','down','down','down','down']);
// Boundary: stand at (4,1) then (5,1) with the lantern; orb at (9,1).
const boundary = run(['right','right','right','right']);
// Waiting: pick up lantern, then wait while t_ms jumps far ahead.
const waiting = run(['right','right','wait','wait','wait'],
  [100, 200, 20100, 40100, 60100]);
const s0 = core.initialState(level, 'mech-52-lantern-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution: solution.snaps, naive: naive.snaps,
  boundary: boundary.snaps, waiting: waiting.snaps,
  solFinal: snap(solution.final),
  fresh: { ...snap(s0), row: s0.grid[1] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class LanternMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_base_radius_before_pickup(self):
        fresh = self.r["fresh"]
        self.assertEqual(fresh["radius"], 2)
        self.assertFalse(fresh["held"])
        self.assertFalse(fresh["litOrb"])

    def test_pickup_widens_radius_to_four(self):
        # snaps[2] stands on the lantern tile at (3,1).
        s = self.r["solution"][2]
        self.assertEqual(s["pos"], {"x": 3, "y": 1})
        self.assertEqual(s["radius"], 4)
        self.assertTrue(s["held"])
        self.assertIn("lantern", s["inv"])

    def test_search_at_four_tiles_where_two_fails(self):
        b = self.r["boundary"]
        # At (4,1) the orb is five tiles away: dark even lit wider.
        self.assertEqual(b[3]["pos"], {"x": 4, "y": 1})
        self.assertFalse(b[3]["litOrb"])
        # At (5,1) it is exactly four away: lit with the lantern,
        # beyond the base two-tile radius from the same spot.
        self.assertEqual(b[4]["pos"], {"x": 5, "y": 1})
        self.assertEqual(b[4]["radius"], 4)
        self.assertTrue(b[4]["litOrb"])

    def test_solution_collects_orb_then_leaves_and_wins(self):
        self.assertEqual(self.r["solFinal"]["orbs"], 0)
        self.assertEqual(self.r["solFinal"]["status"], "won")
        self.assertEqual(self.r["solFinal"]["pos"], {"x": 5, "y": 7})

    def test_adversarial_exit_first_loses_light_and_gate_stays_shut(self):
        n = self.r["naive"]
        # snaps[7] steps on E at (5,4): the lantern ends there.
        self.assertEqual(n[7]["pos"], {"x": 5, "y": 4})
        self.assertEqual(n[7]["radius"], 2)
        self.assertFalse(n[7]["held"])
        self.assertNotIn("lantern", n[7]["inv"])
        # Orb still inside, gate shut, player not stranded.
        self.assertEqual(n[-1]["orbs"], 1)
        self.assertEqual(n[-1]["pos"], {"x": 5, "y": 5})
        self.assertEqual(n[-1]["status"], "playing")

    def test_waiting_never_shrinks_the_radius(self):
        w = self.r["waiting"]
        self.assertEqual(w[-1]["radius"], 4)
        self.assertTrue(w[-1]["held"])
        self.assertEqual(w[-1]["pos"], {"x": 3, "y": 1})

    def test_restart_restores_lantern_and_base_radius(self):
        fresh = self.r["fresh"]
        self.assertEqual(fresh["radius"], 2)
        self.assertIn("L", fresh["row"])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_orb_only_inside_radius(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("lanternPack.isLit(state, dt.x, dt.y)", js)
        self.assertIn("jolly-with-lantern.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/lantern/main.js", html)

    # YAML test_cases blocked by unbuilt mechanics: explicit skips,
    # never fake passes. The local room-exit/gate behaviour above
    # is real; the blocked tiles themselves are not built here.
    @unittest.skip("blocked-by: 16 (hidden orb) - hidden-orb tile not "
                   "built on main; lantern search uses the core orb")
    def test_yaml_solution_hidden_orb_blocked(self):
        pass

    @unittest.skip("blocked-by: 4 (one-way door) - one-way door tile "
                   "not built on main; exit tile E ends the lantern")
    def test_yaml_adversarial_one_way_door_blocked(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right','right','right','right','right','right',
  'right','right','left','left','left','left',
  'down','down','down','down','down','down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-52-lantern-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-52-lantern-room', log);
const replayed2 = core.replay(level, 'mech-52-lantern-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  final: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
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
        self.assertEqual(self.r["final"],
                         {"pos": {"x": 5, "y": 7}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 18)


if __name__ == "__main__":
    unittest.main()
