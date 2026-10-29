"""Checks for player movement and collision (player-movement).

Drives the real JS core under Node against the movement-room Test
Level: one tile per keypress on floor only, wall/lock/gate collision,
and replay to the same end state.

Run with: python -m unittest tools.test_player_movement -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / "movement-room.json"
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


MOVE_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const seq = ['right', 'right', 'down', 'left', 'up'];
let state = core.initialState(level, 'movement-room');
const start = { ...state.player };
const path = [start];
seq.forEach((input, i) => {
  state = core.step(state, { t_ms: (i + 1) * 100, input });
  path.push({ ...state.player });
});
const back = core.step(state, { t_ms: 600, input: 'left' });
// Non-direction input registers but does not move.
const idle = core.step(state, { t_ms: 700, input: null });
const replayed = core.replay(level, 'movement-room',
  seq.map((input, i) => ({ t_ms: (i + 1) * 100, input })));
console.log(JSON.stringify({
  start, path, final: state.player, steps: state.steps,
  idle: idle.player, idleSteps: idle.steps,
  replayFinal: replayed[replayed.length - 1].player,
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  liveDigest: core.stateDigest(state),
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MoveOneTileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_core(MOVE_SCRIPT)

    def test_starts_at_player_tile(self):
        self.assertEqual(self.result["start"], {"x": 2, "y": 2})

    def test_each_keypress_moves_exactly_one_tile_on_floor(self):
        path = self.result["path"]
        self.assertEqual(path, [
            {"x": 2, "y": 2}, {"x": 3, "y": 2}, {"x": 4, "y": 2},
            {"x": 4, "y": 3}, {"x": 3, "y": 3}, {"x": 3, "y": 2},
        ])
        for a, b in zip(path, path[1:]):
            self.assertEqual(abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]), 1)

    def test_recorded_session_replays_to_same_end_state(self):
        self.assertEqual(self.result["replayFinal"], self.result["final"])
        self.assertEqual(self.result["replayDigest"], self.result["liveDigest"])

    def test_non_direction_input_does_not_move(self):
        self.assertEqual(self.result["idle"], self.result["final"])
        self.assertEqual(self.result["idleSteps"],
                         self.result["steps"] + 1)


@unittest.skipUnless(shutil.which("node"), "node not available")
class MovementRoomTests(unittest.TestCase):
    def test_movement_room_is_valid_empty_room(self):
        level = game_levels.load_level(ROOT / "levels", "movement-room")
        self.assertTrue(level["test"])
        rows = level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        flat = "".join(rows)
        self.assertEqual(flat.count("P"), 1)
        for ch in "*G":
            self.assertNotIn(ch, flat)
        for row in rows:
            for ch in row:
                self.assertIn(ch, level["legend"])
        # Border is all wall, interior is floor or the player start.
        self.assertEqual(set(rows[0]), {"#"})
        self.assertEqual(set(rows[-1]), {"#"})
        for row in rows[1:-1]:
            self.assertTrue(row.startswith("#") and row.endswith("#"))
            self.assertLessEqual(set(row[1:-1]), {".", "P"})

    def test_movement_room_listed_as_test_level(self):
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn("movement-room", by_id)
        self.assertTrue(by_id["movement-room"]["test"])


if __name__ == "__main__":
    unittest.main()
