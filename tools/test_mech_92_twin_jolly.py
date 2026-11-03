"""Checks for Twin Jolly (mech-92-twin-jolly).

One input moves both Jollys: the kernel player plus a twin:second
actor driven by a controller repeating the recorded input. A blocked
one stays, orbs/keys are shared, either Jolly on the hazard loses for
both, and both must hold twin exits with no orbs left to win.

Run with: python -m unittest tools.test_mech_92_twin_jolly -v
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

LEVEL_ID = "mech-92-twin-jolly-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class TwinRoomLevelTests(unittest.TestCase):
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
        self.assertIn("Q", grid)
        self.assertIn("H", grid)
        q = [(x, y) for y, r in enumerate(rows)
             for x, ch in enumerate(r) if ch == "Q"][0]
        hazard = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "H"][0]
        # Hazard sits one east step from the twin: the naive east
        # move for the watched Jolly kills the twin.
        self.assertEqual(hazard, (q[0] + 1, q[1]))
        self.assertEqual(grid.count("E"), 2)
        self.assertEqual(grid.count("*"), 2)
        self.assertIn("r", grid)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function actors(s) {
  const p = s.actors.find((a) => a.id === 'player');
  const t = s.actors.find((a) => a.def === 'twin:second');
  return { player: { x: p.x, y: p.y }, twin: { x: t.x, y: t.y } };
}
function run(seq) {
  let s = core.initialState(level, 'mech-92-twin-jolly-room');
  const snap = () => ({ ...actors(s), status: s.status,
    orbs: core.readout(s).orbs_left,
    inv: core.readout(s).inventory });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// BFS over joint states for a winning input sequence.
function solve() {
  const start = core.initialState(level, 'mech-92-twin-jolly-room');
  const keyOf = (s) => JSON.stringify({ a: actors(s),
    o: s.objects, i: s.inventory, c: s.counters, st: s.status });
  const seen = new Set([keyOf(start)]);
  const queue = [{ s: start, path: [] }];
  while (queue.length) {
    const { s, path } = queue.shift();
    if (s.status === 'won') return path;
    if (path.length >= 80) continue;
    for (const input of ['up', 'down', 'left', 'right']) {
      const n = core.step(s, { t_ms: (path.length + 1) * 100, input });
      const k = keyOf(n);
      if (seen.has(k)) continue;
      seen.add(k);
      queue.push({ s: n, path: [...path, input] });
    }
  }
  return null;
}
const solution = solve();
const naive = run(['right']);
const bump = run(['up']);
const twinKey = run(['up', 'up', 'right', 'right']);
const pure0 = core.initialState(level, 'mech-92-twin-jolly-room');
const before = JSON.stringify(pure0);
core.step(pure0, { t_ms: 100, input: 'up' });
console.log(JSON.stringify({ solution, solutionSnaps: solution ? run(solution) : null,
  naive, bump, twinKey, fresh: run([]), pure: JSON.stringify(pure0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class TwinMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_both_lanes_under_one_input(self):
        self.assertIsNotNone(self.r["solution"])
        final = self.r["solutionSnaps"][-1]
        self.assertEqual(final["status"], "won")
        self.assertEqual(final["orbs"], 0)
        # Both Jollys end on the two exits (one per lane).
        self.assertEqual({(final["player"]["x"], final["player"]["y"]),
                          (final["twin"]["x"], final["twin"]["y"])},
                         {(12, 1), (12, 6)})

    def test_adversarial_move_for_the_watched_jolly_only(self):
        naive = self.r["naive"]
        self.assertEqual(naive[1]["player"], {"x": 2, "y": 1})
        self.assertEqual(naive[1]["twin"], {"x": 2, "y": 6})
        self.assertEqual(naive[1]["status"], "lost")

    def test_blocked_one_stays_shared_collection(self):
        bump = self.r["bump"]
        # Player bumps the north wall and stays; the twin still moves.
        self.assertEqual(bump[1]["player"], {"x": 1, "y": 1})
        self.assertEqual(bump[1]["twin"], {"x": 1, "y": 5})
        # The twin alone walks onto the shared red key.
        key = self.r["twinKey"][-1]
        self.assertEqual(key["twin"], {"x": 3, "y": 4})
        self.assertEqual(key["inv"], ["red"])
        self.assertEqual(key["status"], "playing")

    @unittest.skip("blocked-by: 31 (patroller) — lethal-enemy contact "
                   "needs the unbuilt patroller; hazard half covered "
                   "by the adversarial case")
    def test_either_death_loses_for_both(self):
        pass

    def test_restart_restores_both_jollys(self):
        fresh = self.r["fresh"][0]
        self.assertEqual(fresh["player"], {"x": 1, "y": 1})
        self.assertEqual(fresh["twin"], {"x": 1, "y": 6})
        self.assertEqual(fresh["orbs"], 2)
        self.assertEqual(fresh["inv"], [])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_twin_pack_and_sprite(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("twin:second", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/twin/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function actors(s) {
  const p = s.actors.find((a) => a.id === 'player');
  const t = s.actors.find((a) => a.def === 'twin:second');
  return { player: { x: p.x, y: p.y }, twin: { x: t.x, y: t.y } };
}
function solve() {
  const start = core.initialState(level, 'mech-92-twin-jolly-room');
  const keyOf = (s) => JSON.stringify({ a: actors(s),
    o: s.objects, i: s.inventory, c: s.counters, st: s.status });
  const seen = new Set([keyOf(start)]);
  const queue = [{ s: start, path: [] }];
  while (queue.length) {
    const { s, path } = queue.shift();
    if (s.status === 'won') return path;
    if (path.length >= 80) continue;
    for (const input of ['up', 'down', 'left', 'right']) {
      const n = core.step(s, { t_ms: (path.length + 1) * 100, input });
      const k = keyOf(n);
      if (seen.has(k)) continue;
      seen.add(k);
      queue.push({ s: n, path: [...path, input] });
    }
  }
  return null;
}
const inputs = solve();
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-92-twin-jolly-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-92-twin-jolly-room', log);
const replayed2 = core.replay(level, 'mech-92-twin-jolly-room',
  JSON.parse(JSON.stringify(log)));
const last = replayed[replayed.length - 1];
console.log(JSON.stringify({ inputs,
  liveFinal: { ...actors(live), status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(last),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1 }));
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
        self.assertEqual(self.r["replaySteps"], len(self.r["inputs"]))


if __name__ == "__main__":
    unittest.main()
