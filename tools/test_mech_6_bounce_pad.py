"""Checks for the bounce pad (mech-6-bounce-pad).

The mechanic lives in the pure GameCore step (packs/bounce);
driven here under Node against the teaching room. Rules: stepping
on the pad compresses it for exactly one full move with the player
standing on it; the next directional input launches exactly two
tiles that way, clearing the tile in between; the landing tile
must be empty floor or the launch falls and loses; restart (fresh
state) restores the pad. The guard adversarial case from the YAML
is blocked-by mechanic 37 (guard), which is not built, so it is
an explicit skip below, never a fake pass.

Run with: python -m unittest tools.test_mech_6_bounce_pad -v
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

LEVEL_ID = "mech-6-bounce-pad-room"
PAD1 = "5,3"
PAD2 = "10,5"


class BounceRoomLevelTests(unittest.TestCase):
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
        # The teaching pad sits west of a one-tile void gap with
        # floor beyond it, in a wall divider.
        pad_row = next(r for r in rows if "BV" in r)
        self.assertEqual(pad_row.count("B"), 1)
        self.assertEqual(grid.count("B"), 2)
        # An orb and the exit on the far side of the gap.
        self.assertGreaterEqual(grid.count("*"), 2)
        self.assertIn("X", grid)
        pad_y = rows.index(pad_row)
        far = [ch for x, ch in enumerate(rows[pad_y]) if x > 6]
        self.assertIn(".", far)


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
  let s = core.initialState(level, 'mech-6-bounce-pad-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    stage1: (s.meta['5,3'] || {}).bounce_stage || 0,
    stage2: (s.meta['10,5'] || {}).bounce_stage || 0,
    fx: s.last_effects || [] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
const toPad = ['right', 'right', 'right', 'right', 'down', 'down'];
// A: solution - compress, launch east over the gap, orb, exit.
const a = run([...toPad, 'wait', 'right',
  'up', 'up', 'right', 'right', 'right', 'right']);
// B: naive early launch press during compression, then launch.
const b = run([...toPad, 'right', 'right']);
// C: compression move spent stepping off toward floor, then launch.
const c = run([...toPad, 'up', 'right']);
// W: wait while ready (does not launch), then launch.
const w = run([...toPad, 'wait', 'wait', 'right']);
// N: launch north travels exactly two tiles onto floor.
const n = run([...toPad, 'wait', 'up']);
// D: far pad launched east into the wall landing falls.
const d = run([...toPad, 'wait', 'right',
  'down', 'down', 'right', 'right', 'right', 'wait', 'right']);
// F: walking into the void gap on foot is falling.
const f = run([...toPad, 'wait', 'right', 'left']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-6-bounce-pad-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({ a, b, c, w, n, d, f,
  freshStage: (core.initialState(level,
    'mech-6-bounce-pad-room').meta['5,3'] || {}).bounce_stage || 0,
  pure: JSON.stringify(s0) === before }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class BounceMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_chosen_launch_over_the_gap(self):
        a = self.r["a"]
        # Stepping on the pad starts compression (stage 1).
        self.assertEqual(a[6]["pos"], {"x": 5, "y": 3})
        self.assertEqual(a[6]["stage1"], 1)
        self.assertEqual(a[6]["status"], "playing")
        # One full move standing on it: compressed and ready.
        self.assertEqual(a[7]["pos"], {"x": 5, "y": 3})
        self.assertEqual(a[7]["stage1"], 2)
        # Chosen launch: exactly two tiles east, over the void at
        # (6,3), onto floor at (7,3); the pad resets for reuse.
        self.assertEqual(a[8]["pos"], {"x": 7, "y": 3})
        self.assertEqual(a[8]["stage1"], 0)
        self.assertEqual(a[8]["status"], "playing")
        self.assertIn("bounceLaunch", a[8]["fx"])
        # Far orb collected, then the exit wins the room.
        self.assertEqual(a[12]["orbs"], 1)
        self.assertEqual(a[14]["pos"], {"x": 11, "y": 1})
        self.assertEqual(a[14]["status"], "won")

    def test_one_move_pause_boundary(self):
        b = self.r["b"]
        # Pressing toward the gap during compression does not
        # launch and does not fall: it is the pause move itself.
        self.assertEqual(b[7]["pos"], {"x": 5, "y": 3})
        self.assertEqual(b[7]["stage1"], 2)
        self.assertEqual(b[7]["status"], "playing")
        # The next directional input launches.
        self.assertEqual(b[8]["pos"], {"x": 7, "y": 3})
        # Stepping off toward floor during compression is likewise
        # the pause: the player ends the move back on the pad.
        c = self.r["c"]
        self.assertEqual(c[7]["pos"], {"x": 5, "y": 3})
        self.assertEqual(c[7]["stage1"], 2)
        self.assertEqual(c[8]["pos"], {"x": 7, "y": 3})
        # Waiting longer while ready does not launch by itself and
        # does not spend the launch.
        w = self.r["w"]
        self.assertEqual(w[8]["pos"], {"x": 5, "y": 3})
        self.assertEqual(w[8]["stage1"], 2)
        self.assertEqual(w[9]["pos"], {"x": 7, "y": 3})

    def test_exactly_two_tiles_and_landing_must_be_floor(self):
        # North launch from the teaching pad lands exactly two
        # tiles away on floor.
        n = self.r["n"]
        self.assertEqual(n[8]["pos"], {"x": 5, "y": 1})
        self.assertEqual(n[8]["status"], "playing")
        # East launch from the far pad: the tile two away is wall,
        # so the player does not land there and the attempt falls.
        d = self.r["d"]
        self.assertEqual(d[13]["pos"], {"x": 10, "y": 5})
        self.assertEqual(d[13]["stage2"], 1)
        self.assertEqual(d[15]["pos"], {"x": 11, "y": 5})
        self.assertEqual(d[15]["status"], "lost")
        # Walking into the gap on foot (no launch) is falling.
        f = self.r["f"]
        self.assertEqual(f[9]["pos"], {"x": 6, "y": 3})
        self.assertEqual(f[9]["status"], "lost")

    @unittest.skip("blocked-by: 37 (guard): the guard mechanic is "
                   "not built, so being caught while the pad "
                   "compresses cannot be exercised yet")
    def test_adversarial_caught_in_the_pause(self):
        raise AssertionError("unreachable: blocked by guard (37)")

    def test_restart_restores_the_pad(self):
        self.assertEqual(self.r["freshStage"], 0)

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_the_pad_stages(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'B'", js)
        self.assertIn("bounce-pad-compressed.png", js)
        self.assertIn("jolly-launching.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/bounce/main.js", html)

    def test_pack_assets_are_bundled_512_pngs(self):
        pack = ROOT / "tools" / "static" / "packs" / "bounce"
        manifest = json.loads(
            (pack / "manifest.json").read_text(encoding="utf-8"))
        bundled = [a for a in manifest["assets"] if a["bundled"]]
        self.assertEqual([a["file"] for a in bundled],
                         ["bounce-pad.png", "bounce-pad-compressed.png",
                          "jolly-launching.png"])
        for entry in bundled:
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512))


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'right', 'down', 'down',
  'wait', 'right', 'up', 'up', 'right', 'right', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-6-bounce-pad-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-6-bounce-pad-room', log);
const replayed2 = core.replay(level, 'mech-6-bounce-pad-room',
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
                         {"pos": {"x": 11, "y": 1}, "orbs": 1,
                          "status": "won"})
        self.assertEqual(self.r["replaySteps"], 14)


if __name__ == "__main__":
    unittest.main()
