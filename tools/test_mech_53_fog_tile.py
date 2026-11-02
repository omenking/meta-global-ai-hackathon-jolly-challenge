"""Checks for the fog tile (mech-53-fog-tile).

The mechanic lives in the fog pack: a fog tile never shows what
is on it until the player stands next to it (Manhattan <= 1,
sharing a side), after which fog_revealed stays set in cell meta
for the attempt. Movement through fog is normal. Driven here
under Node against the teaching room. Covers every YAML
test_cases entry for mechanic 53; the mimic-in-fog case is
blocked-by 36 (mimic orb) and is an explicit skip, never a pass.

Run with: python -m unittest tools.test_mech_53_fog_tile -v
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

LEVEL_ID = "mech-53-fog-tile-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


class FogRoomLevelTests(unittest.TestCase):
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
        fog_row = next(r for r in rows if "FFFf" in r)
        self.assertEqual(rows.index(fog_row), 5)
        # One visible orb, the gate's last orb hidden in the fog.
        self.assertEqual(grid.count("*"), 1)
        self.assertEqual(grid.count("f"), 1)
        self.assertEqual(grid.count("F"), 3)
        fog_orb = [(x, y) for y, r in enumerate(rows)
                   for x, ch in enumerate(r) if ch == "f"]
        self.assertEqual(fog_orb, [(4, 5)])
        gate = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "G"]
        self.assertEqual(gate, [(11, 1)])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-53-fog-tile-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    steps: s.steps,
    orbs: core.readout(s).orbs_left,
    fogOrb: !!((s.meta['4,5'] || {}).fog_revealed),
    fogEmpty: !!((s.meta['2,5'] || {}).fog_revealed),
    fogOrbRevealedFn: core.isFogRevealed(s, 4, 5) });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const R = (n) => Array(n).fill('right'), L = (n) => Array(n).fill('left');
const D = (n) => Array(n).fill('down'), U = (n) => Array(n).fill('up');
// Solution: down the west side, along the wall (adjacent reveals
// the fog), step onto the fog orb, back up and out the gate.
const sol = run([...D(3), ...R(3), 'down', ...U(4), ...R(8)]);
// Adversarial: the clear floor straight to the gate (entrance
// row, collecting the visible orb), one orb short, gate push
// fails, then recover along the wall. The middle row (y=3) is
// also probed in the boundary run: two tiles from the fog, it
// reveals nothing.
const adv = run([...R(10), ...D(3), ...L(6), 'down', ...U(4), ...R(8)]);
// Boundary: two tiles away reveals nothing; adjacent reveals and
// it stays revealed after walking away; fog crossing is one move.
const bnd = run([...D(2), ...R(3), 'down', ...R(3), ...D(1), ...L(5)]);
const s0 = core.initialState(level, 'mech-53-fog-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, adv: adv.snaps, bnd: bnd.snaps,
  solFinal: { pos: { ...sol.final.player }, status: sol.final.status },
  advFinal: { pos: { ...adv.final.player }, status: adv.final.status },
  fresh: { pos: { ...s0.player },
    orbs: core.readout(s0).orbs_left, fogOrb: !!((s0.meta['4,5'] || {}).fog_revealed) },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class FogMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_search_the_fog_along_the_wall(self):
        sol = self.r["sol"]
        self.assertEqual(sol[0]["orbs"], 2)
        self.assertFalse(sol[0]["fogOrb"])
        # Standing at (4,4), adjacent to the fog orb, reveals it.
        self.assertEqual(sol[6]["pos"], {"x": 4, "y": 4})
        self.assertTrue(sol[6]["fogOrb"])
        # Stepping onto it collects it; both orbs gone by the exit.
        self.assertEqual(sol[7]["pos"], {"x": 4, "y": 5})
        self.assertEqual(sol[7]["orbs"], 1)
        self.assertEqual(self.r["solFinal"],
                         {"pos": {"x": 12, "y": 1}, "status": "won"})

    def test_adversarial_walk_the_clear_middle_floor(self):
        adv = self.r["adv"]
        # Clear-floor route: nine rights land at (10,1) with the
        # visible orb collected and the fog orb still hidden; the
        # tenth right pushes the shut gate and the player stays.
        self.assertFalse(adv[10]["fogOrb"])
        self.assertEqual(adv[10]["pos"], {"x": 10, "y": 1})
        self.assertEqual(adv[10]["orbs"], 1)
        self.assertEqual(adv[10]["status"], "playing")
        # Never stranded: back along the wall reveals and wins.
        self.assertEqual(self.r["advFinal"],
                         {"pos": {"x": 12, "y": 1}, "status": "won"})
        self.assertTrue(all(s["status"] == "playing"
                            for s in adv[:-1]))

    def test_adjacency_and_persistence_boundary(self):
        bnd = self.r["bnd"]
        # At (4,3), two tiles from the fog orb: nothing revealed.
        self.assertEqual(bnd[5]["pos"], {"x": 4, "y": 3})
        self.assertFalse(bnd[5]["fogOrb"])
        # At (4,4), adjacent: revealed (state and core helper agree).
        self.assertEqual(bnd[6]["pos"], {"x": 4, "y": 4})
        self.assertTrue(bnd[6]["fogOrb"])
        self.assertTrue(bnd[6]["fogOrbRevealedFn"])
        # Walking away keeps it revealed for the rest of the attempt.
        self.assertEqual(bnd[9]["pos"], {"x": 7, "y": 4})
        self.assertTrue(bnd[9]["fogOrb"])
        # Movement through fog is normal: stepping west along the
        # fog row advances exactly one tile per step, including
        # onto the empty fog at (2,5).
        self.assertEqual(bnd[13]["pos"], {"x": 4, "y": 5})
        self.assertEqual(bnd[14]["pos"], {"x": 3, "y": 5})
        self.assertEqual(bnd[15]["pos"], {"x": 2, "y": 5})
        self.assertEqual(bnd[15]["steps"], bnd[14]["steps"] + 1)
        self.assertEqual(bnd[15]["status"], "playing")
        self.assertTrue(bnd[15]["fogEmpty"])

    @unittest.skip("blocked-by: 36 (mimic orb) - mimic orb mechanic "
                   "not built on this branch; fog reveal of a mimic "
                   "cannot be checked until it lands")
    def test_mimic_hidden_in_fog(self):
        pass

    def test_restart_restores_hidden_fog(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1}, "orbs": 2,
                          "fogOrb": False})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_fog_states(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("fog-revealed-orb.png", js)
        self.assertIn("fog_revealed", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/fog/main.js", html)
        manifest = json.loads((ROOT / "tools" / "static" / "packs"
                               / "fog" / "manifest.json").read_text(
                                   encoding="utf-8"))
        assets = ROOT / "tools" / "static" / "packs" / "fog" / "assets"
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"])
            self.assertTrue((assets / entry["file"]).is_file(),
                            entry["file"])


if __name__ == "__main__":
    unittest.main()
