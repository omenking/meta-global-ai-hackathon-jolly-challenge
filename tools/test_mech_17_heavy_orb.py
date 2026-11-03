"""Checks for the heavy orb (mech-17-heavy-orb).

The mechanic lives in the pure GameCore step (packs/heavy-orb);
driven here under Node against the teaching room. Rules: the orb
is a solid object pushed one tile at a time like a block and never
walked over; it cannot be pushed into walls or water (neither the
orb nor the player moves); pushing it onto a scale tile locks it
there and counts it as collected; restart (fresh state) restores
it. Covers every test_cases entry in orbs.yml mechanic #17; the
magnet-glove case is blocked-by mechanic 63 (unbuilt) and is an
explicit skip, never a fake pass.

Run with: python -m unittest tools.test_mech_17_heavy_orb -v
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

LEVEL_ID = "mech-17-heavy-orb-room"


class HeavyOrbRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("H"), 1)
        self.assertEqual(grid.count("S"), 1)
        orb = [(x, y) for y, r in enumerate(rows)
               for x, ch in enumerate(r) if ch == "H"][0]
        scale = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "S"][0]
        # The scale sits due south of the orb: the corrected push.
        self.assertEqual(scale, (orb[0], orb[1] + 2))
        # The pocket: the far east cell of the orb's row is walled
        # north, south and east, so a straight-ahead push strands it.
        pocket = (len(rows[0]) - 2, orb[1])
        self.assertEqual(rows[pocket[1]][pocket[0]], ".")
        self.assertEqual(rows[pocket[1] - 1][pocket[0]], "#")
        self.assertEqual(rows[pocket[1] + 1][pocket[0]], "#")
        self.assertEqual(rows[pocket[1]][pocket[0] + 1], "#")


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function orbOf(s) {
  for (let y = 0; y < s.objects.length; y++)
    for (let x = 0; x < s.objects[y].length; x++) {
      const id = s.objects[y][x];
      if (id === 'heavy:orb' || id === 'heavy:orb-locked')
        return { x, y, id };
    }
  return null;
}
function run(seq) {
  let s = core.initialState(level, 'mech-17-heavy-orb-room');
  const snap = () => ({ pos: { ...s.player }, orb: orbOf(s),
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// Solution: stand north of the orb, push it south onto the scale,
// then leave through the gate to the warp.
const solution = run(['right', 'right', 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'right',
  'down', 'down', 'down', 'right', 'right']);
// Adversarial: push it straight east into the wall pocket.
const pocket = run(['down', 'down', 'right',
  'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'right', 'right', 'left']);
// Boundary (wall): push the orb north into the top wall.
const wall = run(['right', 'right', 'right', 'down', 'down', 'down',
  'left', 'up', 'up', 'up']);
// Boundary (water): manoeuvre the orb beside the pool, push east.
const water = run(['right', 'right', 'down', 'down',
  'left', 'down', 'right', 'right', 'right',
  'up', 'right', 'down', 'down', 'left', 'down', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-17-heavy-orb-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution, pocket, wall, water,
  fresh: (() => { const f = core.initialState(level,
    'mech-17-heavy-orb-room');
    return { pos: { ...f.player }, orb: orbOf(f),
      orbs: core.readout(f).orbs_left }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class HeavyOrbMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_push_onto_the_scale(self):
        s = self.r["solution"]
        self.assertEqual(s[0]["orb"], {"x": 3, "y": 3, "id": "heavy:orb"})
        self.assertEqual(s[0]["orbs"], 1)
        # One press moves the orb exactly one tile at a time.
        self.assertEqual(s[4]["orb"], {"x": 3, "y": 4, "id": "heavy:orb"})
        self.assertEqual(s[4]["pos"], {"x": 3, "y": 3})
        # Onto the scale: locked there and counted as collected.
        self.assertEqual(s[5]["orb"],
                         {"x": 3, "y": 5, "id": "heavy:orb-locked"})
        self.assertEqual(s[5]["orbs"], 0)
        # Locked means locked: it never moves again on the way out.
        self.assertEqual(s[-1]["orb"],
                         {"x": 3, "y": 5, "id": "heavy:orb-locked"})
        self.assertEqual(s[-1]["status"], "won")

    def test_adversarial_pocketed_orb(self):
        p = self.r["pocket"]
        # Straight east along the lane pockets the orb at (11, 3).
        self.assertEqual(p[11]["orb"], {"x": 11, "y": 3, "id": "heavy:orb"})
        self.assertEqual(p[11]["pos"], {"x": 10, "y": 3})
        # Pressing on east moves neither the orb nor the player.
        self.assertEqual(p[12]["orb"], {"x": 11, "y": 3, "id": "heavy:orb"})
        self.assertEqual(p[12]["pos"], {"x": 10, "y": 3})
        self.assertEqual(p[13]["orb"], {"x": 11, "y": 3, "id": "heavy:orb"})
        # The player is never stranded: still playing, free to move
        # away, and restart (fresh state) restores the orb.
        self.assertEqual(p[13]["status"], "playing")
        self.assertEqual(p[14]["pos"], {"x": 9, "y": 3})
        self.assertEqual(self.r["fresh"]["orb"],
                         {"x": 3, "y": 3, "id": "heavy:orb"})

    def test_boundary_push_toward_wall_moves_neither(self):
        w = self.r["wall"]
        self.assertEqual(w[8]["orb"], {"x": 3, "y": 2, "id": "heavy:orb"})
        self.assertEqual(w[9]["orb"], {"x": 3, "y": 1, "id": "heavy:orb"})
        self.assertEqual(w[9]["pos"], {"x": 3, "y": 2})
        # The next press north faces the wall: nothing moves.
        self.assertEqual(w[10]["orb"], {"x": 3, "y": 1, "id": "heavy:orb"})
        self.assertEqual(w[10]["pos"], {"x": 3, "y": 2})
        self.assertEqual(w[10]["status"], "playing")

    def test_boundary_push_toward_water_moves_neither(self):
        w = self.r["water"]
        self.assertEqual(w[15]["orb"], {"x": 6, "y": 6, "id": "heavy:orb"})
        self.assertEqual(w[15]["pos"], {"x": 5, "y": 6})
        # Pressing east faces water at (7, 6): nothing moves and
        # neither the orb nor the player enters it.
        self.assertEqual(w[16]["orb"], {"x": 6, "y": 6, "id": "heavy:orb"})
        self.assertEqual(w[16]["pos"], {"x": 5, "y": 6})
        self.assertEqual(w[16]["status"], "playing")

    def test_restart_restores_the_orb(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1},
                          "orb": {"x": 3, "y": 3, "id": "heavy:orb"},
                          "orbs": 1})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    @unittest.skip("blocked-by: 63 (magnet glove) — mechanic 63 is "
                   "unbuilt, so a stranded heavy orb cannot yet be "
                   "pulled back; restart is the recovery path")
    def test_magnet_pull_recovers_a_stranded_orb(self):
        pass

    def test_pack_assets_and_rendering_wired(self):
        pack = ROOT / "tools" / "static" / "packs" / "heavy-orb"
        manifest = json.loads((pack / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "heavy-orb")
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"])
            self.assertTrue((pack / "assets" / entry["file"]).is_file(),
                            entry["file"])
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("heavy:orb-locked", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/heavy-orb/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right', 'right',
  'down', 'down', 'down', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-17-heavy-orb-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-17-heavy-orb-room', log);
const replayed2 = core.replay(level, 'mech-17-heavy-orb-room',
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
                         {"pos": {"x": 11, "y": 7}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 16)


if __name__ == "__main__":
    unittest.main()
