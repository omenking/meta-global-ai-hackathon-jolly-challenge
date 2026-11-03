"""Checks for the peep hole (mech-60-peep-hole).

The mechanic lives in the pure GameCore step (packs/peephole):
stepping on the hole locks the player on it for 2000ms of recorded
t_ms (a tick hook teleports any move back), the timer keeps running
through the lock, the preview covers only the 5-wide strip above
the door, and looking alone opens nothing. Restart (fresh state)
restores the unused hole and the black next room.

YAML test_cases coverage: 'peeping opens no way through' and
'restart and replay' run in full. The three cases marked
blocked-by 4 (one-way door) / 48 (checkpoint) carry explicit
skipped-with-reason checks below; the parts of those cases that do
not need the missing mechanics (preview-then-enter with the key,
naive entry blocked at the lock, the 2000ms lock boundary) run
for real through the stand-in door tile in the teaching room.

Run with: python -m unittest tools.test_mech_60_peep_hole -v
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

LEVEL_ID = "mech-60-peep-hole-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "peephole" / "main.js"
MANIFEST = ROOT / "tools" / "static" / "packs" / "peephole" / "manifest.json"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class PeepHoleLevelTests(unittest.TestCase):
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
        for ch in "PHDLk*X":
            self.assertEqual(grid.count(ch), 1, ch)
        pos = {ch: (r.index(ch), y) for y, r in enumerate(rows) for ch in r}
        # Peep hole, door, lock and key share one column: the pan
        # looks straight up at the lock it previews.
        self.assertEqual(pos["H"][0], pos["D"][0])
        self.assertEqual(pos["D"][0], pos["L"][0])
        self.assertEqual(pos["L"][0], pos["k"][0])
        self.assertLess(pos["L"][1], pos["D"][1])
        self.assertLess(pos["D"][1], pos["H"][1])
        # The orb sits far right in the next room, outside the
        # 5-wide preview strip centred on the hole's column.
        self.assertGreater(pos["*"][0], pos["H"][0] + 2)
        self.assertLess(pos["*"][1], pos["D"][1])


class PeepHoleAssetTests(unittest.TestCase):
    def test_manifest_lists_every_yaml_asset_bundled(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "peephole")
        files = [a["file"] for a in manifest["assets"]]
        self.assertEqual(files, ["peep-hole.png", "peep-hole-active.png",
                                 "unrevealed-room.png", "jolly-peeping.png"])
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"], entry["file"])
            self.assertTrue(entry["shows"], entry["file"])
            path = ROOT / "tools/static/packs/peephole/assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])

    def test_pack_and_game_wiring(self):
        js = PACK.read_text(encoding="utf-8")
        self.assertIn("peep:hole", js)
        self.assertIn("defineAsset", js)
        core = (ROOT / "tools/static/game-core.js").read_text(encoding="utf-8")
        self.assertIn("packs/peephole/main.js", core)
        html = (ROOT / "tools/static/game.html").read_text(encoding="utf-8")
        self.assertIn("packs/peephole/main.js", html)
        game = (ROOT / "tools/static/game.js").read_text(encoding="utf-8")
        self.assertIn("peep:active", game)
        self.assertIn("peep-hole-active.png", game)


def run_core(script):
    out = subprocess.run(
        ["node", "-e", script, str(CORE), str(LEVEL), str(PACK)],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const pack = require(process.argv[3]);
function run(log) {
  let s = core.initialState(level, 'mech-60-peep-hole-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    active: !!s.flags['peep:active'], until: s.flags['peep:until_ms'],
    entered: !!s.flags['peep:entered_next'],
    orbs: core.readout(s).orbs_left,
    inv: core.readout(s).inventory, elapsed: s.elapsed_s,
    row1: s.grid[1], row2: s.grid[2] });
  const snaps = [snap()];
  for (const stepIn of log) { s = core.step(s, stepIn); snaps.push(snap()); }
  return { snaps, final: s };
}
const M = (t_ms, input) => ({ t_ms, input });
// Solution: key, peep, locked attempt, unlock at 2000ms, enter.
const solution = run([M(100,'right'),M(200,'right'),M(300,'right'),
  M(400,'right'),M(500,'up'),M(1500,'right'),M(2500,'up'),M(2600,'up'),
  M(2700,'up'),M(2800,'right'),M(2900,'right'),M(3000,'right'),
  M(3100,'right'),M(3200,'right')]);
// Naive: no key, straight to the door; the lock blocks entry.
const naive = run([M(100,'up'),M(200,'right'),M(300,'right'),
  M(400,'right'),M(500,'right'),M(2500,'wait'),M(2600,'up'),M(2700,'up'),
  M(2800,'down')]);
// Lock boundary: attempts at 1000 and 2499 stay, at 2500 move.
const boundary = run([M(100,'up'),M(200,'right'),M(300,'right'),
  M(400,'right'),M(500,'right'),M(1000,'left'),M(2499,'left'),
  M(2500,'left')]);
// Peep only: trigger, wait out the preview, never cross the door.
const peepOnly = run([M(100,'up'),M(200,'right'),M(300,'right'),
  M(400,'right'),M(500,'right'),M(2500,'wait')]);
// Preview geometry from the pack helper on the peeping state.
let ps = core.initialState(level, 'mech-60-peep-hole-room');
for (const stepIn of [M(100,'up'),M(200,'right'),M(300,'right'),
  M(400,'right'),M(500,'right')]) ps = core.step(ps, stepIn);
const preview = pack.previewCells(ps);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-60-peep-hole-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution: solution.snaps, naive: naive.snaps,
  boundary: boundary.snaps, peepOnly: peepOnly.snaps,
  preview: preview,
  fresh: { active: !!core.initialState(level,
      'mech-60-peep-hole-room').flags['peep:active'],
    entered: !!core.initialState(level,
      'mech-60-peep-hole-room').flags['peep:entered_next'],
    row2: core.initialState(level, 'mech-60-peep-hole-room').grid[2] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class PeepHoleMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_preview_then_enter_with_key(self):
        s = self.r["solution"]
        self.assertEqual(s[4]["pos"], {"x": 5, "y": 5})  # key tile
        self.assertEqual(s[4]["inv"], ["gold"])
        self.assertEqual(s[5]["pos"], {"x": 5, "y": 4})  # peep hole
        self.assertTrue(s[5]["active"])
        self.assertEqual(s[5]["until"], 2500)
        # Locked attempt: position holds, timer keeps running.
        self.assertEqual(s[6]["pos"], {"x": 5, "y": 4})
        self.assertTrue(s[6]["active"])
        self.assertEqual(s[6]["elapsed"], 1.5)
        # At exactly peep_start + 2000ms the player may move again.
        self.assertEqual(s[7]["pos"], {"x": 5, "y": 3})
        self.assertFalse(s[7]["active"])
        self.assertTrue(s[-1]["entered"])
        self.assertEqual(s[-1]["pos"], {"x": 10, "y": 1})
        self.assertEqual(s[-1]["status"], "won")
        self.assertEqual(s[-1]["orbs"], 0)

    def test_naive_entry_without_key_blocked_at_lock(self):
        n = self.r["naive"]
        self.assertEqual(n[5]["pos"], {"x": 5, "y": 4})
        self.assertTrue(n[5]["active"])
        self.assertEqual(n[7]["pos"], {"x": 5, "y": 3})  # door tile
        # The lock blocks without its key; the player is not
        # stranded and walks back out the way they came.
        self.assertEqual(n[8]["pos"], {"x": 5, "y": 3})
        self.assertEqual(n[8]["status"], "playing")
        self.assertEqual(n[9]["pos"], {"x": 5, "y": 4})

    def test_two_second_locked_boundary(self):
        b = self.r["boundary"]
        self.assertEqual(b[5]["pos"], {"x": 5, "y": 4})
        self.assertEqual(b[6]["pos"], {"x": 5, "y": 4})  # t=1000
        self.assertEqual(b[7]["pos"], {"x": 5, "y": 4})  # t=2499
        self.assertTrue(b[7]["active"])
        self.assertEqual(b[7]["elapsed"], 2.499)
        self.assertEqual(b[8]["pos"], {"x": 4, "y": 4})  # t=2500
        self.assertFalse(b[8]["active"])

    def test_preview_is_partial_lock_in_orb_out(self):
        cells = self.r["preview"]
        self.assertIn("5,2", cells)       # the gold lock
        self.assertNotIn("9,1", cells)    # the far orb
        self.assertNotIn("10,1", cells)   # the portal

    def test_peeping_opens_no_way_through(self):
        p = self.r["peepOnly"]
        last = p[-1]
        # Still on the peep-hole side, next room never entered,
        # nothing collected, the lock still drawn in the grid.
        self.assertEqual(last["pos"], {"x": 5, "y": 4})
        self.assertFalse(last["entered"])
        self.assertEqual(last["orbs"], 1)
        self.assertIn("L", last["row2"])

    def test_restart_restores_hole_and_black_room(self):
        self.assertFalse(self.r["fresh"]["active"])
        self.assertFalse(self.r["fresh"]["entered"])
        self.assertIn("L", self.r["fresh"]["row2"])

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    # --- YAML cases blocked by unbuilt mechanics: explicit skips ---
    @unittest.skip("blocked-by: 4 (one-way door) — the full YAML "
                   "check enters through a one-way door; the "
                   "teaching room uses a passable stand-in door and "
                   "the preview-then-enter path runs above")
    def test_yaml_solution_preview_then_choose_to_enter(self):
        pass

    @unittest.skip("blocked-by: 4, 48 (one-way door, checkpoint) — "
                   "committing past the enemy the pan did not reach "
                   "and returning to the checkpoint needs both "
                   "mechanics; the naive no-key block runs above")
    def test_yaml_adversarial_commit_on_partial_preview(self):
        pass

    @unittest.skip("blocked-by: 4 (one-way door) — the YAML boundary "
                   "wording is framed on entering through the "
                   "one-way door; the 2000ms lock/timer boundary "
                   "itself runs above")
    def test_yaml_two_second_locked_boundary(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const log = [
  {t_ms:100,input:'right'},{t_ms:200,input:'right'},
  {t_ms:300,input:'right'},{t_ms:400,input:'right'},
  {t_ms:500,input:'up'},{t_ms:1500,input:'right'},
  {t_ms:2500,input:'up'},{t_ms:2600,input:'up'},
  {t_ms:2700,input:'up'},{t_ms:2800,input:'right'},
  {t_ms:2900,input:'right'},{t_ms:3000,input:'right'},
  {t_ms:3100,input:'right'},{t_ms:3200,input:'right'}];
let live = core.initialState(level, 'mech-60-peep-hole-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-60-peep-hole-room', log);
const replayed2 = core.replay(level, 'mech-60-peep-hole-room',
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
                         {"pos": {"x": 10, "y": 1}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 14)


if __name__ == "__main__":
    unittest.main()
