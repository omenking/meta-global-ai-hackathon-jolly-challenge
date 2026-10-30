"""Checks for the warp and level progression (warp-and-levels).

Stepping onto the portal ('X') behind the open gate wins the run in
the pure GameCore step (status 'won', frozen thereafter) and the
state names the next level in the ordered chain (level JSON 'next';
absent means last level). game.js closes the session as 'won' and
loads that next level. Driven here under Node against the real
orbs-room -> warp-room Test Level chain.

Run with: python -m unittest tools.test_warp_and_levels -v
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


def run_core(script, level_name="orbs-room"):
    level = ROOT / "levels" / f"{level_name}.json"
    out = subprocess.run(["node", "-e", script, str(CORE), str(level)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class WarpRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", "warp-room")

    def test_warp_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertTrue(by_id["warp-room"]["test"])

    def test_rows_rectangular_and_legend_covers_tiles(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_gated_portal_with_orb_in_reachable_chamber(self):
        grid = "".join(self.level["rows"])
        for ch in ("P", "G", "X", "*"):
            self.assertIn(ch, grid)
        gate_y = next(y for y, r in enumerate(self.level["rows"])
                      if "G" in r)
        orb_rows = [y for y, r in enumerate(self.level["rows"])
                    if "*" in r]
        self.assertTrue(all(y < gate_y for y in orb_rows),
                        "an orb behind the gate would deadlock the level")
        portal_y = next(y for y, r in enumerate(self.level["rows"])
                        if "X" in r)
        self.assertGreater(portal_y, gate_y)

    def test_warp_room_is_last_in_the_chain(self):
        self.assertIsNone(self.level.get("next"))
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIsNone(by_id["warp-room"]["next"])


class ProgressionChainTests(unittest.TestCase):
    def test_orbs_room_warps_to_warp_room(self):
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertEqual(by_id["orbs-room"]["next"], "warp-room")

    def test_every_next_names_an_existing_level(self):
        levels = game_levels.list_levels(ROOT / "levels")
        ids = {l["id"] for l in levels}
        for item in levels:
            if item["next"] is not None:
                self.assertIn(item["next"], ids)

    def test_game_loads_next_level_from_state(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("state.next_level", js)
        self.assertIn("loadNextLevel", js)
        self.assertIn("endSession('won')", js)


# Collect both orbs, pass the open gate, step onto the portal.
ORBS_TO_WARP = [
    'right', 'right', 'right',           # collect orb at (4,1)
    'right', 'right', 'right', 'right',  # collect orb at (8,1)
    'left', 'left', 'left',              # back to (5,1)
    'down',                              # (5,2) above the gate
    'down',                              # (5,3) on the open gate
    'down',                              # (5,4) past the gate
    'down',                              # (5,5) onto the warp
]

WARP_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = __INPUTS__;
let s = core.initialState(level, 'orbs-room');
const start = { status: s.status, next: core.readout(s).next_level,
  pos: { ...s.player } };
inputs.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
const warped = { pos: { ...s.player }, status: s.status,
  next: core.readout(s).next_level, tile: s.grid[5][5],
  orbs: core.readout(s).orbs_left, steps: s.steps };
// A won run stays frozen (and stays won past the time limit).
const after = core.step(s, { t_ms: 999999, input: 'left' });
const frozen = { pos: { ...after.player }, status: after.status };
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
const replayed = core.replay(level, 'orbs-room', log).slice(-1)[0];
const s0 = core.initialState(level, 'orbs-room');
console.log(JSON.stringify({ start, warped, frozen,
  liveDigest: core.stateDigest(s), replayDigest: core.stateDigest(replayed),
  freshStatus: s0.status, freshPos: s0.player }));
""".replace("__INPUTS__", json.dumps(ORBS_TO_WARP))


@unittest.skipUnless(shutil.which("node"), "node not available")
class WarpLoadsNextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(WARP_SCRIPT)

    def test_starts_playing_with_next_level_named(self):
        self.assertEqual(self.r["start"]["status"], "playing")
        self.assertEqual(self.r["start"]["next"], "warp-room")

    def test_step_on_warp_behind_open_gate_wins_the_run(self):
        self.assertEqual(self.r["warped"]["pos"], {"x": 5, "y": 5})
        self.assertEqual(self.r["warped"]["status"], "won")
        self.assertEqual(self.r["warped"]["tile"], "X",
                         "the warp tile itself stays 'X'")
        self.assertEqual(self.r["warped"]["orbs"], 0)

    def test_warp_names_the_next_level_to_load(self):
        self.assertEqual(self.r["warped"]["next"], "warp-room")

    def test_won_run_stays_frozen_and_won(self):
        self.assertEqual(self.r["frozen"]["pos"], {"x": 5, "y": 5})
        self.assertEqual(self.r["frozen"]["status"], "won")

    def test_recorded_log_replays_to_same_won_state(self):
        self.assertEqual(self.r["liveDigest"], self.r["replayDigest"])

    def test_step_is_pure(self):
        self.assertEqual(self.r["freshStatus"], "playing")
        self.assertEqual(self.r["freshPos"], {"x": 1, "y": 1})


SHUT_GATE_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
let s = core.initialState(level, 'orbs-room');
// Above the gate at (5,2) with both orbs remaining, press down:
// the shut gate blocks, so the warp behind it stays unreachable.
for (const [i, input] of ['down', 'right', 'right', 'right', 'right'].entries()) {
  s = core.step(s, { t_ms: (i + 1) * 100, input });
}
s = core.step(s, { t_ms: 600, input: 'down' });
console.log(JSON.stringify({ pos: { ...s.player }, status: s.status,
  orbs: core.readout(s).orbs_left }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class WarpUnreachableBehindShutGateTests(unittest.TestCase):
    def test_shut_gate_keeps_warp_unreachable(self):
        r = run_core(SHUT_GATE_SCRIPT)
        self.assertEqual(r["pos"], {"x": 5, "y": 2})
        self.assertEqual(r["status"], "playing")
        self.assertEqual(r["orbs"], 2)


if __name__ == "__main__":
    unittest.main()
