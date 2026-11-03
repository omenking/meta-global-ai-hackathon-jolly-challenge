"""Checks for the checkpoint tile (mech-48-checkpoint-tile).

The mechanic lives in the pure GameCore step (packs/checkpoint-tile);
driven here under Node against the teaching room. Rules: stepping
on a checkpoint lights it and makes it the respawn (only the last
one touched is active); a hazard death with an active checkpoint
returns the player there with timer, orbs and keys as at the death;
with no checkpoint touched the hazard loses the attempt; restart
(fresh state) clears every active checkpoint.

Run with: python -m unittest tools.test_mech_48_checkpoint_tile -v
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

LEVEL_ID = "mech-48-checkpoint-tile-room"


class CheckpointRoomLevelTests(unittest.TestCase):
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
        # Two checkpoints (one per zone) and a hazard corridor.
        self.assertEqual(grid.count("K"), 2)
        self.assertGreaterEqual(grid.count("H"), 3)
        self.assertGreaterEqual(grid.count("*"), 2)
        k1 = [(x, y) for y, r in enumerate(rows)
              for x, ch in enumerate(r) if ch == "K"][0]
        # The first checkpoint sits one row off the direct y=4 line,
        # before the corridor hazards on that line.
        self.assertEqual(k1, (3, 3))
        self.assertIn("H", rows[4])
        hazard_xs = [x for x, ch in enumerate(rows[4]) if ch == "H"]
        self.assertTrue(all(x > k1[0] for x in hazard_xs))


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
  let s = core.initialState(level, 'mech-48-checkpoint-tile-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left, steps: s.steps,
    elapsed: s.elapsed_s,
    meta: JSON.parse(JSON.stringify(s.meta)),
    cp: (s.actors[0].flags || {}).checkpoint || null });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// Adversarial: direct y=4 line, never touching the checkpoint.
const naive = run(['down', 'down', 'down', 'right', 'right',
  'right', 'right', 'right', 'right']);
// Touch activates, death returns there (orb collected en route).
const death = run(['down', 'down', 'down', 'right', 'up', 'right',
  'down', 'right', 'right', 'right', 'right']);
// Solution: checkpoint, safe snake through the corridor, second
// checkpoint, far orb, warp out.
const solution = run(['down', 'down', 'down', 'right', 'up', 'right',
  'down', 'right', 'right', 'right', 'down', 'right', 'right',
  'right', 'up', 'right', 'right', 'right', 'right', 'right',
  'up', 'up', 'up', 'right', 'right', 'left', 'down']);
// Last one touched wins: after the second checkpoint, die back in
// the corridor and land on the second, not the first.
const second = run(['down', 'down', 'down', 'right', 'up', 'right',
  'down', 'right', 'right', 'right', 'down', 'right', 'right',
  'right', 'up', 'right', 'right', 'right', 'right', 'right',
  'up', 'down', 'left', 'left', 'left', 'left', 'down']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-48-checkpoint-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  naive: naive, death: death, solution: solution, second: second,
  freshMeta: core.initialState(level,
    'mech-48-checkpoint-tile-room').meta,
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class CheckpointMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_skip_checkpoint_death_loses_to_start(self):
        # YAML: adversarial skip the checkpoint. The direct line
        # collects the orb but dies at the first corridor hazard
        # with no respawn: the attempt is lost (restart from start).
        last = self.r["naive"][-1]
        self.assertEqual(last["pos"], {"x": 7, "y": 4})
        self.assertEqual(last["status"], "lost")
        self.assertEqual(last["cp"], None)

    def test_touch_lights_checkpoint(self):
        # YAML: touch activates. Standing on K1 lights only it.
        snap = self.r["death"][6]
        self.assertEqual(snap["pos"], {"x": 3, "y": 3})
        self.assertEqual(snap["meta"],
                         {"3,3": {"checkpoint_active": True}})
        self.assertEqual(snap["cp"], {"x": 3, "y": 3})

    def test_death_returns_with_timer_and_orbs_intact(self):
        # YAML: death returns there. The hazard teleports back to
        # K1; the run never resets, so the orb collected before the
        # checkpoint stays collected and the clock kept running.
        last = self.r["death"][-1]
        self.assertEqual(last["pos"], {"x": 3, "y": 3})
        self.assertEqual(last["status"], "playing")
        self.assertEqual(last["orbs"], 2)
        self.assertEqual(last["steps"], 11)
        self.assertAlmostEqual(last["elapsed"], 1.1)

    def test_last_checkpoint_touched_wins(self):
        # YAML: last one touched wins. After K2, K1 is unlit and a
        # corridor death lands on K2.
        at_k2 = self.r["solution"][21]
        self.assertEqual(at_k2["meta"]["14,3"],
                         {"checkpoint_active": True})
        self.assertEqual(at_k2["meta"]["3,3"],
                         {"checkpoint_active": False})
        last = self.r["second"][-1]
        self.assertEqual(last["pos"], {"x": 14, "y": 3})
        self.assertEqual(last["status"], "playing")
        self.assertEqual(last["cp"], {"x": 14, "y": 3})

    def test_solution_reaches_warp_and_wins(self):
        last = self.r["solution"][-1]
        self.assertEqual(last["pos"], {"x": 15, "y": 2})
        self.assertEqual(last["status"], "won")
        self.assertEqual(last["orbs"], 1)

    def test_restart_clears_every_checkpoint(self):
        self.assertEqual(self.r["freshMeta"], {})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_checkpoint_lit_state(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'K'", js)
        self.assertIn("checkpoint-on.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/checkpoint-tile/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
// A death-and-return session: touch K1, die in the corridor,
// respawn, cross safely, touch K2, take the far orb, warp out.
const inputs = ['down', 'down', 'down', 'right', 'up', 'right',
  'down', 'right', 'right', 'right', 'right',
  'down', 'right', 'right', 'right', 'down', 'right', 'right',
  'right', 'up', 'right', 'right', 'right', 'right', 'right',
  'up', 'up', 'up', 'right', 'right', 'left', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-48-checkpoint-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-48-checkpoint-tile-room', log);
const replayed2 = core.replay(level, 'mech-48-checkpoint-tile-room',
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
    """YAML: restart and replay — a recorded death-and-return
    session replays to the same end state."""

    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 15, "y": 2}, "orbs": 1,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 32)


if __name__ == "__main__":
    unittest.main()
