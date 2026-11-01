"""Checks for the master key (mech-12-master-key).

The mechanic lives in packs/master-key/main.js, driven here under
Node against the teaching room. Rules: a silver master key fits any
lock; pressing it into a lock of any colour consumes the master key
and dissolves that one lock only. Holding the matching coloured key
spends that key first, which is how the master is saved. Blocked
case (twin lock, mech 11) is an explicit skip, never a fake pass.

Run with: python -m unittest tools.test_mech_12_master_key -v
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

LEVEL_ID = "mech-12-master-key-room"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class MasterKeyRoomLevelTests(unittest.TestCase):
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
        def pos(ch):
            for y, r in enumerate(rows):
                if ch in r:
                    return (r.index(ch), y)
        self.assertEqual(pos("P"), (1, 1))
        self.assertEqual(pos("M"), (3, 1))
        self.assertEqual(pos("r"), (3, 2))
        self.assertEqual(pos("R"), (5, 3))
        self.assertEqual(pos("B"), (7, 5))
        self.assertEqual(pos("*"), (7, 6))
        grid = "".join(rows)
        # No blue key anywhere: the missing colour is the lesson.
        self.assertNotIn("b", grid)
        self.assertEqual(self.level["legend"]["M"]["def"], "master:key")
        self.assertEqual(self.level["legend"]["R"]["def"], "master:lock-red")
        self.assertEqual(self.level["legend"]["B"]["def"], "master:lock-blue")


class MasterKeyPackTests(unittest.TestCase):
    def test_manifest_lists_both_assets_bundled_with_shows(self):
        manifest = json.loads((ROOT / "tools/static/packs/master-key/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "master-key")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled], ["master-key.png", "master-key-held.png"])
        for entry in bundled:
            self.assertTrue(entry["shows"])
            path = ROOT / "tools/static/packs/master-key/assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])

    def test_main_js_declares_assets_and_no_wall_clock(self):
        js = (ROOT / "tools/static/packs/master-key/main.js").read_text(encoding="utf-8")
        self.assertIn("defineAsset('master-key.png'", js)
        self.assertIn("defineAsset('master-key-held.png'", js)
        self.assertIn("master:master-key", js)
        self.assertNotIn("Date.now", js)
        self.assertNotIn("performance.now", js)
        html = (ROOT / "tools/static/game.html").read_text(encoding="utf-8")
        self.assertIn("packs/master-key/main.js", html)


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
  let s = core.initialState(level, 'mech-12-master-key-room');
  const snap = () => ({ pos: { ...s.player }, inv: core.readout(s).inventory,
    status: s.status, orbs: core.readout(s).orbs_left,
    rTile: s.grid[3], bTile: s.grid[5] });
  const snaps = [snap()];
  seq.forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); snaps.push(snap()); });
  return snaps;
}
const solution = run(['right','right','down','up','right','right','down','down','down','right','right','down','down']);
const naive = run(['right','right','right','right','down','down','down','right','right','down','left']);
// One-use boundary on a synthetic two-lock corridor (any colour).
const synth = (() => {
  const legend = { '.': {label:'floor'}, '#': {label:'wall'}, 'P': {label:'player'},
    'M': {label:'master key', def:'master:key'},
    'R': {label:'lock red', def:'master:lock-red'},
    'B': {label:'lock blue', def:'master:lock-blue'} };
  const lv = { rows: ['########', '#PMRB..#', '########'], legend, time_limit: 120 };
  let s = core.initialState(lv, 'synth-room');
  const snaps = [{ pos: { ...s.player }, inv: core.readout(s).inventory, row: s.grid[1] }];
  ['right','right','right'].forEach((input, i) => { s = core.step(s, { t_ms: (i + 1) * 100, input }); snaps.push({ pos: { ...s.player }, inv: core.readout(s).inventory, row: s.grid[1] }); });
  return snaps;
})();
const s0 = core.initialState(level, 'mech-12-master-key-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ solution, naive, synth,
  fresh: { inv: core.readout(s0).inventory, row1: s0.grid[1], row3: s0.grid[3], row5: s0.grid[5] },
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MasterKeyMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_saving_it_for_the_missing_colour(self):
        snaps = self.r["solution"]
        # Both keys held after the detour to the red key.
        self.assertEqual(snaps[3]["inv"], ["master", "red"])
        # Red lock spends the red key first: master survives.
        self.assertEqual(snaps[8]["pos"], {"x": 5, "y": 3})
        self.assertEqual(snaps[8]["inv"], ["master"])
        self.assertEqual(snaps[8]["rTile"], "#####.#######")
        # Blue lock spends the master: exactly that lock dissolves.
        self.assertEqual(snaps[12]["pos"], {"x": 7, "y": 5})
        self.assertEqual(snaps[12]["inv"], [])
        self.assertEqual(snaps[12]["bTile"], "#######.#####")
        self.assertEqual(snaps[13]["pos"], {"x": 7, "y": 6})
        self.assertEqual(snaps[13]["orbs"], 0)

    def test_adversarial_spending_it_on_the_convenient_lock(self):
        snaps = self.r["naive"]
        # Master spent on red (only master held): master is gone.
        self.assertEqual(snaps[6]["pos"], {"x": 5, "y": 3})
        self.assertEqual(snaps[6]["inv"], [])
        # Blue lock stays locked, player unmoved, not stranded.
        self.assertEqual(snaps[10]["pos"], {"x": 7, "y": 4})
        self.assertEqual(snaps[10]["bTile"], "#######B#####")
        self.assertEqual(snaps[10]["status"], "playing")
        self.assertEqual(snaps[11]["pos"], {"x": 6, "y": 4})

    def test_one_use_boundary_on_any_colour(self):
        snaps = self.r["synth"]
        self.assertEqual(snaps[1]["inv"], ["master"])
        # First lock (red) dissolves, master consumed.
        self.assertEqual(snaps[2]["pos"], {"x": 3, "y": 1})
        self.assertEqual(snaps[2]["inv"], [])
        self.assertEqual(snaps[2]["row"], "#P..B..#")
        # Second lock (blue) unchanged and blocks without a key.
        self.assertEqual(snaps[3]["pos"], {"x": 3, "y": 1})
        self.assertEqual(snaps[3]["row"], "#P..B..#")

    def test_step_is_pure_and_restart_restores(self):
        self.assertTrue(self.r["pure"])
        self.assertEqual(self.r["fresh"]["inv"], [])
        self.assertEqual(self.r["fresh"]["row1"], "#P.M........#")
        self.assertEqual(self.r["fresh"]["row3"], "#####R#######")
        self.assertEqual(self.r["fresh"]["row5"], "#######B#####")

    @unittest.skip("blocked-by: 11 (Twin lock): one master covers one of the two keys a twin lock demands — twin lock mechanic not yet built")
    def test_twin_lock_covers_only_one_of_two(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right','right','down','up','right','right','down','down','down','right','right','down','down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-12-master-key-room');
for (const e of log) live = core.step(live, e);
const replayed = core.replay(level, 'mech-12-master-key-room', log);
const replayed2 = core.replay(level, 'mech-12-master-key-room', JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, inv: core.readout(live).inventory, orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1 }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SanityReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(SANITY_SCRIPT)

    def test_full_playthrough_replays_to_same_end_state(self):
        self.assertEqual(self.r["replayDigest"], self.r["liveDigest"])
        self.assertEqual(self.r["replay2Digest"], self.r["liveDigest"])
        self.assertEqual(self.r["liveFinal"], {"pos": {"x": 7, "y": 6}, "inv": [], "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 13)


if __name__ == "__main__":
    unittest.main()
