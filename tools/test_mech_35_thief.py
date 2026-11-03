"""Checks for the thief (mech-35-thief).

The mechanic lives in the pure GameCore step (packs/thief/main.js);
driven here under Node against the teaching room. Rules: the thief
moves one tile per player move away from the player and is not
lethal; if it starts a move next to the player it snatches the most
recent key, carries it visibly, runs for its burrow tile and drops
the key there for re-pickup; cornering and touching it first drops
the key where it stands; restart (fresh state) restores the room.

YAML test_cases coverage (enemies-and-bots.yml #35):
- "corner it and recover the key" -> ThiefMechanicTests B flow
- "adversarial straight walk at it" -> A flow (snatch + burrow)
- "snatch only from beside the player" -> adjacency/boundary tests
- "slide to cut it off" -> blocked-by ice tile, skipped with reason
- "restart and replay" -> SanityReplayTests + restart test

Run with: python -m unittest tools.test_mech_35_thief -v
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

LEVEL_ID = "mech-35-thief-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class ThiefRoomLevelTests(unittest.TestCase):
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
        # Player, one red key, one thief, its burrow, lock + warp.
        self.assertEqual(grid.count("P"), 1)
        self.assertEqual(grid.count("r"), 1)
        self.assertEqual(grid.count("T"), 1)
        self.assertEqual(grid.count("B"), 1)
        self.assertEqual(grid.count("R"), 1)
        self.assertEqual(grid.count("X"), 1)
        self.assertEqual(self.level["legend"]["T"]["actor"], "thief:thief")
        self.assertEqual(self.level["legend"]["B"]["def"], "thief:burrow")
        # The burrow sits in the far corner from the player start, so
        # the naive chase really does reveal somewhere unnoticed.
        px = next((x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "P")
        bx = next((x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "B")
        self.assertGreater(bx[0], px[0])
        self.assertGreater(bx[1], px[1])


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function snapOf(s) {
  const t = s.actors.find((a) => a.def === 'thief:thief');
  return { pos: { ...s.player },
    thief: { x: t.x, y: t.y, carrying: t.flags.carrying || null },
    inv: core.readout(s).inventory, status: s.status, grid: s.grid };
}
function run(seq) {
  let s = core.initialState(level, 'mech-35-thief-room');
  const snaps = [snapOf(s)];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snapOf(s));
  });
  return snaps;
}
// A: adversarial straight walk at the thief (teaching moment): the
// key is snatched beside the player, carried to the burrow, dropped
// there, picked back up, and the room still completes.
const a = run(['right', 'right', 'right', 'right', 'right', 'down',
  'right', 'right', 'right', 'up', 'up',
  'down', 'down', 'down', 'down',
  'right', 'down', 'down', 'right',
  'left', 'up', 'left', 'right', 'right']);
// B: corner it and recover the key: cut off the burrow line, touch
// the thief before it deposits, it drops the key where it stands.
const b = run(['right', 'right', 'right', 'right', 'right', 'down',
  'right', 'right', 'right', 'right', 'right', 'right',
  'left', 'right']);
// C: corrected route along the far lane: no snatch, key kept, win.
const c = run(['right', 'right', 'down', 'down', 'down', 'down',
  'down', 'right', 'right', 'right', 'right', 'right', 'right',
  'right', 'right', 'up', 'up']);
// F: flee distances from a cold start (no key carried yet).
const f = run(['down', 'down', 'right', 'right', 'up', 'up']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-35-thief-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ a: a, b: b, c: c, f: f,
  fresh: snapOf(core.initialState(level, 'mech-35-thief-room')),
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class ThiefMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_flees_one_tile_per_player_move_and_is_not_lethal(self):
        f = self.r["f"]
        self.assertEqual(f[0]["thief"], {"x": 5, "y": 2, "carrying": None})
        expected = [(6, 2), (6, 1), (7, 1), (8, 1), (9, 1), (10, 1)]
        for i, (x, y) in enumerate(expected, start=1):
            self.assertEqual((f[i]["thief"]["x"], f[i]["thief"]["y"]), (x, y))
            prev = f[i - 1]["thief"]
            moved = abs(x - prev["x"]) + abs(y - prev["y"])
            self.assertEqual(moved, 1, "thief must move exactly one tile")
            self.assertEqual(f[i]["status"], "playing")

    def test_adversarial_straight_walk_snatches_and_drops_at_burrow(self):
        a = self.r["a"]
        # Key picked up on step 2 and held while closing in.
        self.assertEqual(a[2]["inv"], ["red"])
        self.assertEqual(a[10]["inv"], ["red"])
        self.assertIsNone(a[10]["thief"]["carrying"])
        # Step 11 starts beside the player: snatch (most recent key).
        self.assertEqual(a[11]["thief"]["carrying"], "keys:key-red")
        self.assertEqual(a[11]["inv"], [])
        self.assertEqual(a[11]["status"], "playing")
        # It runs for the burrow and drops the key there (11,5).
        self.assertEqual(a[15]["grid"][5], "#..........r#")
        self.assertIsNone(a[15]["thief"]["carrying"])
        # Never soft-locked: the player recovers the key at the
        # burrow, opens the lock and reaches the warp.
        self.assertEqual(a[19]["inv"], ["red"])
        self.assertEqual(a[-1]["status"], "won")
        # The recovered key is then spent on the red lock as usual.
        self.assertEqual(a[-1]["inv"], [])

    def test_corner_it_and_recover_the_key(self):
        b = self.r["b"]
        self.assertEqual(b[11]["thief"]["carrying"], "keys:key-red")
        # Step 12: the thief is cornered onto the player's cell and
        # touched before reaching the burrow; not lethal, and the
        # key drops where it stands (11,2), not at the burrow.
        self.assertEqual(b[12]["pos"], {"x": 11, "y": 2})
        self.assertEqual(b[12]["thief"], {"x": 11, "y": 2, "carrying": None})
        self.assertEqual(b[12]["status"], "playing")
        self.assertEqual(b[12]["grid"][2], "#..........r#")
        self.assertEqual(b[12]["grid"][5], "#..........B#")
        # Stepping back on it picks the key back up.
        self.assertEqual(b[14]["inv"], ["red"])

    def test_snatch_only_from_beside_the_player(self):
        # In the whole adversarial run the inventory is untouched
        # until the one start-of-move adjacency (step 11).
        a = self.r["a"]
        for i in range(2, 11):
            self.assertEqual(a[i]["inv"], ["red"], f"step {i}")
        # At a distance the thief never takes anything (flee run has
        # no key at all, and carrying stays empty throughout).
        for snap in self.r["f"]:
            self.assertIsNone(snap["thief"]["carrying"])

    def test_corrected_route_keeps_the_key_and_wins(self):
        c = self.r["c"]
        for snap in c:
            self.assertIsNone(snap["thief"]["carrying"])
        self.assertEqual(c[2]["inv"], ["red"])
        self.assertEqual(c[-1]["inv"], ["red"])
        self.assertEqual(c[-1]["status"], "won")

    def test_restart_restores_thief_burrow_and_key(self):
        fresh = self.r["fresh"]
        self.assertEqual(fresh["pos"], {"x": 1, "y": 1})
        self.assertEqual(fresh["thief"], {"x": 5, "y": 2, "carrying": None})
        self.assertEqual(fresh["inv"], [])
        self.assertEqual(fresh["grid"][1], "#P.r........#")
        self.assertEqual(fresh["grid"][5], "#..........B#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_thief_and_carrying_pose(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("actor.def !== 'thief:thief'", js)
        self.assertIn("thief-carrying-key.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/thief/main.js", html)

    @unittest.skip("blocked-by: 1 (ice tile): mech-1 ice tile is not "
                   "built on main yet, so sliding to cut off the "
                   "escape line cannot be exercised in this room")
    def test_slide_to_cut_it_off(self):
        raise AssertionError("unreachable while ice tile is unbuilt")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'right', 'right', 'down',
  'right', 'right', 'right', 'up', 'up',
  'down', 'down', 'down', 'down',
  'right', 'down', 'down', 'right',
  'left', 'up', 'left', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-35-thief-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-35-thief-room', log);
const replayed2 = core.replay(level, 'mech-35-thief-room',
  JSON.parse(JSON.stringify(log)));
const thiefOf = (s) => s.actors.find((a) => a.def === 'thief:thief');
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    inv: core.readout(live).inventory, status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  thiefFinal: { ...thiefOf(live) },
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
        self.assertEqual(self.r["liveFinal"]["status"], "won")
        # Recovered at the burrow, then spent on the red lock.
        self.assertEqual(self.r["liveFinal"]["inv"], [])
        self.assertEqual(self.r["replaySteps"], 24)


if __name__ == "__main__":
    unittest.main()
