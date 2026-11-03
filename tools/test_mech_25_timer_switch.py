"""Checks for the timer switch (mech-25-timer-switch).

Mechanic lives in packs/timer-switch; driven under Node against the
teaching room. Countdown is deterministic: deadline = press t_ms +
5000 stored in door meta, tick derives secs_left from recorded t_ms,
closes at zero, re-press resets. No wall-clock reads.
Run: python -m unittest tools.test_mech_25_timer_switch -v
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

LEVEL_ID = "mech-25-timer-switch-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class TimerRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id)

    def test_rows_rectangular_and_legend_covers_tiles(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_teaching_moment_layout(self):
        row = self.level["rows"][1]
        self.assertEqual(row, "#P.S...*......DX#")
        self.assertLess(row.index("S"), row.index("*"))
        self.assertLess(row.index("*"), row.index("D"))
        self.assertLess(row.index("D"), row.index("X"))


SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(pairs) {
  let s = core.initialState(level, 'mech-25-timer-switch-room');
  const snap = () => ({ pos: {...s.player}, row: s.grid[1],
    status: s.status, orbs: core.readout(s).orbs_left,
    door: (s.meta['14,1'] || {}), sw: (s.meta['3,1'] || {}) });
  const snaps = [snap()];
  for (const [input, t] of pairs) {
    s = core.step(s, { t_ms: t, input });
    snaps.push(snap());
  }
  return { snaps, final: s };
}
const R = (n, start, dt) => Array.from({length: n},
  (_, i) => ['right', start + i * dt]);
const L = (n, start, dt) => Array.from({length: n},
  (_, i) => ['left', start + i * dt]);
// Solution: press at t=200 (2 rights), sprint 12 rights to warp.
const sol = run([['right',100],['right',200], ...R(12,300,100)]);
// Adversarial: press, collect orb (x7), waste time to t=6000, door
// closed on arrival, return to switch and re-press.
const adv = run([['right',100],['right',200], ...R(4,300,100),
  ['wait',3000],['wait',6000], ...R(7,6100,100),
  ...L(10,6900,100), ...R(12,8000,100)]);
// Boundary exactly: press at 200, wait at door-adjacent x13; open
// through t=5199 (secs 1), closed at t=5200, step after blocked.
const bnd = run([['right',100],['right',200], ...R(10,300,100),
  ['wait',5199],['wait',5200],['right',5300]]);
// Boundary re-press: press 200, advance 3s, step off and back on
// switch at t=3300; deadline must be 8300 not 5200.
const rep = run([['right',100],['right',200],['right',300],
  ['wait',3200],['left',3300],['wait',8200],['wait',8300]]);
// Purity.
const s0 = core.initialState(level, 'mech-25-timer-switch-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ sol: sol.snaps, adv: adv.snaps,
  bnd: bnd.snaps, rep: rep.snaps,
  fresh: { row: s0.grid[1], meta: s0.meta },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class TimerMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SCRIPT)

    def test_solution_sprint_through_in_time(self):
        sol = self.r["sol"]
        self.assertEqual(sol[2]["door"].get("timer_secs_left"), 5)
        self.assertIn("O", sol[2]["row"])
        # Through door and onto warp before zero: won.
        self.assertEqual(sol[-1]["pos"], {"x": 15, "y": 1})
        self.assertEqual(sol[-1]["status"], "won")

    def test_adversarial_orb_on_the_way(self):
        adv = self.r["adv"]
        # Orb collected on the way (orbs_left drops to 0).
        self.assertEqual(adv[6]["orbs"], 0)
        # Detour spent the window: door closed before arrival.
        self.assertIn("D", adv[8]["row"])
        self.assertNotIn("O", adv[8]["row"])
        # Arrival at closed door is blocked (x stays 13).
        self.assertEqual(adv[15]["pos"], {"x": 13, "y": 1})
        self.assertEqual(adv[15]["status"], "playing")
        # Never stranded: back to switch, re-press, sprint wins.
        self.assertEqual(adv[-1]["status"], "won")

    def test_boundary_five_seconds_exactly(self):
        bnd = self.r["bnd"]
        # At t=5199 still open with 1s left; at 5200 closed.
        self.assertEqual(bnd[13]["door"].get("timer_secs_left"), 1)
        self.assertIn("O", bnd[13]["row"])
        self.assertEqual(bnd[14]["door"].get("timer_secs_left"), 0)
        self.assertIn("D", bnd[14]["row"])
        # Step attempted after zero is blocked at x=13.
        self.assertEqual(bnd[15]["pos"], {"x": 13, "y": 1})
        self.assertEqual(bnd[15]["status"], "playing")

    def test_boundary_repress_resets_countdown(self):
        rep = self.r["rep"]
        # Re-press at t=3300: deadline 8300, full 5s again.
        self.assertEqual(rep[5]["door"].get("timer_deadline_ms"), 8300)
        self.assertEqual(rep[5]["door"].get("timer_secs_left"), 5)
        # Original deadline 5200 passing does not close it.
        self.assertIn("O", rep[6]["row"])
        self.assertEqual(rep[7]["door"].get("timer_secs_left"), 0)
        self.assertIn("D", rep[7]["row"])

    def test_restart_restores_switch_and_door(self):
        self.assertEqual(self.r["fresh"]["row"], "#P.S...*......DX#")
        self.assertEqual(self.r["fresh"]["meta"], {})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_timer_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text()
        self.assertIn("timer-switch-running.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/timer-switch/main.js", html)
        manifest = json.loads((ROOT / "tools" / "static" / "packs"
                               / "timer-switch" / "manifest.json").read_text())
        for entry in manifest["assets"] + manifest["gui"]:
            self.assertTrue(entry["bundled"])
            p = (ROOT / "tools" / "static" / "packs" / "timer-switch"
                 / "assets" / entry["file"])
            self.assertTrue(p.exists(), entry["file"])


SANITY = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const pairs = [['right',100],['right',200],
  ...Array.from({length:12},(_,i)=>['right',300+i*100])];
const log = pairs.map(([input,t_ms])=>({t_ms,input}));
let live = core.initialState(level, 'mech-25-timer-switch-room');
for (const s of log) live = core.step(live, s);
const r1 = core.replay(level, 'mech-25-timer-switch-room', log);
const r2 = core.replay(level, 'mech-25-timer-switch-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(r1[r1.length-1]),
  replay2Digest: core.stateDigest(r2[r2.length-1]),
  final: {pos:{...live.player}, status: live.status},
  steps: r1.length-1 }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["final"],
                         {"pos": {"x": 15, "y": 1}, "status": "won"})
        self.assertEqual(self.r["steps"], 14)


if __name__ == "__main__":
    unittest.main()
