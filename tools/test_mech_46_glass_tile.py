"""Checks for the glass tile (mech-46-glass-tile).

Rules (candidate mechanic #46): first crossing cracks it, second
crossing in either direction shatters it after you leave and it
becomes void; standing on cracked glass is safe. Driven under
Node against the teaching room, mirroring test_mech_5.

Run with: python -m unittest tools.test_mech_46_glass_tile -v
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

LEVEL_ID = "mech-46-glass-tile-room"


class GlassRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("g"), 1)
        self.assertGreaterEqual(grid.count("*"), 2)
        glass_row = next(r for r in rows if "g" in r)
        gx = glass_row.index("g")
        far_orb = [(x, y) for y, r in enumerate(rows)
                   for x, ch in enumerate(r) if ch == "*"]
        self.assertTrue(any(x > gx for x, _ in far_orb),
                        "no orb beyond the glass")
        bottom = rows[-2]
        self.assertEqual(bottom[gx], ".")


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-46-glass-tile-room');
  const snap = () => ({ pos: { ...s.player }, row: s.grid[2],
    status: s.status, orbs: core.readout(s).orbs_left,
    stage: (s.meta['5,2'] || {}).glass_stage || 0 });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toBridge = ['right', 'right', 'right', 'down'];
const a = run([...toBridge, 'right', 'right', 'up', 'right', 'right',
  'left', 'left', 'down', 'left', 'left', 'right']);
const b = run([...toBridge, 'right', 'up', 'up', 'right']);
const c = run([...toBridge, 'right', 'right', 'left', 'up', 'up', 'left']);
const d = run(['right', 'right', 'right', 'down', 'right', 'right',
  'up', 'right', 'right', 'down', 'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left', 'left',
  'up', 'up', 'up', 'up', 'up']);
const s0 = core.initialState(level, 'mech-46-glass-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, d: d.snaps,
  dFinal: { pos: { ...d.final.player },
    orbs: core.readout(d.final).orbs_left },
  freshRow: core.initialState(level,
    'mech-46-glass-tile-room').grid[2],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GlassMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_first_crossing_cracks_on_leaving_not_on_step_on(self):
        a = self.r["a"]
        self.assertEqual(a[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(a[5]["pos"], {"x": 5, "y": 2})
        self.assertEqual(a[5]["stage"], 0)
        self.assertEqual(a[6]["pos"], {"x": 6, "y": 2})
        self.assertEqual(a[6]["stage"], 1)
        self.assertEqual(a[6]["row"], "#....g......#")

    def test_there_and_back_exactly_once_then_shatters(self):
        a = self.r["a"]
        self.assertEqual(a[9]["orbs"], 1)
        self.assertEqual(a[13]["pos"], {"x": 5, "y": 2})
        self.assertEqual(a[13]["stage"], 1)
        self.assertEqual(a[13]["status"], "playing")
        self.assertEqual(a[14]["pos"], {"x": 4, "y": 2})
        self.assertEqual(a[14]["row"], "#....V......#")

    def test_adversarial_third_approach_is_blocked_not_stranded(self):
        a = self.r["a"]
        self.assertEqual(a[15]["pos"], {"x": 4, "y": 2})
        self.assertEqual(a[15]["status"], "playing")
        self.assertEqual(a[15]["row"], "#....V......#")
        # Long way in run d resolves the room from the far side.
        self.assertEqual(self.r["dFinal"],
                         {"pos": {"x": 1, "y": 1}, "orbs": 0})

    def test_safe_standing_on_intact_and_cracked_glass(self):
        b = self.r["b"]
        self.assertEqual(b[7]["pos"], {"x": 5, "y": 2})
        self.assertEqual(b[7]["stage"], 0)
        self.assertEqual(b[8]["stage"], 1)
        c = self.r["c"]
        self.assertEqual(c[9]["pos"], {"x": 5, "y": 2})
        self.assertEqual(c[9]["stage"], 1)
        self.assertEqual(c[9]["status"], "playing")
        self.assertEqual(c[10]["row"], "#....V......#")

    def test_solution_long_way_preserves_cracked_glass(self):
        d = self.r["d"]
        self.assertEqual(d[-1]["row"], "#....g......#")
        self.assertEqual(d[-1]["stage"], 1)

    def test_restart_restores_intact_glass(self):
        self.assertEqual(self.r["freshRow"], "#....g......#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_assets_and_renderer_wiring(self):
        pack = ROOT / "tools" / "static" / "packs" / "glass-tile"
        manifest = json.loads((pack / "manifest.json").read_text())
        self.assertEqual(manifest["pack"], "glass-tile")
        self.assertEqual([a["file"] for a in manifest["assets"]],
                         ["glass.png", "glass-cracked.png", "void.png"])
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"])
            self.assertTrue((pack / "assets" / entry["file"]).is_file(),
                            entry["file"])
        js = (ROOT / "tools" / "static" / "game.js").read_text()
        self.assertIn("dt.ch === 'g'", js)
        self.assertIn("glass-cracked.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text()
        self.assertIn("packs/glass-tile/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'down', 'right', 'right',
  'up', 'right', 'right', 'down', 'down', 'down', 'down', 'down',
  'left', 'left', 'left', 'left', 'left', 'left', 'left',
  'up', 'up', 'up', 'up', 'up'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-46-glass-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-46-glass-tile-room', log);
const replayed2 = core.replay(level, 'mech-46-glass-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row: replayed[replayed.length - 1].grid[2],
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
                         {"pos": {"x": 1, "y": 1}, "orbs": 0})
        self.assertEqual(self.r["row"], "#....g......#")
        self.assertEqual(self.r["replaySteps"], 26)


if __name__ == "__main__":
    unittest.main()
