"""Checks for the current tile (mech-42-current-tile).

The mechanic lives in the pure GameCore step (packs/current plus
the kernel onBeforeMove hook); driven here under Node against the
teaching room. Rules: while on a current tile each directional
move first carries the player exactly one tile downstream, then
the player's own move happens; no drift on dry floor (banks /
islands); aiming straight at the 1-wide banked exit carries the
player past it, aiming upstream lands on it.

YAML test_cases 1-3 are marked blocked-by mech 61 (life
preserver, not built yet): they are explicit skipped-with-reason
checks below, never fake passes. The restart+replay case is not
blocked and runs for real.

Run with: python -m unittest tools.test_mech_42_current_tile -v
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

LEVEL_ID = "mech-42-current-tile-room"
BLOCKED_61 = ("blocked-by: 61 (life preserver): gear that admits "
              "the player to water is not built yet")


class CurrentRoomLevelTests(unittest.TestCase):
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
        stream = next(r for r in rows if ">" in r)
        # An unbroken east-flowing stream; two 1-wide bank exits
        # on its north side, first at x=6, later at x=10.
        self.assertEqual(stream, "#P>>>>>>>>>>#")
        north = rows[rows.index(stream) - 1]
        self.assertEqual(north[6], ".")
        self.assertEqual(north[10], ".")
        self.assertGreaterEqual(grid.count("*"), 2)


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
  let s = core.initialState(level, 'mech-42-current-tile-room');
  const snaps = [{ ...s.player }];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push({ ...s.player });
  });
  return { snaps, orbs: core.readout(s).orbs_left, status: s.status };
}
// Naive: swim to the tile below the x=6 bank, aim straight at it.
const naive = run(['right', 'right', 'right', 'up']);
// Corrected: bump upstream to x=5, then swim north onto the bank.
const corrected = run(['right', 'right', 'up', 'up', 'up']);
// Carried-past player swims on to the later x=10 bank.
const later = run(['right', 'right', 'right', 'up', 'right', 'up', 'up']);
const s0 = core.initialState(level, 'mech-42-current-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ naive, corrected, later,
  fresh: { ...core.initialState(level, 'mech-42-current-tile-room').player },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class CurrentMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_drift_carries_one_tile_before_the_own_move(self):
        # Entering the stream is from the bank (no drift yet);
        # each later east move nets drift + own move.
        self.assertEqual(self.r["corrected"]["snaps"],
                         [{"x": 1, "y": 3}, {"x": 2, "y": 3},
                          {"x": 4, "y": 3}, {"x": 5, "y": 3},
                          {"x": 6, "y": 2}, {"x": 6, "y": 1}])

    def test_aim_straight_at_exit_is_carried_past_it(self):
        self.assertEqual(self.r["naive"]["snaps"][-1], {"x": 7, "y": 3})
        self.assertEqual(self.r["naive"]["status"], "playing")

    def test_carried_past_player_reaches_a_later_bank(self):
        self.assertEqual(self.r["later"]["snaps"][-1], {"x": 10, "y": 1})
        self.assertEqual(self.r["later"]["orbs"], 1)

    def test_no_drift_on_dry_floor(self):
        # The corrected run's last step, bank (6,2) -> orb (6,1),
        # moves exactly one tile north with no downstream drift.
        snaps = self.r["corrected"]["snaps"]
        self.assertEqual(snaps[-2], {"x": 6, "y": 2})
        self.assertEqual(snaps[-1], {"x": 6, "y": 1})
        self.assertEqual(self.r["corrected"]["orbs"], 1)

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_wired_into_page_and_core(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/current/main.js", html)


class YamlBlockedByPreserverTests(unittest.TestCase):
    """YAML test_cases 1-3: blocked-by 61 (life preserver)."""

    @unittest.skip(BLOCKED_61)
    def test_solution_aim_upstream_of_the_bank(self):
        pass

    @unittest.skip(BLOCKED_61)
    def test_adversarial_aim_straight_at_the_exit(self):
        pass

    @unittest.skip(BLOCKED_61)
    def test_drift_before_every_swimming_move(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'up', 'up', 'up'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-42-current-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-42-current-tile-room', log);
const replayed2 = core.replay(level, 'mech-42-current-tile-room',
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

    def test_restart_restores_player_and_current(self):
        r = run_core(BEHAVIOUR_SCRIPT)
        self.assertEqual(r["fresh"], {"x": 1, "y": 3})

    def test_replay_reaches_the_same_end_state(self):
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 6, "y": 1}, "orbs": 1})
        self.assertEqual(self.r["liveDigest"], self.r["replayDigest"])
        self.assertEqual(self.r["replayDigest"], self.r["replay2Digest"])
        self.assertEqual(self.r["replaySteps"], 5)


if __name__ == "__main__":
    unittest.main()
