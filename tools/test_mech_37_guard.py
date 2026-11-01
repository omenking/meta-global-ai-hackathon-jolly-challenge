"""Checks for the guard (mech-37-guard, candidate #37).

The mechanic lives in the pure GameCore step (packs/guard);
driven here under Node against the teaching room. Rules: the
guard never leaves its corridor tile; its facing rotates 90
degrees clockwise every four successful player moves (blocked
pushes do not count); stepping onto its tile from the front it
faces loses the attempt (reset on retry); entering from behind
or from the side passes; restart (fresh state) restores the
placed tile and starting facing; a recorded session replays to
the same end state. Covers every YAML test_cases entry for
mechanic #37; the bounce-pad case is blocked-by 6 and is an
explicit skip, never a fake pass.

Run with: python -m unittest tools.test_mech_37_guard -v
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

LEVEL_ID = "mech-37-guard-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


class GuardRoomLevelTests(unittest.TestCase):
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
        guard = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "U"]
        self.assertEqual(guard, [(6, 3)])
        # The guard tile is the only opening in the divider column.
        column = "".join(r[6] for r in rows)
        self.assertEqual(column, "###U###")
        # Player spawns west of the guard in its corridor row; an
        # orb and the warp wait beyond it.
        self.assertEqual(rows[3].index("P"), 3)
        self.assertIn("*", "".join(rows))
        self.assertIn("X", "".join(rows))
        self.assertEqual(self.level["legend"]["U"]["def"],
                         "guard:guard-left")


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function run(seq) {
  let s = core.initialState(level, 'mech-37-guard-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    facing: (s.meta['6,3'] || {}).guard_facing || null,
    guardDef: s.objects[3][6], row: s.grid[3],
    moves: s.counters['guard:move_count'] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// Turns: pace left/right west of the guard.
const turns = run(['left', 'right', 'left', 'right',
  'left', 'right', 'left', 'right']);
// Blocked pushes into the north wall must not advance the cycle.
const bumps = run(['up', 'up', 'up', 'up', 'left', 'right']);
// Adversarial: walk straight in while the guard faces the player.
const naive = run(['right', 'right', 'right']);
// Pass from behind: 8 pacing moves turn its back (facing right).
const behind = run(['right', 'left', 'right', 'left',
  'right', 'left', 'right', 'right', 'right', 'right']);
// Side entry: after 4 moves it faces up; entering moving right
// is perpendicular and passes.
const side = run(['right', 'left', 'right', 'left',
  'right', 'right', 'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-37-guard-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  turns, bumps, naive, behind, side,
  fresh: (() => { const f = core.initialState(level,
    'mech-37-guard-room');
    return { facing: (f.meta['6,3'] || {}).guard_facing,
      guardDef: f.objects[3][6], pos: { ...f.player } }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class GuardMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_turns_every_four_moves(self):
        t = self.r["turns"]
        self.assertEqual(t[0]["facing"], "left")
        # Three successful moves leave the facing unchanged.
        self.assertEqual(t[3]["facing"], "left")
        self.assertEqual(t[3]["moves"], 3)
        # The fourth rotates exactly 90 degrees, once.
        self.assertEqual(t[4]["facing"], "up")
        self.assertEqual(t[4]["moves"], 4)
        self.assertEqual(t[7]["facing"], "up")
        self.assertEqual(t[8]["facing"], "right")
        # The guard never leaves its corridor tile.
        for snap in t:
            self.assertTrue(snap["guardDef"].startswith("guard:guard-"))
            self.assertEqual(snap["row"][6], "U")

    def test_blocked_pushes_do_not_count_as_moves(self):
        b = self.r["bumps"]
        # Two real moves north, two wall bumps, then left/right:
        # only the four real moves rotate the facing.
        self.assertEqual(b[4]["facing"], "left")
        self.assertEqual(b[4]["moves"], 2)
        self.assertEqual(b[6]["facing"], "up")
        self.assertEqual(b[6]["moves"], 4)

    def test_adversarial_straight_walk_in(self):
        n = self.r["naive"]
        self.assertEqual(n[2]["pos"], {"x": 5, "y": 3})
        self.assertEqual(n[2]["status"], "playing")
        # Meeting it from the front it faces loses the attempt;
        # retrying is a fresh state (see restart test), never
        # stranded on the guard tile.
        self.assertEqual(n[3]["pos"], {"x": 6, "y": 3})
        self.assertEqual(n[3]["status"], "lost")

    def test_pass_from_behind_in_the_window(self):
        b = self.r["behind"]
        self.assertEqual(b[8]["facing"], "right")
        self.assertEqual(b[8]["pos"], {"x": 5, "y": 3})
        # Entering from behind passes onto and through its tile.
        self.assertEqual(b[9]["pos"], {"x": 6, "y": 3})
        self.assertEqual(b[9]["status"], "playing")
        self.assertEqual(b[10]["pos"], {"x": 7, "y": 3})
        self.assertEqual(b[10]["status"], "playing")

    def test_side_entry_passes(self):
        s = self.r["side"]
        self.assertEqual(s[4]["facing"], "up")
        self.assertEqual(s[7]["pos"], {"x": 6, "y": 3})
        self.assertEqual(s[7]["status"], "playing")
        self.assertEqual(s[8]["pos"], {"x": 7, "y": 3})

    def test_restart_restores_guard(self):
        self.assertEqual(self.r["fresh"],
                         {"facing": "left",
                          "guardDef": "guard:guard-left",
                          "pos": {"x": 3, "y": 3}})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_facing_arrow(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("guard-facing-", js)
        self.assertIn("guard_facing", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/guard/main.js", html)

    def test_manifest_assets_exist(self):
        pack = ROOT / "tools" / "static" / "packs" / "guard"
        manifest = json.loads(
            (pack / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "guard")
        self.assertEqual(
            [a["file"] for a in manifest["assets"] if a["bundled"]],
            ["guard-facing-up.png", "guard-facing-right.png",
             "guard-facing-down.png", "guard-facing-left.png"])
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"])
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]),
                             (512, 512), entry["file"])

    @unittest.skip("blocked-by: 6 (bounce pad): launch over the "
                   "guard timed to its turn needs the bounce pad, "
                   "which is not built in this feature")
    def test_launch_over_in_the_window(self):
        raise AssertionError("unreachable: blocked-by 6")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'left', 'right', 'left',
  'right', 'left', 'right', 'right', 'right', 'right',
  'right', 'up', 'up', 'right', 'right', 'right', 'down', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-37-guard-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-37-guard-room', log);
const replayed2 = core.replay(level, 'mech-37-guard-room',
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
                         {"pos": {"x": 11, "y": 3}, "orbs": 0,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 18)


if __name__ == "__main__":
    unittest.main()
