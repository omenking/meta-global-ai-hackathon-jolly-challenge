"""Checks for the lava tile (mech-44-lava-tile).

The mechanic lives in the pure GameCore step (packs/lava-tile);
driven here under Node against the teaching room. Rules: stepping
on lava loses the attempt, lava never spreads, burns out or is
cancelled, and the room is won by routing around it. The ice case
is blocked-by mechanic 82 (ice block) and the dirt fill by
mechanic 90: no pushable blocks exist yet, so those checks are
explicit skips with reasons, never fake passes.

Run with: python -m unittest tools.test_mech_44_lava_tile -v
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

LEVEL_ID = "mech-44-lava-tile-room"


class LavaRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("L"), 3)
        lava = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "L"]
        self.assertEqual(sorted({x for x, _ in lava}), [6])
        orb = [(x, y) for y, r in enumerate(rows)
               for x, ch in enumerate(r) if ch == "*"]
        self.assertTrue(any(x > 6 for x, _ in orb),
                        "no orb beyond the lava column")
        # The route around: the row below the column is plain floor.
        self.assertNotIn("L", rows[4])
        self.assertIn("X", grid)


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
  let s = core.initialState(level, 'mech-44-lava-tile-room');
  const snap = () => ({ pos: { ...s.player }, grid: s.grid.slice(),
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
// A: naive straight line into the lava column.
const a = run(['right', 'right', 'right', 'right', 'right', 'right']);
// B: corrected route around below the column to orb + warp.
const b = run(['down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right',
  'right', 'right', 'right', 'right',
  'up', 'up', 'up', 'right']);
// C: hesitation and backtracking beside lava, then the route.
const c = run(['right', 'right', 'left', 'right', 'up',
  'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right',
  'right', 'right', 'right', 'right',
  'up', 'up', 'up', 'right']);
// D: long wander that never touches lava (permanence check).
const d = run(['down', 'down', 'down', 'right', 'right', 'right',
  'left', 'left', 'right', 'right', 'right', 'right',
  'right', 'right', 'right', 'right',
  'up', 'up', 'up', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-44-lava-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, d: d.snaps,
  fresh: core.initialState(level, 'mech-44-lava-tile-room').grid,
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class LavaMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_stepping_on_lava_loses_the_attempt(self):
        a = self.r["a"]
        self.assertEqual(a[4]["pos"], {"x": 5, "y": 1})
        self.assertEqual(a[4]["status"], "playing")
        self.assertEqual(a[5]["pos"], {"x": 6, "y": 1})
        self.assertEqual(a[5]["status"], "lost")

    def test_lava_is_unchanged_after_losing_and_state_freezes(self):
        a = self.r["a"]
        self.assertEqual(a[5]["grid"], a[0]["grid"])
        # A finished run is frozen: a further input changes nothing.
        self.assertEqual(a[6]["pos"], {"x": 6, "y": 1})
        self.assertEqual(a[6]["status"], "lost")
        self.assertEqual(a[6]["grid"], a[0]["grid"])

    def test_lava_never_spreads_or_burns_out(self):
        for snap in self.r["d"]:
            self.assertEqual("".join(snap["grid"]).count("L"), 3)
            self.assertEqual(snap["grid"][1][6], "L")
            self.assertEqual(snap["grid"][2][6], "L")
            self.assertEqual(snap["grid"][3][6], "L")

    def test_route_around_the_lava_wins(self):
        b = self.r["b"]
        self.assertEqual(b[-1]["pos"], {"x": 11, "y": 1})
        self.assertEqual(b[-1]["status"], "won")
        self.assertEqual(b[-1]["orbs"], 1)

    def test_hesitation_and_backtracking_never_soft_locks(self):
        c = self.r["c"]
        # Blocked push into the wall: still at spawn, still playing.
        self.assertEqual(c[5]["pos"], {"x": 3, "y": 1})
        self.assertEqual(c[5]["status"], "playing")
        self.assertEqual(c[-1]["status"], "won")

    def test_wander_then_route_still_wins(self):
        d = self.r["d"]
        self.assertEqual(d[-1]["pos"], {"x": 11, "y": 1})
        self.assertEqual(d[-1]["status"], "won")

    def test_restart_restores_the_room(self):
        self.assertEqual(self.r["fresh"][1], "#P....L...*X#")
        self.assertEqual(self.r["fresh"][2], "#.....L.....#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_the_lava_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/lava-tile/main.js", html)
        manifest = json.loads(
            (ROOT / "tools" / "static" / "packs" / "lava-tile"
             / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "lava-tile")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled], ["lava.png"])
        for entry in bundled:
            path = (ROOT / "tools" / "static" / "packs" / "lava-tile"
                    / "assets" / entry["file"])
            self.assertTrue(path.is_file(), entry["file"])

    def test_ice_does_not_cancel_lava(self):
        self.skipTest("blocked-by: 82 (ice block) - no pushable "
                      "blocks exist yet; pushing an ice block into "
                      "lava is untestable until mechanic 82 lands")

    def test_dirt_fills_lava(self):
        self.skipTest("blocked-by: 90 (dirt block) - no pushable "
                      "blocks exist yet; filling lava with dirt is "
                      "untestable until mechanic 90 lands")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right',
  'right', 'right', 'right', 'right',
  'up', 'up', 'up', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-44-lava-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-44-lava-tile-room', log);
const replayed2 = core.replay(level, 'mech-44-lava-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left, status: live.status },
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
                         {"pos": {"x": 11, "y": 1}, "orbs": 1,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 16)


if __name__ == "__main__":
    unittest.main()
