"""Checks for the orb pouch (mech-67-orb-pouch).

Pouch levels count orbs UP into a held pouch; pressing into the
orb-door spends exactly 1, the scale exactly 2, with too few held a
press spends nothing; the gate opens on pouch spent, not collected;
unspent held orbs are the score at the warp. Driven under Node
against the teaching room, mirroring test_mech_5_crumbling_tile.py.
Covers every YAML test_cases entry: solution, adversarial, boundary,
gate-reads-spent, restart+replay. No synergy cases are blocked-by
unbuilt mechanics in the YAML, so none are skipped.

Run with: python -m unittest tools.test_mech_67_orb_pouch -v
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

LEVEL_ID = "mech-67-orb-pouch-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class PouchRoomLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = game_levels.load_level(ROOT / "levels", LEVEL_ID)

    def test_room_is_a_test_level(self):
        self.assertTrue(self.level["test"])
        self.assertTrue(self.level["pouch"])
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
        self.assertEqual(grid.count("*"), 4)
        self.assertEqual(grid.count("D"), 1)
        self.assertEqual(grid.count("S"), 1)
        # Door before the scale on the top route; long way round the
        # bottom crosses the divider line on plain floor.
        top = rows[1]
        self.assertLess(top.index("D"), top.index("S"))
        self.assertLess(top.index("S"), top.index("G"))
        self.assertLess(top.index("G"), top.index("X"))
        door_x = top.index("D")
        self.assertEqual(rows[-2][door_x], ".")


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-67-orb-pouch-room');
  seq.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); });
  return s;
}
function info(s) {
  return { pos: { ...s.player }, held: s.counters['pouch:held'],
    spent: s.counters['pouch:spent'], collected: s.counters['pouch:collected'],
    score: s.counters['pouch:score'], gate: s.gate_open, status: s.status,
    orbsLeft: core.readout(s).orbs_left, row1: s.grid[1] };
}
// Corrected: long way round, collect all 4, save for the scale.
const corrected = ['down','right','down','down','down',
  'right','right','right','right','right','right','right',
  'up','up','up','up','right','right','right','right'];
const preScale = run(corrected.slice(0, 16));
const atScale = run(corrected.slice(0, 18));
const solved = run(corrected);
// Naive: spend 1 on the shortcut door first, arrive 1 short.
const naive = ['down','right','up','right','right','right','right',
  'right','right','right','right','right','right'];
const naiveShort = run(naive);
const naiveFull = run([...naive,
  'left','left','left','left','left','down','down','down','down',
  'right','right','right','right','up','up','up','up',
  'right','right','right','right']);
// Boundary: press the door holding nothing.
const doorPoor = run(['right','right','right','right','right']);
// Collect only, spend nothing.
const collectOnly = run(corrected.slice(0, 16));
const s0 = core.initialState(level, 'mech-67-orb-pouch-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  preScale: info(preScale), atScale: info(atScale), solved: info(solved),
  naiveShort: info(naiveShort), naiveFull: info(naiveFull),
  doorPoor: info(doorPoor), collectOnly: info(collectOnly),
  fresh: info(core.initialState(level, 'mech-67-orb-pouch-room')),
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class PouchMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_save_for_the_scale(self):
        # YAML: solution save for the scale.
        self.assertEqual(self.r["preScale"]["held"], 4)
        self.assertEqual(self.r["preScale"]["collected"], 4)
        self.assertEqual(self.r["atScale"]["pos"], {"x": 11, "y": 1})
        self.assertEqual(self.r["atScale"]["held"], 2)
        self.assertEqual(self.r["atScale"]["spent"], 2)
        self.assertTrue(self.r["atScale"]["gate"])
        self.assertEqual(self.r["solved"]["pos"], {"x": 13, "y": 1})
        self.assertEqual(self.r["solved"]["status"], "won")
        self.assertEqual(self.r["solved"]["score"], 2)

    def test_counter_counts_up_not_down(self):
        self.assertEqual(self.r["fresh"]["held"], 0)
        self.assertEqual(self.r["fresh"]["orbsLeft"], 0)
        self.assertEqual(self.r["collectOnly"]["held"], 4)
        self.assertEqual(self.r["collectOnly"]["orbsLeft"], 4)

    def test_adversarial_shortcut_first(self):
        # YAML: adversarial shortcut first - one short, never stranded,
        # no orb spent twice (spent total is exactly 1 + 2).
        n = self.r["naiveShort"]
        self.assertEqual(n["pos"], {"x": 10, "y": 1})
        self.assertEqual(n["held"], 1)
        self.assertEqual(n["spent"], 1)
        self.assertFalse(n["gate"])
        f = self.r["naiveFull"]
        self.assertEqual(f["status"], "won")
        self.assertEqual(f["spent"], 3)
        self.assertEqual(f["score"], 1)
        self.assertEqual(f["collected"], 4)

    def test_boundary_exact_stated_costs(self):
        # YAML: boundary exact stated costs.
        d = self.r["doorPoor"]
        self.assertEqual(d["pos"], {"x": 5, "y": 1})
        self.assertEqual(d["held"], 0)
        self.assertEqual(d["spent"], 0)
        self.assertEqual(d["row1"], "#P....D..*.SGX#")
        # Scale with 1 held spends nothing and stays shut (naiveShort);
        # door spent exactly 1 and scale exactly 2 in the flows above.
        self.assertEqual(self.r["naiveShort"]["spent"], 1)

    def test_gate_reads_spent_not_collected(self):
        # YAML: gate reads spent, not collected.
        c = self.r["collectOnly"]
        self.assertEqual(c["collected"], 4)
        self.assertEqual(c["spent"], 0)
        self.assertFalse(c["gate"])
        self.assertTrue(self.r["atScale"]["gate"])

    def test_restart_restores_pouch(self):
        f = self.r["fresh"]
        self.assertEqual(f["held"], 0)
        self.assertEqual(f["spent"], 0)
        self.assertEqual(f["score"], 0)
        self.assertEqual(f["row1"], "#P....D..*.SGX#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_wired_into_game(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/orb-pouch/main.js", html)
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("dt.ch === 'D'", js)
        pack = ROOT / "tools" / "static" / "packs" / "orb-pouch"
        manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "orb-pouch")
        for entry in manifest["assets"] + manifest["gui"]:
            self.assertTrue(entry["bundled"])
            self.assertTrue((pack / "assets" / entry["file"]).is_file(), entry["file"])


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down','right','down','down','down',
  'right','right','right','right','right','right','right',
  'up','up','up','up','right','right','right','right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-67-orb-pouch-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-67-orb-pouch-room', log);
const replayed2 = core.replay(level, 'mech-67-orb-pouch-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  final: { pos: { ...live.player }, status: live.status,
    held: live.counters['pouch:held'], spent: live.counters['pouch:spent'],
    score: live.counters['pouch:score'] } }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    """YAML: restart and replay - recorded session replays identically."""

    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["replaySteps"], 20)
        self.assertEqual(self.r["final"], {"pos": {"x": 13, "y": 1},
                         "status": "won", "held": 2, "spent": 2, "score": 2})


if __name__ == "__main__":
    unittest.main()
