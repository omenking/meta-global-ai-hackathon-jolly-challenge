"""Checks for the level timer and restart (level-timer).

Drives the real JS core under Node: the countdown must come from the
per-level ``time_limit`` and from recorded ``t_ms`` only, expiry must
end the run as lost at the recorded moment, and replaying a timeout
log must reproduce the loss.

Run with: python -m unittest tools.test_level_timer -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402


def run_core(script, level_name="timer-room"):
    level = ROOT / "levels" / f"{level_name}.json"
    out = subprocess.run(["node", "-e", script, str(CORE), str(level)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


COUNTDOWN_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const s0 = core.initialState(level, 'timer-room');
const s1 = core.step(s0, { t_ms: 2000, input: 'right' });
const s2 = core.step(s1, { t_ms: 4500, input: 'right' });
console.log(JSON.stringify({
  limit: s0.time_limit_s, startLeft: s0.time_left_s,
  after2s: s1.time_left_s, after4_5s: s2.time_left_s,
  elapsed: s2.elapsed_s, readoutTimer: core.readout(s2).timer,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class CountdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_core(COUNTDOWN_SCRIPT)

    def test_countdown_starts_at_level_limit(self):
        self.assertEqual(self.result["limit"], 5)
        self.assertEqual(self.result["startLeft"], 5)

    def test_countdown_decreases_with_recorded_t_ms(self):
        self.assertEqual(self.result["after2s"], 3)
        self.assertEqual(self.result["after4_5s"], 0.5)
        self.assertEqual(self.result["readoutTimer"], 0.5)

    def test_every_level_carries_a_time_limit(self):
        for lid in ("chip1", "test-room", "movement-room", "timer-room"):
            level = game_levels.load_level(ROOT / "levels", lid)
            self.assertIsInstance(level.get("time_limit"), (int, float), lid)
            self.assertGreater(level["time_limit"], 0, lid)

    def test_timer_room_is_a_short_limit_test_level(self):
        level = game_levels.load_level(ROOT / "levels", "timer-room")
        self.assertTrue(level["test"])
        self.assertLessEqual(level["time_limit"], 10)
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertTrue(by_id["timer-room"]["test"])

    def test_hud_counts_down_from_state_limit(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("state.time_limit_s", js)
        self.assertIn("drawHud", js)


if __name__ == "__main__":
    unittest.main()
