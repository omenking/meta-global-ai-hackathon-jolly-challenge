"""Checks for the bonus orb (mech-20-bonus-orb).

The mechanic lives in the pure GameCore step (packs/bonus-orb):
walking onto the bonus orb removes it and banks exactly 10
seconds (the kernel addTime effect raises the level time limit);
it is never counted in orbs-left, so the gate opens on counted
orbs only. The teaching room runs a tight 10-second timer: a
priced (fast) detour banks the bonus and still wins, while an
unpriced (slow, wasteful) detour lets the timer end on the way
back even after banking. Covers every candidate test_case for
mechanic #20 in plans/level-design/candidate-mechanics/orbs.yml;
the sleeper case is blocked-by 33 and is an explicit skip.

Run with: python -m unittest tools.test_mech_20_bonus_orb -v
"""
import json
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

LEVEL_ID = "mech-20-bonus-orb-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "bonus-orb"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class BonusRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("B"), 1, "exactly one bonus orb")
        self.assertEqual(grid.count("*"), 1, "exactly one counted orb")
        self.assertIn("G", grid)
        self.assertIn("X", grid)
        # Tight timer: the detour must be priced against the clock.
        self.assertLessEqual(self.level["time_limit"], 10)
        # The bonus orb sits east of (beyond) the counted orb: the
        # detour costs extra steps past the main-route pickup.
        top = rows[1]
        self.assertLess(top.index("*"), top.index("B"))
        # Row 2 is open floor, so the bonus can also be reached
        # without collecting the counted orb (gate-alone check).
        self.assertEqual(rows[2], "#.........#")


class BonusPackTests(unittest.TestCase):
    def test_manifest_lists_bundled_assets_that_exist(self):
        manifest = json.loads((PACK / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "bonus-orb")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["bonus-orb.png", "timer-gain.png"])
        for entry in bundled:
            path = PACK / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])

    def test_pack_declares_assets_and_tile(self):
        js = (PACK / "main.js").read_text(encoding="utf-8")
        self.assertIn("defineAsset", js)
        self.assertIn("bonus-orb.png", js)
        self.assertIn("timer-gain.png", js)
        self.assertIn("bonus:bonus-orb", js)
        self.assertIn("addTime", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/bonus-orb/main.js", html)
        core = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("packs/bonus-orb/main.js", core)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(inputs, paceMs) {
  let s = core.initialState(level, 'mech-20-bonus-orb-room');
  const snap = () => ({ pos: { ...s.player },
    status: s.status, orbs: core.readout(s).orbs_left,
    gate: core.readout(s).gate_open, limit: s.time_limit_s,
    left: s.time_left_s, row1: s.grid[1] });
  const snaps = [snap()];
  inputs.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * paceMs, input });
    snaps.push(snap());
  });
  return snaps;
}
// Solution: counted orb, bonus detour, gate, portal - fast.
const sol = run(['right','right','right','right','right',
  'left','down','down','down','down'], 400);
// Optional: same room without the bonus still wins when fast.
const direct = run(['right','right','right','right',
  'down','down','down','down'], 400);
// Boundary: reach the bonus via row 2 without the counted orb,
// then press into the shut gate.
const alone = run(['down','right','right','right','right','right',
  'up','left','down','down'], 100);
// Adversarial: bank the bonus, waste moves, slow clock - the
// timer ends on the way back despite the +10.
const adv = run(['right','right','right','right','right',
  'left','right','left','right','down','down','down','down'], 1600);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-20-bonus-orb-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
const fresh = core.initialState(level, 'mech-20-bonus-orb-room');
console.log(JSON.stringify({ sol, direct, alone, adv,
  fresh: { row1: fresh.grid[1], limit: fresh.time_limit_s,
    left: fresh.time_left_s, orbs: core.readout(fresh).orbs_left,
    status: fresh.status },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class BonusMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_bonus_not_counted_in_orbs_left(self):
        # One counted orb placed, one bonus orb placed: counter is 1.
        self.assertEqual(self.r["fresh"]["orbs"], 1)
        self.assertEqual(self.r["fresh"]["row1"], "#P.*..B...#")

    def test_solution_priced_detour(self):
        sol = self.r["sol"]
        # Step 2 collects the counted orb; step 5 banks the bonus.
        self.assertEqual(sol[2]["orbs"], 0)
        self.assertEqual(sol[5]["limit"], 20)
        self.assertEqual(sol[-1]["status"], "won")
        self.assertEqual(sol[-1]["orbs"], 0)

    def test_bonus_is_optional_for_the_gate(self):
        self.assertEqual(self.r["direct"][-1]["status"], "won")
        self.assertEqual(self.r["direct"][-1]["limit"], 10)

    def test_boundary_exactly_10_seconds_and_no_count(self):
        alone = self.r["alone"]
        # Before pickup (t=600ms): placed limit, counted orb left.
        self.assertEqual(alone[6]["limit"], 10)
        self.assertEqual(alone[6]["orbs"], 1)
        # After pickup (t=700ms): exactly +10 on the limit, the
        # counted-orb counter and the gate are untouched.
        self.assertEqual(alone[7]["limit"], 20)
        self.assertEqual(alone[7]["left"], 19.3)
        self.assertEqual(alone[7]["orbs"], 1)
        self.assertFalse(alone[7]["gate"])
        self.assertNotIn("B", alone[7]["row1"])
        # The shut gate blocks: the player stays above it.
        self.assertEqual(alone[-1]["pos"], {"x": 5, "y": 2})
        self.assertEqual(alone[-1]["status"], "playing")

    def test_adversarial_unpriced_detour(self):
        adv = self.r["adv"]
        # The bonus was banked (limit raised) yet the wasted trip
        # still lets the timer end on the way back: a loss, and
        # the run is never stranded without a reset.
        self.assertEqual(adv[5]["limit"], 20)
        self.assertEqual(adv[-1]["status"], "lost")
        self.assertNotEqual(adv[-1]["pos"], {"x": 5, "y": 5})

    def test_restart_restores_bonus_and_timer(self):
        fresh = self.r["fresh"]
        self.assertEqual(fresh["limit"], 10)
        self.assertEqual(fresh["left"], 10)
        self.assertEqual(fresh["status"], "playing")
        self.assertIn("B", fresh["row1"])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    @unittest.skip("blocked-by: 33 (sleeper) - the sleeper enemy is "
                   "not built yet, so whether collecting the bonus "
                   "orb wakes it cannot be exercised; revisit when "
                   "mech-33 lands")
    def test_bonus_wakes_a_sleeper(self):
        self.fail("blocked-by 33: no sleeper exists to wake")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right','right','right','right','right',
  'left','down','down','down','down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 400, input }));
let live = core.initialState(level, 'mech-20-bonus-orb-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-20-bonus-orb-room', log);
const replayed2 = core.replay(level, 'mech-20-bonus-orb-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    orbs: core.readout(live).orbs_left, limit: live.time_limit_s },
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

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 5, "y": 5}, "status": "won",
                          "orbs": 0, "limit": 20})
        self.assertEqual(self.r["replaySteps"], 10)


if __name__ == "__main__":
    unittest.main()
