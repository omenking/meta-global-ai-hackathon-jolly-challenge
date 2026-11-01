"""Checks for the move door (mech-79-move-door).

The mechanic lives in the pure GameCore step (packs/movedoor);
driven here under Node against the teaching room. Rules: a move
counter shows in the HUD; the door opens permanently on your 50th
move input of the attempt and stays open after it. Every move
input counts, including blocked attempts and detours, because the
kernel counts each step input in state.steps. Restart (fresh
state) restores the closed door and a zero counter.

Run with: python -m unittest tools.test_mech_79_move_door -v
"""
import json
import shutil
import struct
import subprocess
import sys
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402

LEVEL_ID = "mech-79-move-door-room"
DOOR = (6, 7)
BESIDE_DOOR = (7, 7)


def _bfs(rows, target):
    start = next((x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "P")
    dist = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        if (x, y) == target:
            return dist[(x, y)]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in dist or rows[ny][nx] == "#":
                continue
            dist[(nx, ny)] = dist[(x, y)] + 1
            queue.append((nx, ny))
    return None


class MoveDoorRoomLevelTests(unittest.TestCase):
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
        # An orb and the warp exit lie beyond the door.
        door_x, door_y = DOOR
        self.assertEqual(rows[door_y][door_x], "D")
        beyond = rows[door_y][:door_x]
        self.assertIn("*", beyond)
        self.assertIn("X", beyond)
        # The efficient route stands beside the door in the low
        # forties, and even walking straight through to the warp
        # totals 49 moves: the door cannot open on efficiency
        # alone, so the room teaches spending moves, and the whole
        # serpentine corridor stays revisitable for pacing (the
        # player is never stranded by a closed door).
        self.assertEqual(_bfs(rows, BESIDE_DOOR), 44)
        self.assertEqual(_bfs(rows, (2, 7)), 49)


class MoveDoorPackTests(unittest.TestCase):
    def test_manifest_mirrors_the_yaml_assets(self):
        pack = ROOT / "tools" / "static" / "packs" / "movedoor"
        manifest = json.loads((pack / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "movedoor")
        entries = (manifest["assets"] + manifest["jolly_states"]
                   + manifest["gui"] + manifest["blocks"])
        self.assertEqual(
            {e["file"]: e["kind"] for e in entries},
            {"move-door-closed.png": "tiles",
             "move-door-open.png": "tiles",
             "move-counter.png": "gui"})
        for entry in entries:
            self.assertTrue(entry["bundled"], entry["file"])
            self.assertTrue(entry["shows"], entry["file"])
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]),
                             (512, 512), entry["file"])

    def test_main_declares_every_manifest_asset(self):
        pack = ROOT / "tools" / "static" / "packs" / "movedoor"
        manifest = json.loads((pack / "manifest.json").read_text(
            encoding="utf-8"))
        js = (pack / "main.js").read_text(encoding="utf-8")
        for entry in (manifest["assets"] + manifest["jolly_states"]
                      + manifest["gui"] + manifest["blocks"]):
            self.assertIn(entry["file"], js)
            self.assertIn("movedoor:door", js)


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
  let s = core.initialState(level, 'mech-79-move-door-room');
  const snap = () => ({ pos: { ...s.player }, steps: s.steps,
    moves: s.counters['movedoor:moves'],
    open: !!((s.meta['6,7'] || {}).move_open),
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const E = [...Array(11).fill('right'), 'down', 'down',
  ...Array(11).fill('left'), 'down', 'down',
  ...Array(11).fill('right'), 'down', 'down',
  ...Array(5).fill('left')];
// A solution: efficient 44, five spent moves, the 50th input is
// the step through the door, then orb and warp.
const a = run([...E, 'right', 'left', 'left', 'right',
  'left', 'left', 'left', 'left', 'left', 'left']);
// B adversarial: efficient arrival, a naive push at the closed
// door, then pacing and through.
const b = run([...E, 'left', 'right', 'left', 'right',
  'left', 'left', 'left', 'left', 'left', 'left']);
// C boundary: 49 inputs with the door still closed, the 50th
// opens it, the next walks through.
const c = run([...E, 'right', 'left', 'right', 'left', 'right',
  'left', 'left']);
// D stays open: through the door, twenty more moves, back in.
const d = run([...E, 'right', 'left', 'left', 'right', 'left',
  ...Array(10).fill(['right', 'left']).flat(),
  'left', 'left', 'left', 'left', 'left']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-79-move-door-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a, b: b, c: c, d: d,
  fresh: { steps: s0.steps, moves: s0.counters['movedoor:moves'],
    open: !!((s0.meta['6,7'] || {}).move_open) },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MoveDoorMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_plan_a_fifty_move_route(self):
        a = self.r["a"]
        self.assertEqual(a[44]["pos"], {"x": 7, "y": 7})
        self.assertEqual(a[44]["moves"], 44)
        self.assertFalse(a[44]["open"])
        # The 50th input opens the door and walks through it.
        self.assertEqual(a[50]["pos"], {"x": 6, "y": 7})
        self.assertEqual(a[50]["steps"], 50)
        self.assertEqual(a[50]["moves"], 50)
        self.assertTrue(a[50]["open"])
        # Orb, then the warp: the run is won with nothing left.
        self.assertEqual(a[54]["pos"], {"x": 2, "y": 7})
        self.assertEqual(a[54]["status"], "won")
        self.assertEqual(a[54]["orbs"], 0)

    def test_adversarial_efficient_route_arrives_early(self):
        b = self.r["b"]
        # Efficient arrival in the low forties: still closed.
        self.assertEqual(b[44]["pos"], {"x": 7, "y": 7})
        self.assertFalse(b[44]["open"])
        # The naive push at the closed door: no move, no loss,
        # never stranded; the input still counts as a move.
        self.assertEqual(b[45]["pos"], {"x": 7, "y": 7})
        self.assertEqual(b[45]["steps"], 45)
        self.assertEqual(b[45]["status"], "playing")
        self.assertFalse(b[45]["open"])
        # Spending the remaining moves on detours and returning
        # opens the door and completes the room.
        self.assertEqual(b[50]["pos"], {"x": 6, "y": 7})
        self.assertTrue(b[50]["open"])
        self.assertEqual(b[54]["status"], "won")

    def test_boundary_forty_ninth_and_fiftieth_moves(self):
        c = self.r["c"]
        self.assertEqual(c[49]["steps"], 49)
        self.assertEqual(c[49]["moves"], 49)
        self.assertFalse(c[49]["open"])
        # Exactly the 50th move input opens it.
        self.assertEqual(c[50]["steps"], 50)
        self.assertTrue(c[50]["open"])
        self.assertEqual(c[51]["pos"], {"x": 6, "y": 7})

    def test_boundary_open_stays_open(self):
        d = self.r["d"]
        # The 50th input is a pacing move beside the door: the
        # door opens on it and never closes again.
        self.assertEqual(d[50]["pos"], {"x": 8, "y": 7})
        self.assertTrue(d[50]["open"])
        # Twenty more moves and a return: still open, and walking
        # back through needs no further counting.
        self.assertEqual(d[69]["steps"], 69)
        self.assertTrue(d[69]["open"])
        self.assertEqual(d[70]["pos"], {"x": 6, "y": 7})
        self.assertTrue(d[70]["open"])
        self.assertEqual(d[74]["status"], "won")

    def test_restart_restores_door_and_counter(self):
        self.assertEqual(self.r["fresh"],
                         {"steps": 0, "moves": 0, "open": False})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wiring_renders_door_and_counter(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("move-door-open.png", js)
        self.assertIn("movedoor:moves", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/movedoor/main.js", html)


@unittest.skipUnless(shutil.which("node"), "node not available")
class MoveDoorAssetPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
console.log(JSON.stringify({
  names: core.assetsForLevel(level),
  paths: core.assetPathsForLevel(level),
}));
"""
        out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                             capture_output=True, text=True, check=True)
        cls.result = json.loads(out.stdout.strip().splitlines()[-1])
        cls.by_name = {a["name"]: a["url"] for a in cls.result["paths"]}

    def test_bundled_assets_load_from_the_pack(self):
        for name in ("move-door-closed.png", "move-door-open.png",
                     "move-counter.png"):
            self.assertIn(name, self.result["names"])
            self.assertEqual(self.by_name[name],
                             f"packs/movedoor/assets/{name}")


if __name__ == "__main__":
    unittest.main()
