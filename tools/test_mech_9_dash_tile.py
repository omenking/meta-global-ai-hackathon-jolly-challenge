"""Checks for the dash tile (mech-9-dash-tile).

The mechanic lives in the pure GameCore step (packs/dash-tile);
driven here under Node against the teaching room. Rules: stepping
on the tile stores one dash (HUD charge item); moving in the same
direction twice in a row spends it, the second step travelling two
tiles and clearing a one-tile gap; changing direction keeps the
charge; restart (fresh state) clears the charge and restores the
tile. Covers every test_cases entry in movement-tiles.yml #9: no
entry is blocked-by another mechanic, so nothing is skipped.

Run with: python -m unittest tools.test_mech_9_dash_tile -v
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

LEVEL_ID = "mech-9-dash-tile-room"


class DashRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("D"), 1)
        self.assertEqual(grid.count("V"), 1)
        d = [(x, y) for y, r in enumerate(rows)
             for x, ch in enumerate(r) if ch == "D"][0]
        # Dash tile on the straight corridor, far wall two tiles east.
        self.assertEqual(rows[d[1]][d[0] + 1], ".")
        self.assertEqual(rows[d[1]][d[0] + 2], "#")
        # One-tile gap with floor, orb and warp beyond it.
        v = [(x, y) for y, r in enumerate(rows)
             for x, ch in enumerate(r) if ch == "V"][0]
        self.assertEqual(rows[v[1]][v[0] + 1], ".")
        self.assertIn("*", rows[v[1]][v[0] + 1:])
        self.assertIn("X", rows[v[1]][v[0] + 1:])


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function runOn(lvl, name, seq) {
  let s = core.initialState(lvl, name);
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    inv: core.readout(s).inventory,
    orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const run = (seq) => runOn(level, 'mech-9-dash-tile-room', seq);
// Solution: charge, zigzag to keep it, east+east dashes the gap.
const solution = ['right', 'right', 'right', 'down', 'right', 'down',
  'right', 'right', 'right', 'right'];
const a = run(solution);
// Adversarial: habit spends the dash into the far wall, then the
// room resolves by returning to the dash tile and playing correctly.
const b = run(['right', 'right', 'right', 'right',
  'left', 'down', 'right', 'down', 'right', 'right', 'right', 'right']);
// Uncharged walk into the gap after the wall spend falls.
const c = run(['right', 'right', 'right', 'right',
  'down', 'down', 'right', 'right']);
// Synthetic vertical rooms: one-tile gap clears, two-tile does not.
const legend = level.legend;
const oneGap = { ...level, rows: ['#######', '#P.D###', '###.###',
  '###V###', '###.###', '###X###', '#######'] };
const twoGap = { ...level, rows: ['#######', '#P.D###', '###.###',
  '###V###', '###V###', '###.###', '###X###', '#######'] };
const d = runOn(oneGap, 'synthetic-one-gap',
  ['right', 'right', 'down', 'down', 'down']);
const e = runOn(twoGap, 'synthetic-two-gap',
  ['right', 'right', 'down', 'down']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-9-dash-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a, b, c, d, e,
  fresh: { pos: { ...s0.player }, inv: core.readout(
    core.initialState(level, 'mech-9-dash-tile-room')).inventory,
    row: core.initialState(level, 'mech-9-dash-tile-room').grid[1] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class DashMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_save_the_dash_for_the_gap(self):
        a = self.r["a"]
        # Stepping on the tile stores one dash, shown as HUD charge.
        self.assertEqual(a[3]["pos"], {"x": 4, "y": 1})
        self.assertEqual(a[3]["inv"], ["dash"])
        # Zigzag changes direction and keeps the charge to the lane.
        self.assertEqual(a[7]["pos"], {"x": 6, "y": 3})
        self.assertEqual(a[7]["inv"], ["dash"])
        # Second east step dashes two tiles over the gap onto floor.
        self.assertEqual(a[8]["pos"], {"x": 8, "y": 3})
        self.assertEqual(a[8]["inv"], [])
        self.assertEqual(a[8]["status"], "playing")
        self.assertEqual(a[10]["pos"], {"x": 10, "y": 3})
        self.assertEqual(a[10]["status"], "won")
        self.assertEqual(a[10]["orbs"], 0)

    def test_adversarial_habit_spends_the_dash(self):
        b = self.r["b"]
        # Keeping east out of habit dashes into the far wall: the
        # player stops one tile on, charge spent, nothing stranded.
        self.assertEqual(b[4]["pos"], {"x": 5, "y": 1})
        self.assertEqual(b[4]["inv"], [])
        self.assertEqual(b[4]["status"], "playing")
        # Returning west re-arms on the dash tile and the corrected
        # zigzag then completes the room.
        self.assertEqual(b[5]["pos"], {"x": 4, "y": 1})
        self.assertEqual(b[5]["inv"], ["dash"])
        self.assertEqual(b[-1]["pos"], {"x": 10, "y": 3})
        self.assertEqual(b[-1]["status"], "won")

    def test_uncharged_gap_entry_falls(self):
        c = self.r["c"]
        self.assertEqual(c[-1]["pos"], {"x": 7, "y": 3})
        self.assertEqual(c[-1]["status"], "lost")

    def test_repeat_spends_change_keeps(self):
        a = self.r["a"]
        # Four direction changes in a row never spend the charge.
        for snap in a[4:8]:
            self.assertEqual(snap["inv"], ["dash"])
        # The first repeated direction spends it (snap 8, solution
        # test); the next east step is a normal one tile, proving no
        # second dash remains.
        self.assertEqual(a[9]["pos"], {"x": 9, "y": 3})
        self.assertEqual(a[9]["inv"], [])

    def test_clears_exactly_one_tile(self):
        d, e = self.r["d"], self.r["e"]
        # One-tile gap: dash lands beyond it and wins at the warp.
        self.assertEqual(d[4]["pos"], {"x": 3, "y": 4})
        self.assertEqual(d[4]["status"], "playing")
        self.assertEqual(d[5]["status"], "won")
        # Two-tile gap: the dash lands in the second gap tile, lost.
        self.assertEqual(e[4]["pos"], {"x": 3, "y": 4})
        self.assertEqual(e[4]["status"], "lost")

    def test_restart_restores_tile_and_clears_charge(self):
        self.assertEqual(self.r["fresh"]["pos"], {"x": 1, "y": 1})
        self.assertEqual(self.r["fresh"]["inv"], [])
        self.assertEqual(self.r["fresh"]["row"], "#P..D.#######")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_dash_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dash-tile-spent.png", js)
        self.assertIn("jolly-dashing.png", js)
        self.assertIn("dash-charge.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/dash-tile/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'down', 'right', 'down',
  'right', 'right', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-9-dash-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-9-dash-tile-room', log);
const replayed2 = core.replay(level, 'mech-9-dash-tile-room',
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
                         {"pos": {"x": 10, "y": 3}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 10)


if __name__ == "__main__":
    unittest.main()
