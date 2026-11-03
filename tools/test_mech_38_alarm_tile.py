"""Checks for the alarm tile (mech-38-alarm-tile).

Rules (YAML #38): stepping on it rings once and wakes every sleeper
in the room immediately, then it becomes inert floor; it does not
wake sleepers in other rooms. Driven under Node against the
teaching room, mirroring test_mech_5_crumbling_tile.py.

Run with: python -m unittest tools.test_mech_38_alarm_tile -v
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

LEVEL_ID = "mech-38-alarm-tile-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class AlarmRoomLevelTests(unittest.TestCase):
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
        rows, grid = self.level["rows"], "".join(self.level["rows"])
        self.assertIn("P", grid)
        self.assertEqual(grid.count("A"), 1)
        self.assertEqual(grid.count("*"), 1)
        # Direct floor (top row) passes through the alarm; the rows
        # below are open floor, i.e. a longer way round exists.
        self.assertIn("A", rows[1])
        self.assertNotIn("A", rows[2])
        # Sleepers in the main room and in the sealed room below.
        self.assertEqual(grid.count("S"), 4)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-38-alarm-tile-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    rings: s.counters['alarm:rings'] || 0,
    mainSleepers: [s.objects[4][3], s.objects[4][11]],
    farSleepers: [s.objects[8][1], s.objects[8][13]],
    alarmDef: s.objects[1][4], row1: s.grid[1], row4: s.grid[4] });
  const snaps = [snap()];
  seq.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); snaps.push(snap()); });
  return snaps;
}
const quiet = run(['down', ...Array(10).fill('right'), 'up',
  ...Array(4).fill('left'), ...Array(5).fill('down')]);
const direct = run([...Array(10).fill('right'), ...Array(3).fill('down')]);
const twice = run(['right', 'right', 'right', 'left', 'right']);
const s0 = core.initialState(level, 'mech-38-alarm-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ quiet, direct, twice,
  fresh: { alarmDef: core.initialState(level, 'mech-38-alarm-tile-room').objects[1][4],
    mainSleepers: [core.initialState(level, 'mech-38-alarm-tile-room').objects[4][3]] },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class AlarmMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SCRIPT)

    def test_long_way_round_stays_quiet(self):
        q = self.r["quiet"]
        self.assertEqual(q[-1]["orbs"], 0)
        self.assertEqual(q[-1]["status"], "won")
        self.assertEqual(q[-1]["rings"], 0)
        self.assertEqual(q[-1]["mainSleepers"],
                         ["alarm:sleeper-asleep", "alarm:sleeper-asleep"])
        self.assertEqual(q[-1]["alarmDef"], "alarm:tile")

    def test_adversarial_direct_floor_wakes_the_room(self):
        d = self.r["direct"]
        self.assertEqual(d[3]["alarmDef"], "alarm:inert")
        self.assertEqual(d[3]["mainSleepers"],
                         ["alarm:sleeper-awake", "alarm:sleeper-awake"])
        self.assertEqual(d[3]["rings"], 1)
        # Touching a woken sleeper loses the attempt (retryable).
        self.assertEqual(d[-1]["status"], "lost")

    def test_rings_once_and_only_in_this_room(self):
        t = self.r["twice"]
        self.assertEqual(t[3]["rings"], 1)
        self.assertEqual(t[5]["rings"], 1)
        self.assertEqual(t[5]["alarmDef"], "alarm:inert")
        self.assertEqual(t[5]["farSleepers"],
                         ["alarm:sleeper-asleep", "alarm:sleeper-asleep"])
        d = self.r["direct"]
        self.assertEqual(d[3]["farSleepers"],
                         ["alarm:sleeper-asleep", "alarm:sleeper-asleep"])

    def test_restart_restores_alarm_and_sleepers(self):
        self.assertEqual(self.r["fresh"]["alarmDef"], "alarm:tile")
        self.assertEqual(self.r["fresh"]["mainSleepers"], ["alarm:sleeper-asleep"])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    @unittest.skip("blocked-by: 39 (decoy Jolly) - decoy mechanic not built yet")
    def test_wake_them_at_the_decoy(self):
        pass

    def test_game_wires_alarm_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("dt.ch === 'A'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/alarm/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', ...Array(10).fill('right'), 'up',
  ...Array(4).fill('left'), ...Array(5).fill('down')];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-38-alarm-tile-room');
for (const e of log) live = core.step(live, e);
const replayed = core.replay(level, 'mech-38-alarm-tile-room', log);
const replayed2 = core.replay(level, 'mech-38-alarm-tile-room', JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, orbs: core.readout(live).orbs_left, status: live.status },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
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
        self.assertEqual(self.r["liveFinal"]["orbs"], 0)


if __name__ == "__main__":
    unittest.main()
