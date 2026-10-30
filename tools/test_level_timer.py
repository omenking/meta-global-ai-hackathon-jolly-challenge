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


LOSE_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const s0 = core.initialState(level, 'timer-room');
const before = core.step(s0, { t_ms: 4999, input: 'right' });
const atZero = core.step(before, { t_ms: 5000, input: 'timeout' });
const after = core.step(atZero, { t_ms: 6000, input: 'right' });
const moveAtExpiry = core.step(s0, { t_ms: 5000, input: 'right' });
const log = [
  { t_ms: 1000, input: 'right' },
  { t_ms: 5000, input: 'timeout' },
];
const replayed = core.replay(level, 'timer-room', log);
const live = core.replay(level, 'timer-room', log);
console.log(JSON.stringify({
  startStatus: s0.status, beforeStatus: before.status,
  beforePos: before.player, atZeroStatus: atZero.status,
  atZeroLeft: atZero.time_left_s, atZeroPos: atZero.player,
  afterStatus: after.status, afterPos: after.player,
  moveAtExpiryPos: moveAtExpiry.player, startPos: s0.player,
  replayStatus: replayed[replayed.length - 1].status,
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  liveDigest: core.stateDigest(live[live.length - 1]),
  replaySteps: replayed.map((s) => [s.t_ms, s.status]),
  isLost: core.isLost(atZero), readoutStatus: core.readout(atZero).status,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class LoseAtZeroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_core(LOSE_SCRIPT)

    def test_expiry_at_limit_loses_with_no_time_left(self):
        self.assertEqual(self.result["startStatus"], "playing")
        self.assertEqual(self.result["beforeStatus"], "playing")
        self.assertEqual(self.result["atZeroStatus"], "lost")
        self.assertEqual(self.result["atZeroLeft"], 0)
        self.assertTrue(self.result["isLost"])
        self.assertEqual(self.result["readoutStatus"], "lost")

    def test_no_movement_on_or_after_expiry(self):
        self.assertEqual(self.result["moveAtExpiryPos"],
                         self.result["startPos"])
        self.assertEqual(self.result["afterStatus"], "lost")
        self.assertEqual(self.result["afterPos"], self.result["atZeroPos"])

    def test_timeout_loss_replays_as_loss_at_same_moment(self):
        self.assertEqual(self.result["replayStatus"], "lost")
        self.assertEqual(self.result["replaySteps"],
                         [[0, "playing"], [1000, "playing"], [5000, "lost"]])
        self.assertEqual(self.result["replayDigest"],
                         self.result["liveDigest"])

    def test_game_page_shows_loss_message_and_ends_session_lost(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertNotIn('id="game-message"', html)
        self.assertIn("Time's up", js)
        self.assertIn("retryGroup", js)
        self.assertNotIn("lostOverlay", js)
        self.assertIn("endSession('lost')", js)
        self.assertIn("input: 'timeout'", js)
        self.assertIn('id="dbg-status"', html)


RESTART_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
let s = core.initialState(level, 'timer-room');
const start = { pos: { ...s.player }, left: s.time_left_s, status: s.status };
s = core.step(s, { t_ms: 1000, input: 'right' });
s = core.step(s, { t_ms: 5000, input: 'timeout' });
const lost = { pos: { ...s.player }, status: s.status };
// Restart is a fresh initial state: position, orbs, keys and timer.
const fresh = core.initialState(level, 'timer-room');
const r = core.readout(fresh);
console.log(JSON.stringify({
  start, lostPos: lost.pos, lostStatus: lost.status,
  freshPos: fresh.player, freshLeft: fresh.time_left_s,
  freshStatus: fresh.status, freshSteps: fresh.steps,
  freshTms: fresh.t_ms, orbs: r.orbs_left, inventory: r.inventory,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class RestartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_core(RESTART_SCRIPT)

    def test_restart_restores_position_timer_and_status(self):
        r = self.result
        self.assertEqual(r["lostStatus"], "lost")
        self.assertEqual(r["freshPos"], r["start"]["pos"])
        self.assertEqual(r["freshLeft"], r["start"]["left"])
        self.assertEqual(r["freshStatus"], "playing")
        self.assertEqual(r["freshSteps"], 0)
        self.assertEqual(r["freshTms"], 0)
        # Orbs/keys live in the restored initial grid/inventory.
        self.assertGreaterEqual(r["orbs"], 1)
        self.assertEqual(r["inventory"], [])

    def test_game_page_restarts_with_r_and_button_as_new_session(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertNotIn('id="btn-restart"', html)
        self.assertIn("retryGroup", js)
        self.assertIn("pointertap", js)
        self.assertIn("HUD_H", js)
        self.assertIn("restartLevel", js)
        self.assertIn("ev.key === 'r'", js)
        self.assertIn("GameCore.initialState(level, levelName)", js)
        # A restart closes the old recorder and clears it, so the
        # next move creates a new recorded session.
        self.assertIn("recorder = null", js)
        self.assertIn("inputLog.length = 0", js)
        self.assertIn("sessionStartTs = null", js)


class FallenPoseTests(unittest.TestCase):
    def test_fallen_sprite_published_and_derived(self):
        published = sorted((ROOT / "assets" / "published").glob(
            "jolly-fall-*.png"))
        self.assertTrue(published, "jolly-fall must be in assets/published")
        prep = (ROOT / "tools" / "prep_level_sprites.sh").read_text(
            encoding="utf-8")
        self.assertIn("jolly-fall", prep)
        # The standing sprite must not resolve to jolly-fall-* files.
        self.assertIn('-[0-9]*.png', prep)

    def test_player_sprite_swaps_to_fallen_when_lost(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("jolly-fall.png", js)
        self.assertIn("state.status === 'lost'", js)
        self.assertIn("getPlayerPose", js)


class CurrentGameUiTests(unittest.TestCase):
    def test_restart_and_retry_message_live_in_canvas_not_outside_ui(self):
        jsx = (ROOT / "tools" / "web" / "src" / "GamePage.jsx").read_text(
            encoding="utf-8")
        # No outside-UI Restart button or loss banner in /game; the
        # message and button are drawn inside the Pixi canvas.
        self.assertNotIn(">Restart</button>", jsx)
        self.assertNotIn("Time's up", jsx)
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertNotIn("lostOverlay", js)
        self.assertIn("retryGroup", js)
        self.assertIn("Time's up", js)
        self.assertIn("'Restart'", js)


if __name__ == "__main__":
    unittest.main()
