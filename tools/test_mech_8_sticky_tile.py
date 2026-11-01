"""Checks for the sticky tile (mech-8-sticky-tile).

The mechanic lives in the pure GameCore step (packs/sticky);
driven here under Node against the teaching room. Rules: entering
a sticky tile is a normal step; leaving it takes two inputs (the
first strains in place, the second steps off); the tile stays
reusable; enemies are not slowed (the exit rule is player-only —
the patroller integration itself is blocked-by mechanic 31).

Run with: python -m unittest tools.test_mech_8_sticky_tile -v
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

LEVEL_ID = "mech-8-sticky-tile-room"


class StickyRoomLevelTests(unittest.TestCase):
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
        # The shortcut is a 3-tile sticky bridge in the divider.
        bridge_row = next(r for r in rows if "SSS" in r)
        self.assertEqual(bridge_row.count("S"), 3)
        # An orb on the far side and one worth returning for.
        self.assertGreaterEqual(grid.count("*"), 2)
        bridge_xs = [x for x, ch in enumerate(bridge_row) if ch == "S"]
        far_orb = [(x, y) for y, r in enumerate(rows)
                   for x, ch in enumerate(r) if ch == "*"]
        self.assertTrue(any(x > max(bridge_xs) for x, _ in far_orb),
                        "no orb beyond the bridge")
        # The long way back: the bottom row crosses the divider line
        # on plain floor, so the sticky shortcut never soft-locks.
        bottom = rows[-2]
        self.assertEqual(bottom[min(bridge_xs):max(bridge_xs) + 1],
                         "." * len(bridge_xs))


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
  let s = core.initialState(level, 'mech-8-sticky-tile-room');
  const snap = () => {
    const p = s.actors.find((a) => a.id === 'player');
    return { pos: { ...s.player }, row: s.grid[2],
      status: s.status, orbs: core.readout(s).orbs_left,
      strained: !!(p && p.flags && p.flags.sticky_strained) };
  };
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toBridge = ['right', 'right', 'right', 'down'];
// A: cross the sticky bridge one tile at a time (solution cost).
const a = run([...toBridge, 'right', 'right', 'right', 'right',
  'right', 'right', 'right', 'up']);
// B: wall bump while on sticky, then the two-input exit.
const b = run([...toBridge, 'right', 'up', 'right', 'right']);
// C: cross, come back over the same tiles, cross again (reusable).
const c = run([...toBridge, 'right', 'right', 'right',
  'left', 'left', 'left', 'left', 'right', 'right', 'right']);
// D: full room — far orb over the bridge, long way home.
const d = run([...toBridge,
  'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'up', 'right', 'right', 'left', 'left',
  'down', 'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left',
  'left', 'up', 'up', 'up', 'up', 'up']);
// Enemy rule at pack level: a non-player actor is never vetoed.
const s0 = core.initialState(level, 'mech-8-sticky-tile-room');
const stickyDef = core.getTileDef('sticky:sticky');
const fakeEnemy = { id: 'actor-0', def: 'enemy:patroller',
  x: 5, y: 2, flags: {} };
const enemyBlocked = stickyDef.blocksExit(s0,
  { x: 5, y: 2 }, fakeEnemy, 'right');
// Purity: stepping must not mutate the state it was given.
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, d: d.snaps,
  dFinal: { pos: { ...d.final.player },
    orbs: core.readout(d.final).orbs_left },
  enemyBlocked: enemyBlocked,
  enemyFlags: fakeEnemy.flags,
  fresh: (() => { const f = core.initialState(level,
    'mech-8-sticky-tile-room');
    const p = f.actors.find((ac) => ac.id === 'player');
    return { pos: { ...f.player }, row: f.grid[2],
      strained: !!(p && p.flags && p.flags.sticky_strained) }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class StickyMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_sticky_shortcut_at_its_move_cost(self):
        a = self.r["a"]
        # Standing before the bridge, then entering is one step.
        self.assertEqual(a[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(a[5]["pos"], {"x": 5, "y": 2})
        self.assertFalse(a[5]["strained"])
        # First input on the tile strains in place; second steps off.
        self.assertEqual(a[6]["pos"], {"x": 5, "y": 2})
        self.assertTrue(a[6]["strained"])
        self.assertEqual(a[7]["pos"], {"x": 6, "y": 2})
        self.assertFalse(a[7]["strained"])
        # Every sticky tile on the crossing costs the same two inputs.
        self.assertEqual(a[8]["pos"], {"x": 6, "y": 2})
        self.assertTrue(a[8]["strained"])
        self.assertEqual(a[9]["pos"], {"x": 7, "y": 2})
        self.assertEqual(a[10]["pos"], {"x": 7, "y": 2})
        self.assertTrue(a[10]["strained"])
        self.assertEqual(a[11]["pos"], {"x": 8, "y": 2})
        self.assertEqual(a[12]["pos"], {"x": 8, "y": 1})
        self.assertEqual(a[12]["status"], "playing")

    def test_exactly_two_inputs_and_wall_bump_is_free(self):
        b = self.r["b"]
        self.assertEqual(b[5]["pos"], {"x": 5, "y": 2})
        # Bumping the wall above consumes nothing: still unstrained.
        self.assertEqual(b[6]["pos"], {"x": 5, "y": 2})
        self.assertFalse(b[6]["strained"])
        # One input never leaves; two always do.
        self.assertEqual(b[7]["pos"], {"x": 5, "y": 2})
        self.assertTrue(b[7]["strained"])
        self.assertEqual(b[8]["pos"], {"x": 6, "y": 2})
        self.assertFalse(b[8]["strained"])

    def test_tile_stays_reusable(self):
        c = self.r["c"]
        # Back over the same sticky tiles costs two inputs each again.
        self.assertEqual(c[7]["pos"], {"x": 6, "y": 2})
        self.assertEqual(c[8]["pos"], {"x": 6, "y": 2})
        self.assertTrue(c[8]["strained"])
        self.assertEqual(c[9]["pos"], {"x": 5, "y": 2})
        self.assertEqual(c[10]["pos"], {"x": 5, "y": 2})
        self.assertTrue(c[10]["strained"])
        self.assertEqual(c[11]["pos"], {"x": 4, "y": 2})
        # And crossing forward a second time still costs two per tile.
        self.assertEqual(c[12]["pos"], {"x": 5, "y": 2})
        self.assertEqual(c[13]["pos"], {"x": 5, "y": 2})
        self.assertTrue(c[13]["strained"])
        self.assertEqual(c[14]["pos"], {"x": 6, "y": 2})

    def test_long_way_home_and_both_orbs(self):
        self.assertEqual(self.r["dFinal"],
                         {"pos": {"x": 1, "y": 1}, "orbs": 0})

    def test_enemy_actor_is_never_vetoed(self):
        # Pack-level half of "enemies are not slowed": the exit rule
        # only ever applies to the player actor.
        self.assertFalse(self.r["enemyBlocked"])
        self.assertEqual(self.r["enemyFlags"], {})

    def test_restart_restores_the_room(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1},
                          "row": "#....SSS....#", "strained": False})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_the_sticky_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("jolly-straining.png", js)
        self.assertIn("sticky_strained", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/sticky/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'up', 'right', 'right', 'left', 'left',
  'down', 'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left',
  'left', 'up', 'up', 'up', 'up', 'up'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-8-sticky-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-8-sticky-tile-room', log);
const replayed2 = core.replay(level, 'mech-8-sticky-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row: replayed[replayed.length - 1].grid[2],
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
        self.assertEqual(self.r["row"], "#....SSS....#")
        self.assertEqual(self.r["replaySteps"], 33)


class BlockedByPatrollerTests(unittest.TestCase):
    """YAML cases whose check needs the patroller (mechanic 31)."""

    @unittest.skip("blocked-by: 31 (patroller) — patroller not built "
                   "yet; the player-side strain is covered by "
                   "StickyMechanicTests, never faked here")
    def test_adversarial_shortcut_under_the_patroller(self):
        pass

    @unittest.skip("blocked-by: 31 (patroller) — patroller not built "
                   "yet; the pack-level player-only rule is covered "
                   "by test_enemy_actor_is_never_vetoed")
    def test_enemies_are_not_slowed(self):
        pass


if __name__ == "__main__":
    unittest.main()
