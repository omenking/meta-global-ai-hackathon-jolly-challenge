"""Checks for the weight switch (mech-29-weight-switch).

The mechanic lives in the pure GameCore step (packs/weight-switch);
driven here under Node against the teaching room. Rules: the linked
door is open only while a block sits on the plate, or while the
player stands on it; stepping off closes it, so the player alone
cannot leave it held; restart (fresh state) restores the plate
empty and the door closed.

YAML test_cases coverage (switches-and-doors.yml mechanic 29):
- solution leave a block on the plate: blocked-by 81 (push block),
  an explicit skip below, never a fake pass; the door rule itself is
  verified with a block placed on the plate at state level.
- adversarial stand and step off: real end-to-end check.
- boundary removing the block closes it: blocked-by 81, skip below.
- boundary player holds only while present: real end-to-end check.
- restart and replay: fresh-state check here; replay digest in
  SanityReplayTests.

Run with: python -m unittest tools.test_mech_29_weight_switch -v
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

LEVEL_ID = "mech-29-weight-switch-room"
PACK = ROOT / "tools" / "static" / "packs" / "weight-switch"

YAML_ASSETS = ["weight-switch-empty.png", "weight-switch-weighted.png",
               "door-closed.png", "door-open.png",
               "jolly-on-weight-switch.png", "push-block.png",
               "heavy-block.png"]


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class WeightRoomLevelTests(unittest.TestCase):
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
        self.assertIn("W", grid)  # weight plate
        self.assertIn("E", grid)  # linked door
        self.assertIn("B", grid)  # block in the room
        top = rows[1]
        plate_x, door_x = top.index("W"), top.index("E")
        # Two floor tiles between plate and door: stepping off the
        # plate closes the door before the player can reach it.
        self.assertEqual(top[plate_x + 1:door_x], "..")
        beyond = top[door_x + 1:]
        self.assertIn("*", beyond)  # orb beyond the door
        self.assertIn("X", beyond)  # warp beyond the door


class PackAssetTests(unittest.TestCase):
    def test_manifest_lists_every_yaml_asset_bundled(self):
        manifest = json.loads((PACK / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "weight-switch")
        self.assertEqual(manifest["main"], "main.js")
        bundled = [a["file"] for a in manifest["assets"] if a["bundled"]]
        self.assertEqual(bundled, YAML_ASSETS)

    def test_bundled_asset_files_exist_at_512(self):
        for name in YAML_ASSETS:
            path = PACK / "assets" / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(_png_size(path), (512, 512), name)

    def test_pack_declares_assets_and_tiles(self):
        js = (PACK / "main.js").read_text(encoding="utf-8")
        for name in YAML_ASSETS:
            self.assertIn(name, js)
        self.assertIn("weight:plate", js)
        self.assertIn("weight:door", js)
        self.assertIn("weight:block", js)


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const DOOR = { x: 8, y: 1 };
function doorOpen(s) {
  const p = s.actors.find((a) => a.id === 'player');
  return core.kernel.canEnter(s, p, DOOR.x, DOOR.y);
}
function run(seq) {
  let s = core.initialState(level, 'mech-29-weight-switch-room');
  const snap = () => ({ pos: { ...s.player }, door: doorOpen(s),
    status: s.status });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toPlate = ['right', 'right', 'right', 'right'];
// Adversarial: stand on the plate, step off toward the door, hurry.
const a = run([...toPlate, 'right', 'right', 'right', 'left', 'left']);
// Boundary: hold the plate pushing into the wall, then step off.
const b = run([...toPlate, 'up', 'up', 'right']);
// Placed-block hold: a block already on the plate (pushing it there
// is mechanic 81) holds the door while the player walks away,
// around and through it to the warp.
let placed = core.initialState(level, 'mech-29-weight-switch-room');
placed.objects[1][5] = 'weight:block';
const placedDoorAtStart = doorOpen(placed);
let s = placed;
const route = ['right', 'right', 'right', 'down', 'right', 'right',
  'right', 'up', 'right', 'right', 'right', 'right'];
const placedSnaps = [{ pos: { ...s.player }, door: doorOpen(s) }];
route.forEach((input, i) => {
  s = core.step(s, { t_ms: (i + 1) * 100, input });
  placedSnaps.push({ pos: { ...s.player }, door: doorOpen(s),
    status: s.status });
});
let removed = core.initialState(level, 'mech-29-weight-switch-room');
removed.objects[1][5] = 'weight:block';
const withBlock = doorOpen(removed);
removed.objects[1][5] = null;
const withoutBlock = doorOpen(removed);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-29-weight-switch-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, placedSnaps,
  placedFinal: { pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left },
  placedDoorAtStart, withBlock, withoutBlock,
  fresh: { pos: { ...core.initialState(level,
      'mech-29-weight-switch-room').player },
    door: doorOpen(core.initialState(level,
      'mech-29-weight-switch-room')),
    row: core.initialState(level,
      'mech-29-weight-switch-room').grid[1] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class WeightMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_adversarial_stand_and_step_off(self):
        a = self.r["a"]
        # Standing on the plate (5,1) opens the door.
        self.assertEqual(a[4]["pos"], {"x": 5, "y": 1})
        self.assertTrue(a[4]["door"])
        # Stepping off closes it before the player arrives; the
        # hurried step into the doorway is blocked, never stranded.
        self.assertEqual(a[5]["pos"], {"x": 6, "y": 1})
        self.assertFalse(a[5]["door"])
        self.assertEqual(a[7]["pos"], {"x": 7, "y": 1})
        self.assertEqual(a[7]["status"], "playing")
        # Returning to the plate reopens it.
        self.assertEqual(a[9]["pos"], {"x": 5, "y": 1})
        self.assertTrue(a[9]["door"])

    def test_boundary_player_holds_only_while_present(self):
        b = self.r["b"]
        # Two blocked pushes into the wall: still on the plate, the
        # door stays open for every occupied move.
        self.assertEqual(b[5]["pos"], {"x": 5, "y": 1})
        self.assertTrue(b[5]["door"])
        self.assertEqual(b[6]["pos"], {"x": 5, "y": 1})
        self.assertTrue(b[6]["door"])
        # Stepping off ends the hold at once: no lasting hold from
        # the player alone.
        self.assertEqual(b[7]["pos"], {"x": 6, "y": 1})
        self.assertFalse(b[7]["door"])

    def test_block_on_plate_holds_door_while_player_walks_through(self):
        # Door rule with a block placed on the plate (the push itself
        # is mechanic 81): open from the start, open while the player
        # walks away and around, and the player exits through it.
        self.assertTrue(self.r["placedDoorAtStart"])
        self.assertTrue(all(snap["door"]
                            for snap in self.r["placedSnaps"]))
        self.assertEqual(self.r["placedFinal"],
                         {"pos": {"x": 11, "y": 1},
                          "status": "won", "orbs": 0})

    def test_removing_block_closes_door_at_state_level(self):
        self.assertTrue(self.r["withBlock"])
        self.assertFalse(self.r["withoutBlock"])

    @unittest.skip("blocked-by: 81 (push block): pushing a block onto "
                   "the plate is not built on main; the door rule for "
                   "a block on the plate is covered at state level by "
                   "test_block_on_plate_holds_door_while_player_walks_through")
    def test_solution_leave_a_block_on_the_plate(self):
        pass

    @unittest.skip("blocked-by: 81 (push block): pushing a block off "
                   "the plate is not built on main; removal closing "
                   "the door is covered at state level by "
                   "test_removing_block_closes_door_at_state_level")
    def test_boundary_removing_the_block_closes_it(self):
        pass

    def test_restart_restores_plate_empty_and_door_closed(self):
        fresh = self.r["fresh"]
        self.assertEqual(fresh["pos"], {"x": 1, "y": 1})
        self.assertFalse(fresh["door"])
        self.assertEqual(fresh["row"], "#P...W..E.*X#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_the_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'E' || dt.ch === 'W'", js)
        self.assertIn("door-open.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/weight-switch/main.js", html)
        core = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("packs/weight-switch/main.js", core)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'right', 'up', 'up',
  'right', 'right', 'right', 'left', 'left'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-29-weight-switch-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-29-weight-switch-room', log);
const replayed2 = core.replay(level, 'mech-29-weight-switch-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left },
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
        # Hold the plate, hurry at the closed door, return to it.
        self.assertEqual(self.r["liveFinal"],
                         {"pos": {"x": 5, "y": 1}, "orbs": 1})
        self.assertEqual(self.r["replaySteps"], 11)


if __name__ == "__main__":
    unittest.main()
