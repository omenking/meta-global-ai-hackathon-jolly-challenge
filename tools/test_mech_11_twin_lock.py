"""Checks for the twin lock (mech-11-twin-lock).

Mechanic lives in packs/twin-lock via the pure GameCore step; driven
under Node against the teaching room. Rules: press with one matching
key shows needs-one (grid 't'), consumes nothing; press with two
consumes both and dissolves to floor; wrong colours never count;
naive twin-first spend strands at the single lock; restart/replay
restore and reproduce. Run:
python -m unittest tools.test_mech_11_twin_lock -v
"""
import json, shutil, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402
LEVEL_ID = "mech-11-twin-lock-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"

class RoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)
    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id); self.assertTrue(by_id[LEVEL_ID]["test"])
    def test_rows_rectangular_and_legend(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row: self.assertIn(ch, self.level["legend"])
        self.assertEqual(self.level["legend"]["T"].get("twin_lock_color"), "red")
        self.assertEqual(self.level["legend"]["R"].get("lock_color"), "red")
    def test_teaching_layout(self):
        grid = "".join(self.level["rows"])
        self.assertEqual(grid.count("T"), 1); self.assertEqual(grid.count("R"), 1)
        # twin is met before the single lock on the top corridor
        top = self.level["rows"][1]
        self.assertLess(top.index("T"), top.index("R"))
        # long-way gap in first divider (col 8) on lower rows
        self.assertEqual(self.level["rows"][6][8], ".")
        self.assertEqual(self.level["rows"][7][8], ".")

def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])

SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq){let s=core.initialState(level,'mech-11-twin-lock-room');
 const snap=()=>({pos:{...s.player},inv:core.readout(s).inventory,row:s.grid[1],status:s.status});
 const snaps=[snap()]; seq.forEach((input,i)=>{s=core.step(s,{t_ms:(i+1)*100,input}); snaps.push(snap());}); return snaps;}
const R='right',L='left',U='up',D='down';
const one=run([R,R,R,R,R,R,R]);
const sol=run([R,R,R,D,D,L,L,U,U,R,R,R,R,R,R]);
const adv=run([R,R,R,D,D,L,L,U,U,R,R,R,R,R,R,R,R,R,R]);
const wrong=run([D,D,D,R,R,R,R,U,U,U,R,R,R]);
const corrSeq=[R,R,R,D,D,L,L,L,D,D,D,D,R,R,R,R,R,R,R,R,R,R,U,U,U,U,U,U,R,R,R,R];
const corr=run(corrSeq);
const s0=core.initialState(level,'mech-11-twin-lock-room'); const before=JSON.stringify(s0);
core.step(s0,{t_ms:100,input:'right'});
console.log(JSON.stringify({one,sol,adv,wrong,corr,fresh:core.initialState(level,'mech-11-twin-lock-room').grid[1],pure:JSON.stringify(s0)===before,corrSeq}));
"""

@unittest.skipUnless(shutil.which("node"), "node not available")
class TwinLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r = run_core(SCRIPT)
    def test_one_key_boundary_consumes_nothing(self):
        f = self.r["one"][-1]
        self.assertEqual(f["pos"], {"x": 7, "y": 1}); self.assertEqual(f["inv"], ["red"])
        self.assertIn("t", f["row"]); self.assertEqual(f["status"], "playing")
    def test_solution_two_keys_dissolve(self):
        f = self.r["sol"][-1]
        self.assertEqual(f["pos"], {"x": 8, "y": 1}); self.assertEqual(f["inv"], [])
        self.assertNotIn("T", f["row"]); self.assertNotIn("t", f["row"])
    def test_adversarial_spending_both_strands_at_single(self):
        f = self.r["adv"][-1]
        self.assertEqual(f["pos"], {"x": 11, "y": 1}); self.assertEqual(f["inv"], [])
        self.assertIn("R", f["row"]); self.assertEqual(f["status"], "playing")
    def test_wrong_colour_does_not_count(self):
        f = self.r["wrong"][-1]
        self.assertEqual(f["inv"], ["blue", "blue"]); self.assertIn("T", f["row"])
        self.assertEqual(f["pos"], {"x": 7, "y": 1})
    def test_corrected_long_way_wins(self):
        f = self.r["corr"][-1]
        self.assertEqual(f["status"], "won"); self.assertEqual(f["pos"], {"x": 15, "y": 1})
        self.assertEqual(f["inv"], ["red"])
    def test_restart_restores(self):
        self.assertIn("T", self.r["fresh"]); self.assertNotIn("t", self.r["fresh"])
    def test_step_is_pure(self): self.assertTrue(self.r["pure"])
    def test_wiring(self):
        self.assertIn("packs/twin-lock/main.js", (ROOT/"tools/static/game.html").read_text())
        self.assertIn("twin-lock", (ROOT/"tools/static/game-core.js").read_text())
        man = json.loads((ROOT/"tools/static/packs/twin-lock/manifest.json").read_text())
        for a in man["assets"] + man["gui"]:
            self.assertTrue(a["bundled"]); self.assertTrue((ROOT/"tools/static/packs/twin-lock/assets"/a["file"]).exists(), a["file"])

SANITY = r"""
const core=require(process.argv[1]); const level=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));
const seq=['right','right','right','down','down','left','left','left','down','down','down','down','right','right','right','right','right','right','right','right','right','right','up','up','up','up','up','up','right','right','right','right'];
const log=seq.map((input,i)=>({t_ms:(i+1)*100,input}));
let live=core.initialState(level,'mech-11-twin-lock-room'); for(const s of log) live=core.step(live,s);
const rep=core.replay(level,'mech-11-twin-lock-room',log); const rep2=core.replay(level,'mech-11-twin-lock-room',JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({liveDigest:core.stateDigest(live),replayDigest:core.stateDigest(rep[rep.length-1]),replay2Digest:core.stateDigest(rep2[rep2.length-1]),steps:rep.length-1,final:{pos:{...live.player},status:live.status,inv:core.readout(live).inventory}}));
"""
@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r = run_core(SANITY)
    def test_replay_digest_matches(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["final"], {"pos": {"x": 15, "y": 1}, "status": "won", "inv": ["red"]})
        self.assertEqual(self.r["steps"], 32)

if __name__ == "__main__": unittest.main()
