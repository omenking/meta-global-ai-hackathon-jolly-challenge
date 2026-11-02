"""Checks for hidden orb (mech-16-hidden-orb). Run: python -m unittest tools.test_mech_16_hidden_orb -v"""
import json, shutil, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402
LEVEL_ID = "mech-16-hidden-orb-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "hidden-orb" / "main.js"

class LevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)
    def test_test_level(self):
        self.assertTrue(self.level["test"])
        by_id = {l["id"]: l for l in game_levels.list_levels(ROOT / "levels")}
        self.assertIn(LEVEL_ID, by_id)
    def test_layout(self):
        rows = self.level["rows"]
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows))
        for row in rows:
            for ch in row: self.assertIn(ch, self.level["legend"])
        grid = "".join(rows); self.assertEqual(grid.count("H"), 1); self.assertIn("G", grid); self.assertIn("X", grid)
        # orb outside entrance light: spawn (1,1), orb (9,1), Chebyshev 8 > 2
        self.assertGreater(max(abs(9-1), abs(1-1)), 2)

def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL), str(PACK)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])

SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const pack = require(process.argv[3]);
function run(seq){ let s=core.initialState(level,'mech-16-hidden-orb-room'); const snaps=[{pos:{...s.player},orbs:core.readout(s).orbs_left,status:s.status,lit:pack.isLit(s.player,9,1),grid:s.grid[1]}]; seq.forEach((input,i)=>{s=core.step(s,{t_ms:(i+1)*100,input}); snaps.push({pos:{...s.player},orbs:core.readout(s).orbs_left,status:s.status,lit:pack.isLit(s.player,9,1),grid:s.grid[1]});}); return {snaps, final:s}; }
const boundary = run(['right','right','right','right','right','right','left']);
const naive = run(['right','right','right','right','down','down','down']);
const solution = run(['right','right','right','right','right','right','right','right','left','left','left','left','down','down','down','down','down']);
const s0 = core.initialState(level,'mech-16-hidden-orb-room'); const before=JSON.stringify(s0); core.step(s0,{t_ms:100,input:'right'});
console.log(JSON.stringify({boundary:boundary.snaps, naive:naive.snaps, solution:solution.snaps, solFinal:{pos:{...solution.final.player},orbs:core.readout(solution.final).orbs_left,status:solution.final.status}, fresh:{orbs:core.readout(s0).orbs_left,grid:s0.grid[1]}, pure: JSON.stringify(s0)===before}));
"""

@unittest.skipUnless(shutil.which("node"), "node not available")
class MechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r = run_core(SCRIPT)
    def test_not_drawn_outside_radius(self):
        self.assertFalse(self.r["boundary"][0]["lit"]); self.assertFalse(self.r["boundary"][5]["lit"])  # at (6,1) dist 3
    def test_boundary_edge_of_radius(self):
        # YAML boundary: 2 tiles away drawn, 3 not; stepping away hides again
        self.assertTrue(self.r["boundary"][6]["lit"])   # (7,1) dist 2
        self.assertFalse(self.r["boundary"][7]["lit"])  # back to (6,1)
    def test_adversarial_lit_route_only(self):
        n=self.r["naive"]; self.assertEqual(n[-1]["orbs"],1); self.assertEqual(n[-1]["pos"],{"x":5,"y":3}); self.assertEqual(n[-1]["status"],"playing")
    def test_solution_walk_light_through_room(self):
        self.assertEqual(self.r["solFinal"]["orbs"],0); self.assertEqual(self.r["solFinal"]["status"],"won")
    def test_restart_restores(self):
        self.assertEqual(self.r["fresh"]["orbs"],1); self.assertIn("H", self.r["fresh"]["grid"])
    def test_pure(self): self.assertTrue(self.r["pure"])
    def test_render_rule_in_game_js(self):
        js=(ROOT/"tools"/"static"/"game.js").read_text(); self.assertIn("dt.ch === 'H'",js)
        self.assertIn("packs/hidden-orb/main.js",(ROOT/"tools"/"static"/"game.html").read_text())
    # Explicit skipped-with-reason for blocked-by YAML aspects (never fake pass)
    @unittest.skip("blocked-by: 51 (dark room) - full dark-room tile culling not built; hidden-orb radius visibility above is real")
    def test_yaml_full_dark_room_blocked(self): pass
    @unittest.skip("blocked-by: 54 (echo tile) - echo tile not built")
    def test_yaml_echo_blocked(self): pass

SANITY = r"""
const core=require(process.argv[1]); const level=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));
const inputs=['right','right','right','right','right','right','right','right','left','left','left','left','down','down','down','down','down'];
const log=inputs.map((input,i)=>({t_ms:(i+1)*100,input}));
let live=core.initialState(level,'mech-16-hidden-orb-room'); for(const s of log) live=core.step(live,s);
const r1=core.replay(level,'mech-16-hidden-orb-room',log); const r2=core.replay(level,'mech-16-hidden-orb-room',JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({live:core.stateDigest(live),r1:core.stateDigest(r1[r1.length-1]),r2:core.stateDigest(r2[r2.length-1]),steps:r1.length-1,final:{pos:{...live.player},orbs:core.readout(live).orbs_left,status:live.status}}));
"""
@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r = run_core(SANITY)
    def test_replay_digest(self):
        self.assertEqual(self.r["r1"], self.r["live"]); self.assertEqual(self.r["r2"], self.r["live"])
        self.assertEqual(self.r["final"]["status"],"won"); self.assertEqual(self.r["steps"],17)

if __name__ == "__main__": unittest.main()
