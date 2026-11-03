"""Checks for the mimic orb (mech-36-mimic-orb).

The mechanic lives in the pure GameCore step (packs/mimic);
driven here under Node against the teaching room. Rules: the
mimic is identical to an orb until the player comes within one
tile (Manhattan <= 1), when it reveals and starts a small
three-tile patrol, lethal on touch; before it reveals, stepping
on it collects nothing; restart (fresh state) restores the
disguise. YAML test_cases covered: 'reveal then time the
patrol' (solution), 'adversarial collect in order', 'reveal
distance and no early collect', 'joins an existing loop'
(blocked-by 31, skipped with reason), 'restart and replay'.

Run with: python -m unittest tools.test_mech_36_mimic_orb -v
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

LEVEL_ID = "mech-36-mimic-orb-room"


class MimicRoomLevelTests(unittest.TestCase):
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
        orb_row = next(r for r in rows if "M" in r)
        # Three orbs in a row: real, mimic (middle), real.
        self.assertEqual(orb_row.count("*"), 2)
        self.assertEqual(orb_row.count("M"), 1)
        self.assertLess(orb_row.index("*"), orb_row.index("M"))
        self.assertLess(orb_row.index("M"), orb_row.rindex("*"))
        # The patrol lane: two open floor tiles below the mimic.
        mx = orb_row.index("M")
        my = rows.index(orb_row)
        self.assertEqual(rows[my + 1][mx], ".")
        self.assertEqual(rows[my + 2][mx], ".")


CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function mimicPos(s) {
  for (let y = 0; y < s.objects.length; y++)
    for (let x = 0; x < s.objects[y].length; x++)
      if (s.objects[y][x] && s.objects[y][x].startsWith('mimic'))
        return { x, y, id: s.objects[y][x] };
  return null;
}
function run(seq) {
  let s = core.initialState(level, 'mech-36-mimic-orb-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left, mimic: mimicPos(s),
    row: s.grid[2] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// NAIVE: collect in the order met, walk straight on.
const naive = run(['right', 'right', 'right', 'right']);
// PATROL: reveal, then wait (bump the wall) watching the patrol.
const patrol = run(['right', 'right', 'right',
  'up', 'up', 'up', 'up', 'up', 'up', 'up']);
// SOLUTION: reveal, step aside, cross while it patrols, take the
// far orb, time the return, back to the start with both orbs.
const solution = run(['right', 'right', 'right', 'up', 'down',
  'right', 'right', 'right',
  'left', 'left', 'left', 'left', 'left', 'left']);
// BOUNDARY: stand diagonally (Manhattan 2) - must NOT reveal.
const diagonal = run(['down', 'right', 'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-36-mimic-orb-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  naive, patrol, solution, diagonal,
  fresh: { mimic: mimicPos(core.initialState(level,
      'mech-36-mimic-orb-room')),
    row: core.initialState(level, 'mech-36-mimic-orb-room').grid[2],
    orbs: core.readout(core.initialState(level,
      'mech-36-mimic-orb-room')).orbs_left },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class MimicMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_disguised_mimic_is_not_counted_as_an_orb(self):
        fresh = self.r["fresh"]
        self.assertEqual(fresh["mimic"], {"x": 5, "y": 2, "id": "mimic:orb"})
        self.assertEqual(fresh["row"], "#P.*.M.*....#")
        # Only the two real orbs count toward the gate.
        self.assertEqual(fresh["orbs"], 2)

    def test_adversarial_collect_in_order_reveals_and_resets(self):
        n = self.r["naive"]
        # First real orb collected on the way.
        self.assertEqual(n[2]["pos"], {"x": 3, "y": 2})
        self.assertEqual(n[2]["orbs"], 1)
        self.assertEqual(n[2]["mimic"]["id"], "mimic:orb")
        # At arm's length (one tile away) it reveals.
        self.assertEqual(n[3]["pos"], {"x": 4, "y": 2})
        self.assertEqual(n[3]["mimic"], {"x": 5, "y": 2, "id": "mimic:revealed"})
        # Walking on blindly touches it: lost, and stepping on
        # the mimic collected nothing (orbs unchanged).
        self.assertEqual(n[4]["pos"], {"x": 5, "y": 2})
        self.assertEqual(n[4]["status"], "lost")
        self.assertEqual(n[4]["orbs"], 1)

    def test_reveal_exactly_at_one_tile_never_earlier(self):
        d = self.r["diagonal"]
        # (4,3) is diagonally adjacent: Manhattan distance 2.
        self.assertEqual(d[4]["pos"], {"x": 4, "y": 3})
        self.assertEqual(d[4]["mimic"]["id"], "mimic:orb")
        p = self.r["patrol"]
        # One tile away orthogonally: revealed on that step.
        self.assertEqual(p[3]["mimic"]["id"], "mimic:revealed")

    def test_revealed_mimic_patrols_three_tiles(self):
        p = self.r["patrol"]
        ys = [p[i]["mimic"]["y"] for i in range(3, 11)]
        # Reveal at anchor, then 3 -> 4 -> 3 -> 2 -> 3 ... ping-pong
        # over the three-tile patrol (y = 2, 3, 4), never wider.
        self.assertEqual(ys, [2, 3, 4, 3, 2, 3, 4, 3])
        self.assertTrue(all(p[i]["mimic"]["x"] == 5 for i in range(3, 11)))
        self.assertTrue(all(p[i]["status"] == "playing" for i in range(11)))

    def test_solution_times_the_patrol_and_collects_both_orbs(self):
        s = self.r["solution"]
        self.assertEqual(s[-1]["pos"], {"x": 1, "y": 2})
        self.assertEqual(s[-1]["orbs"], 0)
        self.assertEqual(s[-1]["status"], "playing")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_the_mimic_states(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("dt.ch === 'M'", js)
        self.assertIn("mimicPool", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/mimic/main.js", html)

    def test_joins_an_existing_loop(self):
        self.skipTest("blocked-by: 31 (patroller): a revealed mimic "
                      "joining a patroller loop needs the patroller "
                      "mechanic, which is not built yet")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'up', 'down',
  'right', 'right', 'right',
  'left', 'left', 'left', 'left', 'left', 'left'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-36-mimic-orb-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-36-mimic-orb-room', log);
const replayed2 = core.replay(level, 'mech-36-mimic-orb-room',
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
                         {"pos": {"x": 1, "y": 2}, "orbs": 0,
                          "status": "playing"})
        self.assertEqual(self.r["replaySteps"], 14)

    def test_restart_restores_the_disguise(self):
        r = run_core(BEHAVIOUR_SCRIPT)
        self.assertEqual(r["fresh"]["mimic"],
                         {"x": 5, "y": 2, "id": "mimic:orb"})
        self.assertEqual(r["fresh"]["row"], "#P.*.M.*....#")
        self.assertEqual(r["fresh"]["orbs"], 2)


if __name__ == "__main__":
    unittest.main()
