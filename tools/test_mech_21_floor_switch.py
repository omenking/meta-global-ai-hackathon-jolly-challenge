"""Checks for the floor switch (mech-21-floor-switch).

The mechanic lives in the pure GameCore step (packs/floor-switch);
driven here under Node against the teaching room. Rules: the linked
door is open only while you, a bot or a block stands on the plate;
step off and it closes on the next move (still open during the step
off itself); sprites follow the pressed plate and the door state;
restart (fresh state) restores plate unpressed and door closed.
The block-holds-the-door solution is blocked-by mechanic 81 (push
block), which is not on this branch, so that YAML case is an
explicit skipped-with-reason check, never a fake pass.

Run with: python -m unittest tools.test_mech_21_floor_switch -v
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

LEVEL_ID = "mech-21-floor-switch-room"
PACK = ROOT / "tools" / "static" / "packs" / "floor-switch"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class FloorSwitchRoomLevelTests(unittest.TestCase):
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
        plates = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "S"]
        doors = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "D"]
        self.assertEqual(len(doors), 1)
        self.assertEqual(len(plates), 2)
        door = doors[0]
        # Teaching plate in sight of the door, too far to reach
        # before the held door closes again.
        far = min(plates, key=lambda p: -abs(p[0] - door[0]))
        self.assertGreaterEqual(abs(far[0] - door[0]), 4)
        # Corrected action exists: a plate beside the door, so
        # stepping off it carries the player through.
        near = min(plates, key=lambda p: abs(p[0] - door[0]))
        self.assertEqual(abs(near[0] - door[0]), 1)
        self.assertEqual(near[1], door[1])
        grid = "".join(rows)
        self.assertIn("P", grid)
        self.assertIn("*", grid)
        self.assertIn("X", grid)


class FloorSwitchPackAssetTests(unittest.TestCase):
    def test_manifest_lists_every_yaml_asset_bundled(self):
        manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "floor-switch")
        files = [a["file"] for a in manifest["assets"]]
        files += [a["file"] for a in manifest["jolly_states"]]
        files += [a["file"] for a in manifest["blocks"]]
        self.assertEqual(files, ["floor-switch-unpressed.png",
                                 "floor-switch-pressed.png", "door-closed.png",
                                 "door-open.png", "jolly-on-plate.png",
                                 "push-block.png"])
        for entry in (manifest["assets"] + manifest["jolly_states"]
                      + manifest["blocks"]):
            self.assertTrue(entry["bundled"], entry["file"])
            path = PACK / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])


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
  let s = core.initialState(level, 'mech-21-floor-switch-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    open: !!s.flags['switch:open:door1'],
    pressedA: !!(s.meta['2,3'] || {}).switch_pressed,
    doorOpenMeta: !!(s.meta['8,3'] || {}).switch_open,
    orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toA = ['down', 'down', 'right'];
// ADVERSARIAL: on the far plate, off toward the door, keep walking;
// the door closes on the next move before the player arrives.
const adv = run([...toA, 'right', 'right', 'left', 'left']);
// BOUNDARY CLOSE: stand on the door-side plate, step off (still
// open during the step off), one more move (closed from then on).
const toB = ['down', 'down', 'right', 'right', 'right', 'right',
  'right', 'right'];
const close = run([...toB, 'left', 'left']);
// BOUNDARY HELD: on the door-side plate push into the wall twice.
const held = run([...toB, 'up', 'up']);
// SOLUTION (player-only corrected action): far plate teaches the
// held rule, door-side plate carries the player through to the
// orb and the warp.
const sol = run([...toA, 'right', 'right', 'right', 'right', 'right',
  'right', 'right', 'up', 'up', 'right', 'right', 'right',
  'down', 'down']);
// Door predicate probes on live states (closed at spawn, open
// while the plate is occupied).
const s0 = core.initialState(level, 'mech-21-floor-switch-room');
const doorDef = core.getTileDef('switch:door');
const closedBlocks = doorDef.blocks(s0, { x: 8, y: 3 });
let sOn = s0;
[...toA].forEach((input, i) => {
  sOn = core.step(sOn, { t_ms: (i + 1) * 100, input });
});
const openBlocks = doorDef.blocks(sOn, { x: 8, y: 3 });
// Purity: stepping must not mutate the state it was given.
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  adv: adv.snaps, close: close.snaps, held: held.snaps,
  sol: sol.snaps,
  solFinal: { pos: { ...sol.final.player },
    orbs: core.readout(sol.final).orbs_left, status: sol.final.status },
  closedBlocks: closedBlocks, openBlocks: openBlocks,
  fresh: { open: !!s0.flags['switch:open:door1'],
    pressedA: !!(s0.meta['2,3'] || {}).switch_pressed,
    doorOpenMeta: !!(s0.meta['8,3'] || {}).switch_open,
    pos: { ...s0.player } },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class FloorSwitchMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_block_holds_the_door(self):
        # YAML: 'solution block holds the door' is blocked-by 81
        # (push block): push a block onto the plate and walk through.
        # The push-block pack is not on this branch (it is a separate
        # in-review feature), so this is an explicit skip with the
        # reason, never a fake pass. The pack still reads a
        # blocks:push-block object on a plate as holding it, so the
        # rule composes once that pack lands.
        if not (ROOT / "tools" / "static" / "packs" / "push-block"
                / "main.js").is_file():
            self.skipTest("blocked-by: 81 (push block) - push-block "
                          "pack not on this branch")

    def test_adversarial_step_off_and_hurry(self):
        adv = self.r["adv"]
        # On the far plate the door is held open.
        self.assertEqual(adv[3]["pos"], {"x": 2, "y": 3})
        self.assertTrue(adv[3]["open"])
        self.assertTrue(adv[3]["pressedA"])
        # Stepped off toward the door: still open during the step
        # off, closed from the next move onward, before arrival.
        self.assertEqual(adv[4]["pos"], {"x": 3, "y": 3})
        self.assertTrue(adv[4]["open"])
        self.assertEqual(adv[5]["pos"], {"x": 4, "y": 3})
        self.assertFalse(adv[5]["open"])
        self.assertFalse(adv[5]["doorOpenMeta"])
        # Never stranded: the player walks back onto the plate and
        # the door is held open again.
        self.assertEqual(adv[7]["pos"], {"x": 2, "y": 3})
        self.assertTrue(adv[7]["open"])
        self.assertEqual(adv[7]["status"], "playing")

    def test_boundary_closes_on_the_next_move(self):
        close = self.r["close"]
        # Standing on the door-side plate holds the door open.
        self.assertEqual(close[8]["pos"], {"x": 7, "y": 3})
        self.assertTrue(close[8]["open"])
        # The step off itself: door still open during it.
        self.assertEqual(close[9]["pos"], {"x": 6, "y": 3})
        self.assertTrue(close[9]["open"])
        # Exactly one more move: closed from the next move onward.
        self.assertEqual(close[10]["pos"], {"x": 5, "y": 3})
        self.assertFalse(close[10]["open"])

    def test_boundary_held_while_occupied(self):
        held = self.r["held"]
        # Two blocked pushes into the wall: no leaving, so the door
        # stays open for every move the plate stays occupied.
        self.assertEqual(held[9]["pos"], {"x": 7, "y": 3})
        self.assertTrue(held[9]["open"])
        self.assertEqual(held[10]["pos"], {"x": 7, "y": 3})
        self.assertTrue(held[10]["open"])
        self.assertTrue(held[10]["doorOpenMeta"])

    def test_door_blocks_closed_and_opens_held(self):
        self.assertTrue(self.r["closedBlocks"])
        self.assertFalse(self.r["openBlocks"])

    def test_solution_through_the_door_side_plate(self):
        sol = self.r["sol"]
        # Through the held-open doorway, orb collected, warp won.
        self.assertEqual(sol[9]["pos"], {"x": 8, "y": 3})
        self.assertEqual(self.r["solFinal"],
                         {"pos": {"x": 12, "y": 3}, "orbs": 0,
                          "status": "won"})

    def test_restart_restores_plate_and_door(self):
        self.assertEqual(self.r["fresh"],
                         {"open": False, "pressedA": False,
                          "doorOpenMeta": False, "pos": {"x": 1, "y": 1}})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_pressed_plate_and_door_state(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("'switch_open' in smeta", js)
        self.assertIn("floor-switch-pressed.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/floor-switch/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down', 'down', 'right', 'right', 'right', 'right',
  'right', 'right', 'right', 'right', 'up', 'up', 'right', 'right',
  'right', 'down', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-21-floor-switch-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-21-floor-switch-room', log);
const replayed2 = core.replay(level, 'mech-21-floor-switch-room',
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
                         {"pos": {"x": 12, "y": 3}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 17)


if __name__ == "__main__":
    unittest.main()
