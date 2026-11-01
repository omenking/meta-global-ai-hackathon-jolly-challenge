"""Checks for the mirror block (mech-84-mirror-block).

The mechanic lives in packs/mirror-block: pushed one tile onto
empty floor or a switch plate only; hazards/walls/blocks/enemies
block the push; an enemy moving into it reverses instead of
passing. YAML cases blocked-by unbuilt mechanics (31 patroller,
37 guard, 21 floor switch) are explicit skips below, never fake
passes; separate local tests prove the same rules with this
pack's own patroller controller. Restart/replay is not blocked.

Run with: python -m unittest tools.test_mech_84_mirror_block -v
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

LEVEL_ID = "mech-84-mirror-block-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class MirrorRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("M"), 1)
        self.assertEqual(grid.count("E"), 1)
        mirror = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "M"]
        enemy = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "E"]
        # Mirror starts exactly one tile off the patroller lane.
        self.assertEqual(mirror, [(5, 4)])
        self.assertEqual(enemy, [(1, 3)])
        self.assertEqual(mirror[0][1] - enemy[0][1], 1)
        self.assertGreaterEqual(grid.count("*"), 1)


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq, lvl, name) {
  let s = core.initialState(lvl || level, name || 'mech-84-mirror-block-room');
  const info = () => ({ pos: { ...s.player },
    enemies: s.actors.filter((a) => a.id !== 'player')
      .map((a) => ({ x: a.x, y: a.y, dir: (a.flags || {}).dir })),
    grid: s.grid.slice(), status: s.status,
    orbs: core.readout(s).orbs_left });
  const snaps = [info()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input }); snaps.push(info());
  });
  return { snaps, final: s };
}
const L = (rows, extra) => Object.assign({ name: 'synth', test: true,
  time_limit: 120, legend: {
    '.': { label: 'floor' }, '#': { label: 'wall' },
    'P': { label: 'player' }, '*': { label: 'orb' },
    'M': { def: 'mirror:mirror-block' }, 'E': { actor: 'mirror:patroller' },
    's': { def: 'mirror:switch' }, '~': { def: 'mirror:water' },
    'w': { def: 'mirror:deep-water' }, 'v': { def: 'mirror:void' },
    'f': { def: 'mirror:fire' }, 'l': { def: 'mirror:lava' },
    'B': { def: 'mirror:mirror-block' } }, rows }, extra || {});
// Push onto floor (right), then onto switch plate is a fresh room.
const pushFloor = run(['right'], L(['#####', '#PM.#', '#####']), 'synth');
// Player at (1,1) pushes M right onto floor at (3,1).
const pushSwitch = run(['right'], L(['#####', '#PMs#', '#####']), 'synth');
const blockedWall = run(['right'], L(['#####', '#PM##', '#####']), 'synth');
const blockedHazard = {};
for (const [k, ch] of Object.entries({ water: '~', deep: 'w', void: 'v', fire: 'f', lava: 'l' })) {
  blockedHazard[k] = run(['right'], L(['#####', '#PM' + ch + '#', '#####']), 'synth');
}
const blockedBlock = run(['right'], L(['######', '#PMB.#', '######']), 'synth');
// Enemy reversal: patroller walks right into the mirror, turns, walks back.
const reversal = run(['up', 'up', 'up', 'up', 'up', 'up'],
  L(['########', '#P.....#', '#..E.M.#', '########']), 'synth');
// Teaching room waits: patroller crosses the whole lane unbent.
const waits = run(Array(16).fill('up'));
// Solution: cross at x=9, step below the mirror, push it up into
// the lane, retreat below, then wait against the bottom wall.
const solSeq = ['up','up','up','up',
  'right','right','right','right','right','right','right','right',
  'down','down','down','down','left','left','left','left','up','down','down'];
const solution = run([...solSeq, ...Array(14).fill('down')]);
const s0 = core.initialState(level, 'mech-84-mirror-block-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ pushFloor: pushFloor.snaps,
  pushSwitch: pushSwitch.snaps, blockedWall: blockedWall.snaps,
  blockedHazard: Object.fromEntries(Object.entries(blockedHazard)
    .map(([k, v]) => [k, v.snaps])),
  blockedBlock: blockedBlock.snaps, reversal: reversal.snaps,
  waits: waits.snaps, solution: solution.snaps,
  fresh: core.initialState(level, 'mech-84-mirror-block-room').grid,
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MirrorLocalMechanicTests(unittest.TestCase):
    """Local (non-YAML) proofs using this pack's own controllers."""

    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_push_onto_empty_floor_moves_one_tile(self):
        snaps = self.r["pushFloor"]
        self.assertEqual(snaps[1]["pos"], {"x": 2, "y": 1})
        self.assertEqual(snaps[1]["grid"][1], "#P.M#")

    def test_push_onto_switch_plate(self):
        self.assertEqual(self.r["pushSwitch"][1]["grid"][1], "#P.M#")
        self.assertEqual(self.r["pushSwitch"][1]["pos"], {"x": 2, "y": 1})

    def test_blocked_pushes_stay_put(self):
        self.assertEqual(self.r["blockedWall"][1]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["blockedWall"][1]["grid"][1], "#PM##")
        for name, snaps in self.r["blockedHazard"].items():
            self.assertEqual(snaps[1]["pos"], {"x": 1, "y": 1}, name)
            self.assertTrue(snaps[1]["grid"][1].startswith("#PM"), name)
        self.assertEqual(self.r["blockedBlock"][1]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["blockedBlock"][1]["grid"][1], "#PMM.#")

    def test_enemy_reverses_never_passes(self):
        snaps = self.r["reversal"]
        xs = [s["enemies"][0]["x"] for s in snaps]
        # Approaches the mirror, never enters/passes x=5, comes back.
        self.assertEqual(max(xs), 4)
        self.assertNotIn(5, xs)
        self.assertEqual(snaps[2]["enemies"][0]["dir"], "left")
        self.assertLess(xs[2], xs[1])

    def test_patroller_crosses_whole_lane_without_mirror(self):
        xs = [s["enemies"][0]["x"] for s in self.r["waits"]]
        self.assertEqual(max(xs), 13)

    def test_pushed_mirror_confines_the_loop(self):
        snaps = self.r["solution"]
        self.assertEqual(snaps[21]["grid"][3][5], "M")
        after = snaps[-8:]
        self.assertTrue(all(s["enemies"][0]["x"] <= 4 for s in after))
        self.assertEqual(snaps[-1]["status"], "playing")

    def test_restart_restores_block_and_loop(self):
        self.assertEqual(self.r["fresh"][4], "#....M........#")
        self.assertEqual(self.r["fresh"][3], "#.............#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wiring_renders_mirror_and_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/mirror-block/main.js", html)
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("dt.ch === 'M'", js)


class MirrorYamlBlockedTests(unittest.TestCase):
    """Every YAML test_cases entry for mechanic 84, by name."""

    @unittest.skip("blocked-by: 31 (patroller) - patroller mechanic not built as its own feature; local reversal proof in MirrorLocalMechanicTests")
    def test_solution_bend_the_patroller_away(self):
        pass

    @unittest.skip("blocked-by: 31 (patroller) - patroller mechanic not built as its own feature; local confinement proof in MirrorLocalMechanicTests")
    def test_adversarial_mirror_left_off_the_spot(self):
        pass

    @unittest.skip("blocked-by: 31, 37 (patroller, guard) - enemy mechanics not built as their own features; local reversal proof in MirrorLocalMechanicTests")
    def test_enemy_reverses_never_passes(self):
        pass

    @unittest.skip("blocked-by: 21 (floor switch) - floor switch mechanic not built; local switch-plate proof in MirrorLocalMechanicTests")
    def test_push_rules_match_the_push_block(self):
        pass


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['up','up','up','up',
  'right','right','right','right','right','right','right','right',
  'down','down','down','down','left','left','left','left','up','down','down',
  'down','down','down','down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-84-mirror-block-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-84-mirror-block-room', log);
const replayed2 = core.replay(level, 'mech-84-mirror-block-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1, row3: replayed[replayed.length - 1].grid[3],
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
        self.assertEqual(self.r["liveFinal"]["pos"], {"x": 5, "y": 6})
        self.assertEqual(self.r["row3"][5], "M")
        self.assertEqual(self.r["replaySteps"], 27)


if __name__ == "__main__":
    unittest.main()
