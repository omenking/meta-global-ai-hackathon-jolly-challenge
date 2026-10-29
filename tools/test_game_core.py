"""Determinism checks for the pure step function (game-core.js).

Drives the real JS core under Node: same level + same timestamped log
must replay to identical states, step must not mutate its input state,
and the timer must be a function of recorded t_ms only.

Run with: python -m unittest tools.test_game_core -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / "chip1.json"

SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const log = [
  { t_ms: 0, input: 'up' },
  { t_ms: 500, input: 'left' },
  { t_ms: 1250, input: 'down' },
  { t_ms: 2000, input: 'right' },
];
const a = core.replay(level, 'chip1', log);
const b = core.replay(level, 'chip1', JSON.parse(JSON.stringify(log)));
const before = JSON.stringify(a[0]);
core.step(a[0], log[0]);
const pure = JSON.stringify(a[0]) === before;
let backwards = false;
try { core.step(a[2], { t_ms: 100, input: 'up' }); } catch (e) { backwards = true; }
console.log(JSON.stringify({
  same: JSON.stringify(a) === JSON.stringify(b),
  pure: pure, backwards: backwards,
  digests: a.map(core.stateDigest),
  final: a[a.length - 1],
  player: a[0].player,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GameCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(
            ["node", "-e", SCRIPT, str(CORE), str(LEVEL)],
            capture_output=True, text=True, check=True)
        cls.result = json.loads(out.stdout.strip().splitlines()[-1])

    def test_same_log_replays_to_same_states(self):
        self.assertTrue(self.result["same"])

    def test_step_is_pure(self):
        self.assertTrue(self.result["pure"])

    def test_timer_derived_from_recorded_t_ms(self):
        final = self.result["final"]
        self.assertEqual(final["t_ms"], 2000)
        self.assertEqual(final["elapsed_s"], 2.0)
        self.assertEqual(final["steps"], 4)
        self.assertEqual(final["last_input"], "right")

    def test_backwards_time_rejected(self):
        self.assertTrue(self.result["backwards"])

    def test_player_starts_on_level_start_tile(self):
        level = json.loads(LEVEL.read_text(encoding="utf-8"))
        y = next(i for i, r in enumerate(level["rows"]) if "P" in r)
        self.assertEqual(self.result["player"],
                         {"x": level["rows"][y].index("P"), "y": y})


if __name__ == "__main__":
    unittest.main()
