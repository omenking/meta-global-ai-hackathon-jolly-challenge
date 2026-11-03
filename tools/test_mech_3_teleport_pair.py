"""Checks for the teleport pair (mech-3-teleport-pair).

The mechanic lives in the pure GameCore step (packs/teleport);
driven here under Node against the teaching room. Rules: stepping
on a pad instantly moves you to its same-mark twin keeping your
direction; pads work both ways; if a block sits on the twin the
teleport does not happen; restart (fresh state) restores the room.
The YAML case "blocked twin prevents teleport" is blocked-by 81
(push block): no pushable block tile exists yet to place on a twin
in a level, so that case is an explicit skip below; the pack's
occupancy guard itself is exercised by occupying the twin cell
with an object at state level.

Run with: python -m unittest tools.test_mech_3_teleport_pair -v
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

LEVEL_ID = "mech-3-teleport-pair-room"


class TeleportRoomLevelTests(unittest.TestCase):
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
        # Two pads of different marks in the start chamber, two each.
        self.assertEqual(grid.count("a"), 2)
        self.assertEqual(grid.count("b"), 2)
        start_row = rows[1]
        self.assertIn("a", start_row)
        self.assertIn("b", start_row)
        # The B twin sits alone in a sealed alcove (wall rows around).
        alcove_y = next(y for y, r in enumerate(rows)
                        if "b" in r and y != 1)
        self.assertEqual(set(rows[alcove_y - 1]), {"#"})
        self.assertEqual(set(rows[alcove_y + 1]), {"#"})
        # The A twin shares its sealed chamber with orb and exit;
        # the chamber (rows 6-8) is walled off above and below.
        goal_y = next(y for y, r in enumerate(rows) if "a" in r and y != 1)
        self.assertIn("*", rows[goal_y])
        self.assertIn("X", rows[goal_y])
        self.assertEqual(set(rows[goal_y - 2]), {"#"})
        self.assertEqual(set(rows[goal_y + 2]), {"#"})


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq, mutate) {
  let s = core.initialState(level, 'mech-3-teleport-pair-room');
  if (mutate) s = mutate(s);
  const snap = () => {
    const p = s.actors.find((a) => a.id === 'player');
    return { pos: { x: p.x, y: p.y }, dir: p.dir,
      status: s.status, orbs: core.readout(s).orbs_left };
  };
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// Solution: right x3 onto pad A (4,1) -> twin (3,7), keep going to
// the orb (9,7) and exit (11,7).
const solution = run(['right','right','right',
  'right','right','right','right','right','right','right','right']);
// Both ways: arrive on the twin, step off, step back on -> start pad.
const bothWays = run(['right','right','right','left','right']);
// Adversarial: drop to row 2, cross under pad A, up onto pad B
// (8,1) -> alcove twin (6,4), step off and back on -> back where
// they started, no progress.
const adversarial = run(['down','right','right','right','right',
  'right','right','right','up','left','right']);
// Occupied twin: an object sitting on the A twin (3,7) blocks it.
const occupied = run(['right','right','right'], (s) => {
  s.objects[7][3] = 'core:orb'; return s;
});
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-3-teleport-pair-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  solution, bothWays, adversarial, occupied,
  fresh: (() => { const f = core.initialState(level,
    'mech-3-teleport-pair-room');
    return { pos: { ...f.player }, row: f.grid[1] }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class TeleportMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_paired_pads_link_chambers(self):
        s = self.r["solution"]
        self.assertEqual(s[0]["pos"], {"x": 1, "y": 1})
        # Stepping on pad A arrives instantly on its same-mark twin,
        # keeping the entry direction, with no chained bounce back.
        self.assertEqual(s[3]["pos"], {"x": 3, "y": 7})
        self.assertEqual(s[3]["dir"], "right")
        self.assertEqual(s[3]["status"], "playing")

    def test_solution_reaches_orb_and_exit(self):
        s = self.r["solution"]
        self.assertEqual(s[-1]["pos"], {"x": 11, "y": 7})
        self.assertEqual(s[-1]["orbs"], 0)
        self.assertEqual(s[-1]["status"], "won")

    def test_pads_work_both_ways(self):
        s = self.r["bothWays"]
        self.assertEqual(s[3]["pos"], {"x": 3, "y": 7})
        self.assertEqual(s[4]["pos"], {"x": 2, "y": 7})
        # Stepping back onto the twin returns to the start pad.
        self.assertEqual(s[5]["pos"], {"x": 4, "y": 1})
        self.assertEqual(s[5]["status"], "playing")

    def test_adversarial_random_pads_make_no_progress(self):
        s = self.r["adversarial"]
        # Pad B dumps the player in the sealed alcove...
        self.assertEqual(s[9]["pos"], {"x": 6, "y": 4})
        # ...and its twin sends them straight back where they started.
        self.assertEqual(s[11]["pos"], {"x": 8, "y": 1})
        self.assertEqual(s[11]["status"], "playing")
        self.assertEqual(s[11]["orbs"], 1)

    @unittest.skip("blocked-by: 81 (push block) — no pushable block "
                   "tile exists yet to sit on a twin in a level; the "
                   "pack occupancy guard is covered at state level by "
                   "test_occupied_twin_prevents_teleport")
    def test_blocked_twin_prevents_teleport(self):
        raise AssertionError("unreachable: blocked-by 81")

    def test_occupied_twin_prevents_teleport(self):
        s = self.r["occupied"]
        # With an object on the twin, stepping on pad A does not
        # teleport: the player stays on the pad they stepped on.
        self.assertEqual(s[3]["pos"], {"x": 4, "y": 1})
        self.assertEqual(s[3]["status"], "playing")

    def test_restart_restores_the_room(self):
        self.assertEqual(self.r["fresh"],
                         {"pos": {"x": 1, "y": 1},
                          "row": "#P..a...b...#"})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_the_teleport_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/teleport/main.js", html)
        core_js = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("packs/teleport/main.js", core_js)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right','right','right',
  'right','right','right','right','right','right','right','right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-3-teleport-pair-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-3-teleport-pair-room', log);
const replayed2 = core.replay(level, 'mech-3-teleport-pair-room',
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
                         {"pos": {"x": 11, "y": 7}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 11)


if __name__ == "__main__":
    unittest.main()


class TeleportPackAssetTests(unittest.TestCase):
    def test_bundled_pad_art_exists_and_is_512_png(self):
        import struct
        pack = ROOT / "tools" / "static" / "packs" / "teleport"
        manifest = json.loads((pack / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "teleport")
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["teleport-pad-a.png", "teleport-pad-b.png"])
        for entry in bundled:
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]),
                             (512, 512), entry["file"])

    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_bundled_assets_load_from_their_pack(self):
        script = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
console.log(JSON.stringify({
  paths: core.assetPathsForLevel(level),
}));
"""
        r = run_core(script)
        by_name = {a["name"]: a["url"] for a in r["paths"]}
        for name in ("teleport-pad-a.png", "teleport-pad-b.png"):
            self.assertEqual(by_name[name],
                             f"packs/teleport/assets/{name}")
