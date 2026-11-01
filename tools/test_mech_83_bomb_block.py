"""Checks for the bomb block (mech-83-bomb-block).

The mechanic lives in the bomb-block pack (packs/bomb-block/main.js)
on top of the pure GameCore step; driven here under Node against the
teaching room. Rules: the bomb block slides only onto empty floor or
a switch plate exactly as a push block; water, deep water, void, fire
and lava block it; a push that would drive it into a wall explodes it
instead (that wall becomes floor, the bomb is consumed); locks,
closed gates and other blocks never crack. Restart (fresh state)
restores the bomb and every wall; a recorded session replays to the
same end state.

Run with: python -m unittest tools.test_mech_83_bomb_block -v
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

LEVEL_ID = "mech-83-bomb-block-room"


class BombRoomLevelTests(unittest.TestCase):
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
        # One player, one bomb block, one switch plate, one warp.
        self.assertEqual(grid.count("P"), 1)
        self.assertEqual(grid.count("B"), 1)
        self.assertEqual(grid.count("S"), 1)
        self.assertEqual(grid.count("X"), 1)
        # Two crackable walls face the bomb: rock wall and exit wall.
        walls = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "W"]
        self.assertEqual(len(walls), 2)
        (exit_x, exit_y), (rock_x, rock_y) = sorted(
            walls, key=lambda p: p[1])
        # The bomb starts aligned with the nearest (rock) wall, so the
        # naive eastward push spends it; the exit wall is rows away.
        bomb = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "B"][0]
        self.assertEqual(bomb[1], rock_y)
        self.assertNotEqual(bomb[1], exit_y)
        # Behind the rock wall is solid rock; behind the exit wall is
        # open floor leading to the warp.
        self.assertEqual(rows[rock_y][rock_x + 1], "#")
        self.assertEqual(rows[exit_y][exit_x + 1], ".")
        warp = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "X"][0]
        self.assertGreater(warp[0], exit_x)


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function bombs(s) {
  const out = [];
  s.grid.forEach((row, y) => { for (let x = 0; x < row.length; x++)
    if (row[x] === 'B') out.push([x, y]); });
  return out;
}
function snap(s) {
  return { pos: { ...s.player }, status: s.status, bombs: bombs(s),
    row3: s.grid[3], row5: s.grid[5] };
}
function run(seq, lvl, name) {
  let s = core.initialState(lvl || level, name || 'mech-83-bomb-block-room');
  const snaps = [snap(s)];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap(s));
  });
  return { snaps, final: s };
}
// Solution: push the bomb north to the exit-wall row, east over the
// switch plate, explode the exit wall and walk out to the warp.
const sol = run(['down', 'right', 'right', 'up', 'up', 'left', 'up',
  'right', 'right', 'right', 'right', 'right', 'right', 'right',
  'right', 'up', 'right']);
// Adversarial: the naive eastward push along the bomb's own row
// spends it on the rock wall; the player is left free, not stranded.
const adv = run(['right', 'right', 'right', 'right', 'right',
  'right', 'right', 'left']);
// Synthetic one-push rooms for the blocker/hazard cases.
const LEGEND = {
  '.': {label: 'floor', sprite: 'floor_default.png'},
  '#': {label: 'wall', sprite: 'wall.png'},
  'P': {base: 'floor_default.png', label: 'player', sprite: 'jolly.png'},
  'B': {base: 'floor_default.png', label: 'bomb block', def: 'bomb:bomb-block'},
  'W': {base: 'floor-after-blast.png', label: 'cracked wall', def: 'bomb:cracked-wall'},
  'S': {base: 'floor_default.png', label: 'switch plate', def: 'bomb:switch-plate'},
  'K': {base: 'floor_default.png', label: 'crate', def: 'bomb:crate'},
  'L': {label: 'red lock', lock_color: 'red'},
  'G': {base: 'floor_default.png', label: 'gate', sprite: 'gate.png'},
  '*': {base: 'floor_default.png', label: 'chip', sprite: 'orb.png'},
  '~': {base: 'floor_default.png', label: 'water', def: 'water:water'},
  'D': {base: 'floor_default.png', label: 'deep water', def: 'bomb:deep-water'},
  'V': {base: 'floor_default.png', label: 'void', def: 'crumble:void'},
  'F': {base: 'floor_default.png', label: 'fire', def: 'bomb:fire'},
  'A': {base: 'floor_default.png', label: 'lava', def: 'bomb:lava'},
};
function mini(midRow) {
  return { name: 'mini', time_limit: 120, test: true, legend: LEGEND,
    rows: ['#####', midRow, '#####'] };
}
function pushCase(midRow) {
  const r = run(['right'], mini(midRow), 'mini');
  const f = r.snaps[1];
  return { pos: f.pos, bombs: f.bombs, status: f.status,
    row: r.final.grid[1], orbs: core.readout(r.final).orbs_left };
}
const cases = {};
for (const t of ['L', 'K', 'B', '~', 'D', 'V', 'F', 'A', '#', 'W', '.', 'S']) {
  cases[t] = pushCase('#PB' + t + '#');
}
// Closed gate: an uncollected orb elsewhere keeps the gate shut.
cases['G'] = pushCase('#PBG*#');
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-83-bomb-block-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, adv: adv.snaps, cases: cases,
  freshRow3: core.initialState(level,
    'mech-83-bomb-block-room').grid[3],
  freshRow5: core.initialState(level,
    'mech-83-bomb-block-room').grid[5],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class BombMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_cracks_the_exit_wall_and_walks_out(self):
        sol = self.r["sol"]
        # The bomb slides north, then east over the switch plate.
        self.assertEqual(sol[5]["bombs"], [[5, 3]])
        self.assertEqual(sol[9]["bombs"], [[7, 3]])
        # The fifth eastward push explodes it on the exit wall:
        # wall becomes floor, bomb consumed, player follows through.
        self.assertEqual(sol[12]["pos"], {"x": 9, "y": 3})
        self.assertEqual(sol[12]["bombs"], [])
        self.assertEqual(sol[12]["row3"], "#......S.......#")
        self.assertEqual(sol[-1]["pos"], {"x": 13, "y": 2})
        self.assertEqual(sol[-1]["status"], "won")

    def test_adversarial_spend_it_on_solid_rock(self):
        adv = self.r["adv"]
        # Sixth input drives the bomb into the rock wall: it is
        # spent, the cracked cell is floor, solid rock behind it.
        self.assertEqual(adv[6]["pos"], {"x": 9, "y": 5})
        self.assertEqual(adv[6]["bombs"], [])
        self.assertEqual(adv[6]["row5"], "#..P.......#####")
        self.assertEqual(adv[6]["status"], "playing")
        # Never stranded: the player walks into the alcove and back.
        self.assertEqual(adv[7]["pos"], {"x": 10, "y": 5})
        self.assertEqual(adv[8]["pos"], {"x": 9, "y": 5})
        self.assertEqual(adv[8]["status"], "playing")

    def test_only_walls_crack(self):
        self.assertEqual(self.r["cases"]["G"]["orbs"], 1)
        for target in ("L", "G", "K"):
            case = self.r["cases"][target]
            self.assertEqual(case["pos"], {"x": 1, "y": 1}, target)
            self.assertEqual(case["bombs"], [[2, 1]], target)
            self.assertEqual(case["status"], "playing", target)
        # Another bomb block blocks too: neither bomb moves or blows.
        case = self.r["cases"]["B"]
        self.assertEqual(case["pos"], {"x": 1, "y": 1})
        self.assertEqual(case["bombs"], [[2, 1], [3, 1]])
        # A plain wall and a cracked wall both explode to floor.
        for target in ("#", "W"):
            case = self.r["cases"][target]
            self.assertEqual(case["bombs"], [], target)
            self.assertEqual(case["row"], "#P..#", target)
            self.assertEqual(case["pos"], {"x": 2, "y": 1}, target)

    def test_hazards_block_the_bomb_block(self):
        for target in ("~", "D", "V", "F", "A"):
            case = self.r["cases"][target]
            self.assertEqual(case["pos"], {"x": 1, "y": 1}, target)
            self.assertEqual(case["bombs"], [[2, 1]], target)
            self.assertEqual(case["row"][3], target, target)
            self.assertEqual(case["status"], "playing", target)

    def test_slides_onto_floor_and_switch_plate_only(self):
        floor = self.r["cases"]["."]
        self.assertEqual(floor["bombs"], [[3, 1]])
        self.assertEqual(floor["pos"], {"x": 2, "y": 1})
        plate = self.r["cases"]["S"]
        self.assertEqual(plate["bombs"], [[3, 1]])
        self.assertEqual(plate["pos"], {"x": 2, "y": 1})

    def test_restart_restores_bomb_and_walls(self):
        self.assertEqual(self.r["freshRow3"], "#......S..W....#")
        self.assertEqual(self.r["freshRow5"], "#..P.B....W#####")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_assets_are_bundled_and_wired(self):
        pack = ROOT / "tools" / "static" / "packs" / "bomb-block"
        manifest = json.loads(
            (pack / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "bomb-block")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["cracked-wall.png", "floor-after-blast.png",
                          "bomb-block.png", "bomb-block-exploding.png"])
        for entry in bundled:
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            import struct
            self.assertEqual(struct.unpack(">II", data[16:24]),
                             (512, 512), entry["file"])
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'B'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/bomb-block/main.js", html)


if __name__ == "__main__":
    unittest.main()
