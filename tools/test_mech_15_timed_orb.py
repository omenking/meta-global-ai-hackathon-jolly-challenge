"""Checks for the timed orb (mech-15-timed-orb).

The mechanic lives in the pure GameCore step (packs/timed-orb);
driven here under Node against the teaching room. Rules: the
countdown starts the first time the orb enters the camera view
(ring, 10 s to collect); collected in time it counts as normal;
if it expires it dissolves and reforms at its start tile after
5 s; restart (fresh state) restores it unseen. One YAML case is
blocked-by mechanic 9 (dash tile) and is skipped with reason.

Run with: python -m unittest tools.test_mech_15_timed_orb -v
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

LEVEL_ID = "mech-15-timed-orb-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class TimedOrbLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("T"), 1)
        self.assertGreaterEqual(grid.count("*"), 1)
        tpos = next((x, y) for y, r in enumerate(rows)
                    for x, ch in enumerate(r) if ch == "T")
        spos = next((x, y) for y, r in enumerate(rows)
                    for x, ch in enumerate(r) if ch == "*")
        ppos = next((x, y) for y, r in enumerate(rows)
                    for x, ch in enumerate(r) if ch == "P")
        # Timed orb straight ahead on the player's lane; the nearer
        # orb is a detour off it, so order is a real choice.
        self.assertEqual(tpos[1], ppos[1])
        self.assertGreater(tpos[0], ppos[0])
        self.assertNotEqual(spos[1], ppos[1])
        self.assertIn("G", grid)
        self.assertIn("X", grid)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(pairs) {
  let s = core.initialState(level, 'mech-15-timed-orb-room');
  const snap = () => ({ pos: { ...s.player }, row1: s.grid[1],
    status: s.status, orbs: core.readout(s).orbs_left,
    gate: s.gate_open, meta: (s.meta['7,1'] || {}) });
  const snaps = [snap()];
  for (const [t, input] of pairs) {
    s = core.step(s, { t_ms: t, input });
    snaps.push(snap());
  }
  return snaps;
}
const mv = (list, start) => list.map((input, i) =>
  [(start || 100) + i * 100, input]);
// Solution: timed orb first, then the detour orb, gate, portal.
const solMoves = [...Array(6).fill('right'), ...Array(5).fill('left'),
  'down', 'down', ...Array(8).fill('right'), 'up', 'up', 'right'];
const a = run(mv(solMoves));
// Adversarial: nearer orb first, hesitate past the deadline,
// wait out the reform, then finish the room.
const adv = run([
  [100, 'down'], [200, 'down'], [300, 'right'],
  [10100, 'wait'], [15099, 'wait'], [15100, 'wait'], [15200, 'wait'],
  [15300, 'up'], [15400, 'up'], [15500, 'right'], [15600, 'right'],
  [15700, 'right'], [15800, 'right'], [15900, 'right'],
  [16000, 'right'], [16100, 'right'], [16200, 'right'], [16300, 'right'],
]);
// Boundary collect: step on at seen+9999ms (counts as normal).
const bc = run([[100,'right'],[200,'right'],[300,'right'],[400,'right'],
  [500,'right'],[10098,'wait'],[10099,'right']]);
// Boundary expire: step on at exactly seen+10000ms (too late),
// then reform at exactly gone+5000ms, absent at gone+4999ms.
const be = run([[100,'right'],[200,'right'],[300,'right'],[400,'right'],
  [500,'right'],[10099,'wait'],[10100,'right'],[15099,'wait'],
  [15100,'wait']]);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-15-timed-orb-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ a, adv, bc, be,
  fresh: { row1: s0.grid[1], meta: (s0.meta['7,1'] || {}),
    orbs: core.readout(s0).orbs_left },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class TimedOrbMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_unseen_until_first_step_then_ring_starts_on_sight(self):
        self.assertEqual(self.r["fresh"]["meta"]["timed_phase"], "unseen")
        self.assertIsNone(self.r["fresh"]["meta"]["timed_seen_ms"])
        self.assertEqual(self.r["fresh"]["orbs"], 2)
        first = self.r["a"][1]
        self.assertEqual(first["meta"]["timed_phase"], "ringing")
        self.assertEqual(first["meta"]["timed_seen_ms"], 100)

    def test_solution_timed_orb_first(self):
        a = self.r["a"]
        # Collected in time (t=600ms) and counts as a normal orb.
        self.assertEqual(a[6]["pos"], {"x": 7, "y": 1})
        self.assertEqual(a[6]["meta"]["timed_phase"], "collected")
        self.assertEqual(a[6]["orbs"], 1)
        # Both orbs: gate opens and the portal wins the room.
        self.assertEqual(a[-1]["status"], "won")
        self.assertEqual(a[-1]["orbs"], 0)
        self.assertTrue(a[-1]["gate"])

    def test_adversarial_nearer_orb_first_dissolves_and_reforms(self):
        adv = self.r["adv"]
        self.assertEqual(adv[3]["orbs"], 1)  # nearer orb collected
        # Deadline passes while hesitating: dissolved, not collected.
        self.assertEqual(adv[4]["meta"]["timed_phase"], "dissolved")
        self.assertEqual(adv[4]["meta"]["timed_gone_ms"], 10100)
        self.assertNotIn("T", adv[4]["row1"])
        self.assertEqual(adv[4]["orbs"], 1)
        self.assertEqual(adv[4]["status"], "playing")
        # Absent at gone+4999, reformed at gone+5000 on its start tile.
        self.assertEqual(adv[5]["meta"]["timed_phase"], "dissolved")
        self.assertEqual(adv[6]["meta"]["timed_phase"], "unseen")
        self.assertIn("T", adv[6]["row1"])
        # Ring restarts on sight and the room is still completable.
        self.assertEqual(adv[7]["meta"]["timed_phase"], "ringing")
        self.assertEqual(adv[-1]["status"], "won")
        self.assertEqual(adv[-1]["orbs"], 0)

    def test_boundary_collect_before_10_seconds_counts(self):
        bc = self.r["bc"]
        self.assertEqual(bc[-1]["pos"], {"x": 7, "y": 1})
        self.assertEqual(bc[-1]["meta"]["timed_phase"], "collected")
        self.assertEqual(bc[-1]["orbs"], 1)

    def test_boundary_expire_at_10_and_reform_at_5(self):
        be = self.r["be"]
        # Entering at exactly seen+10000 is too late: dissolves,
        # no orb counted, player unharmed on the start tile.
        self.assertEqual(be[7]["pos"], {"x": 7, "y": 1})
        self.assertEqual(be[7]["meta"]["timed_phase"], "dissolved")
        self.assertEqual(be[7]["meta"]["timed_gone_ms"], 10100)
        self.assertEqual(be[7]["orbs"], 2)
        self.assertEqual(be[7]["status"], "playing")
        self.assertEqual(be[8]["meta"]["timed_phase"], "dissolved")
        self.assertNotIn("T", be[8]["row1"])
        self.assertEqual(be[9]["meta"]["timed_phase"], "unseen")
        self.assertIn("T", be[9]["row1"])

    def test_dash_beats_the_ring(self):
        self.skipTest("blocked-by: 9 (dash tile) - dash tile not yet "
                      "built; spend-a-stored-dash case cannot run")

    def test_restart_restores_unseen_orb(self):
        self.assertEqual(self.r["fresh"]["row1"], "#P.....T..GX#")
        self.assertEqual(self.r["fresh"]["meta"]["timed_phase"], "unseen")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_assets_and_rendering_wiring(self):
        pack = ROOT / "tools" / "static" / "packs" / "timed-orb"
        manifest = json.loads((pack / "manifest.json").read_text())
        self.assertEqual(manifest["pack"], "timed-orb")
        self.assertEqual([a["file"] for a in manifest["assets"]],
                         ["timed-orb.png", "timed-orb-ringing.png",
                          "timed-orb-reforming.png"])
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"])
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512))
        js = (ROOT / "tools" / "static" / "game.js").read_text()
        self.assertIn("timed-orb-ringing.png", js)
        self.assertIn("dt.ch === 'T'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/timed-orb/main.js", html)
        main = (pack / "main.js").read_text()
        for name in ("timed-orb.png", "timed-orb-ringing.png",
                     "timed-orb-reforming.png"):
            self.assertIn(name, main)
        self.assertIn("defineAsset", main)
        # Determinism: no unrecorded wall-clock reads in the pack.
        self.assertNotIn("Date.now", main)
        self.assertNotIn("performance.now", main)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const moves = [...Array(6).fill('right'), ...Array(5).fill('left'),
  'down', 'down', ...Array(8).fill('right'), 'up', 'up', 'right'];
const log = moves.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-15-timed-orb-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-15-timed-orb-room', log);
const replayed2 = core.replay(level, 'mech-15-timed-orb-room',
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
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 11, "y": 1}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 24)


if __name__ == "__main__":
    unittest.main()
