"""Checks for one-time switch (mech-27-one-time-switch).

YAML test_cases (switches-and-doors.yml #27):
- solution press last and leave
- adversarial press as soon as reached (blocked-by: 31 patroller)
- boundary first press only
- boundary never resets in the attempt
- restart and replay
Run: python -m unittest tools.test_mech_27_one_time_switch -v
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

LEVEL_ID = "mech-27-one-time-switch-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class RoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id)

    def test_rows_and_legend(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row:
                self.assertIn(ch, self.level["legend"])

    def test_teaching_layout(self):
        grid = "".join(self.level["rows"])
        for ch in "PSDX*":
            self.assertIn(ch, grid)
        # Switch in sight of door: same room, door is exit divider.
        self.assertIn("S", self.level["rows"][2])
        self.assertIn("D", self.level["rows"][4])

    def test_pack_assets_exist(self):
        pack = ROOT / "tools/static/packs/one-time-switch"
        man = json.loads((pack / "manifest.json").read_text())
        self.assertEqual(man["pack"], "one-time-switch")
        for e in man["assets"]:
            self.assertTrue(e["bundled"])
            self.assertTrue((pack / "assets" / e["file"]).is_file(), e["file"])


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-27-one-time-switch-room');
  const snap = () => ({ pos: {...s.player}, row2: s.grid[2], row4: s.grid[4], status: s.status, orbs: core.readout(s).orbs_left });
  const snaps=[snap()];
  seq.forEach((input,i)=>{ s=core.step(s,{t_ms:(i+1)*100,input}); snaps.push(snap()); });
  return {snaps, final:s};
}
const solution=['right','right','right','down','right','right','down','left','down','down','right','down'];
const naive=['down','down','right','right','right','right','down','down'];
const sol=run(solution);
const nai=run(naive);
// first press only: press, leave, re-enter broken twice
const pressOnly=run(['right','right','right','down','right','right','left','right','left','right']);
// never resets: press then 20 moves bouncing in upper room
const bounce=['left','right']; let seq20=['right','right','right','down','right','right'];
for(let i=0;i<10;i++) seq20.push('left','right');
const never=run(seq20);
// purity
const s0=core.initialState(level,'mech-27-one-time-switch-room');
const before=JSON.stringify(s0); core.step(s0,{t_ms:100,input:'right'});
console.log(JSON.stringify({sol:sol.snaps, nai:nai.snaps, pressOnly:pressOnly.snaps, never:never.snaps,
  fresh:{row2:core.initialState(level,'mech-27-one-time-switch-room').grid[2], row4:core.initialState(level,'mech-27-one-time-switch-room').grid[4]},
  pure: JSON.stringify(s0)===before, solFinal:{pos:{...sol.final.player},status:sol.final.status,orbs:core.readout(sol.final).orbs_left}}));
"""

SANITY = r"""
const core=require(process.argv[1]);
const level=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));
const inputs=['right','right','right','down','right','right','down','left','down','down','right','down'];
const log=inputs.map((input,i)=>({t_ms:(i+1)*100,input}));
let live=core.initialState(level,'mech-27-one-time-switch-room');
for(const s of log) live=core.step(live,s);
const r1=core.replay(level,'mech-27-one-time-switch-room',log);
const r2=core.replay(level,'mech-27-one-time-switch-room',JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({liveDigest:core.stateDigest(live), replayDigest:core.stateDigest(r1[r1.length-1]), replay2Digest:core.stateDigest(r2[r2.length-1]), steps:r1.length-1, final:{pos:{...live.player},status:live.status}}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SCRIPT)
        cls.s = run_core(SANITY)

    def test_solution_press_last_and_leave(self):
        # After press (snap 6): switch broken B, door open O; end won at warp.
        self.assertEqual(self.r["sol"][6]["row2"], "#.....B.....#")
        self.assertEqual(self.r["sol"][6]["row4"], "#####O#######")
        self.assertEqual(self.r["solFinal"], {"pos": {"x": 6, "y": 6}, "status": "won", "orbs": 0})

    def test_naive_straight_to_closed_door_fails(self):
        n = self.r["nai"]
        self.assertEqual(n[-1]["pos"], {"x": 5, "y": 3})
        self.assertEqual(n[-1]["status"], "playing")
        self.assertEqual(n[-1]["row4"], "#####D#######")

    @unittest.skip("blocked-by: 31 (patroller) - patroller mechanic not built; "
                   "press-early opens exit permanently and patroller gains way in cannot be exercised")
    def test_adversarial_press_as_soon_as_reached(self):
        pass

    def test_boundary_first_press_only(self):
        p = self.r["pressOnly"]
        # Re-entering broken switch (snaps 8 and 10) changes nothing.
        self.assertEqual(p[8]["row2"], "#.....B.....#")
        self.assertEqual(p[10]["row2"], "#.....B.....#")
        self.assertEqual(p[10]["row4"], "#####O#######")

    def test_boundary_never_resets(self):
        n = self.r["never"]
        self.assertEqual(n[-1]["row2"], "#.....B.....#")
        self.assertEqual(n[-1]["row4"], "#####O#######")
        self.assertEqual(n[-1]["status"], "playing")

    def test_restart_restores(self):
        self.assertEqual(self.r["fresh"], {"row2": "#.....S.....#", "row4": "#####D#######"})

    def test_step_is_pure_and_wall_clock_free(self):
        self.assertTrue(self.r["pure"])
        js = (ROOT / "tools/static/packs/one-time-switch/main.js").read_text()
        for bad in ("Date.now", "performance.now", "new Date"):
            self.assertNotIn(bad, js)

    def test_replay_digest_matches(self):
        self.assertEqual(self.s["replayDigest"], self.s["liveDigest"])
        self.assertEqual(self.s["replay2Digest"], self.s["liveDigest"])
        self.assertEqual(self.s["steps"], 12)
        self.assertEqual(self.s["final"]["status"], "won")

    def test_game_wiring(self):
        self.assertIn("packs/one-time-switch/main.js",
                      (ROOT / "tools/static/game.html").read_text())
        self.assertIn("one-time-switch-broken.png",
                      (ROOT / "tools/static/game.js").read_text())


if __name__ == "__main__":
    unittest.main()
