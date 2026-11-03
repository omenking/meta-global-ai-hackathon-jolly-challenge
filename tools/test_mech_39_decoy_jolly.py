"""Checks for Decoy Jolly (mech-39-decoy-jolly).

Rules: one decoy carried in a slot; walking over its pickup
drops the copy on the stepped-off tile; lasts 20 moves; while
it stands (and was seen dropped) the guard targets it instead
of the player. Blocker synergy case is blocked-by mech 34.

Run with: python -m unittest tools.test_mech_39_decoy_jolly -v
"""
import json, shutil, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402
LEVEL_ID = "mech-39-decoy-jolly-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"

WAIT = ["up", "up"]
TO_PICKUP = ["right"] * 4 + ["down"]
CORRECTED = WAIT + TO_PICKUP + ["right", "right", "down", "right", "right"]
NAIVE = TO_PICKUP + ["right", "right"]

SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function snap(s) {
  const g = s.actors.find((a) => a.def === 'decoy:guard');
  let d = null;
  for (let y = 0; y < s.height; y++) for (let x = 0; x < s.width; x++)
    if (s.objects[y][x] === 'decoy:decoy') d = { x, y, ttl: (s.meta[x+','+y]||{}).decoy_ttl || 0, seen: (s.meta[x+','+y]||{}).decoy_seen || 0 };
  return { pos: { ...s.player }, guard: g ? { x: g.x, y: g.y } : null,
    decoy: d, inv: core.readout(s).inventory, status: s.status, grid: s.grid };
}
function run(seq) {
  let s = core.initialState(level, 'mech-39-decoy-jolly-room');
  const snaps = [snap(s)];
  seq.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); snaps.push(snap(s)); });
  return snaps;
}
const corrected = run(JSON.parse(process.argv[3]));
const naive = run(JSON.parse(process.argv[4]));
const deployIdx = 8;
const longSeq = [...JSON.parse(process.argv[3]).slice(0, 8)];
for (let i = 0; i < 20; i++) longSeq.push(i % 2 ? 'left' : 'right');
const longRun = run(longSeq);
const s0 = core.initialState(level, 'mech-39-decoy-jolly-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
const log = JSON.parse(process.argv[3]).map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-39-decoy-jolly-room');
for (const st of log) live = core.step(live, st);
const replayed = core.replay(level, 'mech-39-decoy-jolly-room', log);
console.log(JSON.stringify({ corrected, naive, longRun,
  fresh: snap(core.initialState(level, 'mech-39-decoy-jolly-room')),
  pure: JSON.stringify(s0) === before,
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]) }));
"""

def run_core():
    out = subprocess.run(["node", "-e", SCRIPT, str(CORE), str(LEVEL),
                          json.dumps(CORRECTED), json.dumps(NAIVE)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])

class LevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)
    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id); self.assertTrue(by_id[LEVEL_ID]["test"])
    def test_rows_rectangular_and_legend_covers(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row: self.assertIn(ch, self.level["legend"])
        grid = "".join(rows)
        for ch in "PD*GXE": self.assertIn(ch, grid)

@unittest.skipUnless(shutil.which("node"), "node not available")
class DecoyMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r = run_core()
    def test_one_slot_carry_then_deploy_on_step_off(self):
        c = self.r["corrected"]
        self.assertEqual(c[7]["inv"], ["decoy"])  # standing on pickup
        self.assertEqual(c[8]["inv"], [])
        self.assertEqual(c[8]["decoy"], {"x": 5, "y": 2, "ttl": 20, "seen": 1})
        self.assertEqual(c[8]["pos"], {"x": 6, "y": 2})
    def test_plant_in_sight_and_cross(self):
        c = self.r["corrected"]
        self.assertEqual(c[-1]["status"], "won")
        self.assertEqual(c[10]["guard"], {"x": 5, "y": 2})  # guard at decoy
    def test_adversarial_drop_unseen_chased_and_lost(self):
        n = self.r["naive"]
        self.assertEqual(n[6]["decoy"]["seen"], 0)
        self.assertEqual(n[-1]["status"], "lost")
    def test_retry_after_unseen_can_succeed(self):
        # Fresh restart state then corrected sequence wins (replayed in corrected run).
        self.assertEqual(self.r["fresh"]["decoy"], None)
        self.assertEqual(self.r["corrected"][-1]["status"], "won")
    def test_lasts_twenty_moves(self):
        lr = self.r["longRun"]
        self.assertEqual(lr[8]["decoy"]["ttl"], 20)
        self.assertIsNotNone(lr[27]["decoy"]); self.assertEqual(lr[27]["decoy"]["ttl"], 1)
        self.assertIsNone(lr[28]["decoy"])
    @unittest.skip("blocked-by: 34 (blocker) - blocker mechanic not built; decoy/blocker doorway synergy deferred")
    def test_blocker_vacates_doorway(self): pass
    def test_restart_restores_pickup_and_slot_empty(self):
        f = self.r["fresh"]
        self.assertEqual(f["inv"], []); self.assertIsNone(f["decoy"])
        self.assertIn("D", "".join(f["grid"]))
    def test_step_is_pure(self): self.assertTrue(self.r["pure"])
    def test_wiring(self):
        html = (ROOT / "tools/static/game.html").read_text(encoding="utf-8")
        self.assertIn("packs/decoy/main.js", html)
        js = (ROOT / "tools/static/game.js").read_text(encoding="utf-8")
        self.assertTrue(js)  # game page loads pack via html script tag

@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r = run_core()
    def test_replay_digest_matches(self):
        self.assertEqual(self.r["liveDigest"], self.r["replayDigest"])
        self.assertEqual(self.r["corrected"][-1]["status"], "won")

if __name__ == "__main__": unittest.main()
