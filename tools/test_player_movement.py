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


COLLISION_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function attempt(rows, input) {
  const lvl = { name: 't', rows, legend: level.legend };
  const s0 = core.initialState(lvl, 't');
  const s1 = core.step(s0, { t_ms: 100, input });
  return { from: s0.player, to: s1.player, steps: s1.steps };
}
const blockers = {};
// '*' and 'G' are no longer unconditional blockers: orbs-and-gate
// makes '*' collectible and 'G' passable at zero orbs (both states
// covered by tools/test_orbs_and_gate.py). 'X' is the warp:
// warp-and-levels makes stepping onto it win the run (covered by
// tools/test_warp_and_levels.py).
for (const ch of ['#', 'B', 'E', 'R', 'Y', 'b', 'g', 'r', 'y', '?']) {
  blockers[ch] = attempt(['###', '#P' + ch, '###'], 'right');
}
// Walls of the movement room: up, up (second hits border), then around.
let s = core.initialState(level, 'movement-room');
const wallPath = [];
for (const [i, input] of ['up', 'up', 'left', 'left', 'left'].entries()) {
  s = core.step(s, { t_ms: (i + 1) * 100, input });
  wallPath.push({ ...s.player });
}
// Off-grid blocks, floor and the start tile do not.
const open = { name: 't', rows: ['P.'], legend: level.legend };
let o = core.initialState(open, 't');
const offGrid = [];
for (const [i, input] of ['left', 'right', 'right', 'left'].entries()) {
  o = core.step(o, { t_ms: (i + 1) * 100, input });
  offGrid.push({ ...o.player });
}
console.log(JSON.stringify({ blockers, wallPath, offGrid,
  walkable: { floor: core.isWalkable(['.'], 0, 0),
              start: core.isWalkable(['P'], 0, 0),
              wall: core.isWalkable(['#'], 0, 0),
              gate: core.isWalkable(['G'], 0, 0) } }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class CollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_core(COLLISION_SCRIPT)

    def test_wall_lock_and_gate_block(self):
        for ch, r in self.result["blockers"].items():
            self.assertEqual(r["to"], r["from"], f"tile {ch!r} must block")
            self.assertEqual(r["steps"], 1)

    def test_movement_room_walls_block(self):
        self.assertEqual(self.result["wallPath"], [
            {"x": 2, "y": 1}, {"x": 2, "y": 1},
            {"x": 1, "y": 1}, {"x": 1, "y": 1}, {"x": 1, "y": 1},
        ])

    def test_off_grid_blocks_and_start_tile_is_walkable(self):
        self.assertEqual(self.result["offGrid"], [
            {"x": 0, "y": 0}, {"x": 1, "y": 0},
            {"x": 1, "y": 0}, {"x": 0, "y": 0},
        ])
        self.assertEqual(self.result["walkable"],
                         {"floor": True, "start": True,
                          "wall": False, "gate": False})


class SpriteFollowsStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Board construction moved to view/board.js in Phase 5b;
        # assertions follow the code, intent unchanged.
        cls.js = ((ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
            + (ROOT / "tools" / "static" / "view" / "board.js").read_text(
                encoding="utf-8"))

    def test_player_sprite_repositioned_from_state(self):
        self.assertIn("textures['jolly.png']", self.js)
        self.assertIn("playerSprite.position.set(state.player.x * TILE",
                      self.js)
        self.assertIn("getPlayerSpritePos", self.js)

    def test_start_tile_not_drawn_as_static_sprite(self):
        # The static board must not leave a second Jolly at the start.
        # Board resolves sprites via pack defs (spriteName) since the
        # pack-assets change; assertion follows the code.
        self.assertIn("spriteName && ch !== 'P'", self.js)


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
