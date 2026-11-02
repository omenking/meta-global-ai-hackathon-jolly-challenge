"""Checks for the secret wall (mech-59-secret-wall).

The mechanic lives in the pure GameCore step (packs/secret-wall);
driven here under Node against the teaching room. Rules (YAML
test_cases): drawn exactly as a wall but with no collision; the
first walk-through fades the sprite and the opening stays passable
both ways; a readable clue sits beside it; naive solid-wall play
finishes one orb short and is never stranded; restart (fresh
state) restores the unfaded wall; sessions replay deterministically.

Run with: python -m unittest tools.test_mech_59_secret_wall -v
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

LEVEL_ID = "mech-59-secret-wall-room"


class SecretWallRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("S"), 1)
        self.assertGreaterEqual(grid.count("*"), 2)
        s_pos = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "S"]
        (sx, sy) = s_pos[0]
        # Last orb behind the secret wall (other side of divider).
        orbs = [(x, y) for y, r in enumerate(rows)
                for x, ch in enumerate(r) if ch == "*"]
        self.assertTrue(any(x > sx for x, _ in orbs),
                        "no orb behind the secret wall")
        self.assertTrue(any(x < sx for x, _ in orbs),
                        "no orb on the main side")
        # Readable clue on the main side near the secret wall.
        clues = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "?"]
        self.assertEqual(len(clues), 1)
        (cx, cy) = clues[0]
        self.assertLess(cx, sx)
        self.assertLessEqual(abs(cy - sy), 2)
        # Exit + gate on the main side: secret hides only an
        # optional orb, never the required exit.
        self.assertLess(rows[6].index("X"), sx)
        self.assertLess(rows[6].index("G"), sx)


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
  let s = core.initialState(level, 'mech-59-secret-wall-room');
  const snap = () => ({ pos: { ...s.player },
    row2: s.grid[2], status: s.status,
    orbs: core.readout(s).orbs_left,
    found: !!((s.meta['5,2'] || {}).secret_found) });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
// Solution: main orb, through the secret wall, secret orb, back
// through it, gate, exit.
const sol = run(['right', 'right', 'right', 'down', 'right',
  'right', 'right', 'up', 'right',
  'left', 'down', 'left', 'left', 'left',
  'down', 'down', 'down', 'down', 'left', 'left']);
// Adversarial: treat every wall as solid — main orb only, gate
// stays shut, player keeps moving (never stranded).
const adv = run(['right', 'right',
  'down', 'down', 'down', 'down', 'down', 'right', 'right',
  'left', 'left', 'up']);
// Real wall never enterable: push into divider '#' above secret.
const wall = run(['right', 'right', 'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-59-secret-wall-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, adv: adv.snaps, wall: wall.snaps,
  solFinal: { pos: { ...sol.final.player }, status: sol.final.status,
    orbs: core.readout(sol.final).orbs_left },
  freshRow2: core.initialState(level,
    'mech-59-secret-wall-room').grid[2],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class SecretWallMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_finds_clue_and_walks_through(self):
        sol = self.r["sol"]
        # Stands before the secret wall at (4,2), still unfaded.
        self.assertEqual(sol[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(sol[4]["row2"], "#....S......#")
        # Walks straight through what is drawn as a wall.
        self.assertEqual(sol[5]["pos"], {"x": 5, "y": 2})
        self.assertEqual(sol[5]["status"], "playing")

    def test_first_walkthrough_fades_the_sprite(self):
        sol = self.r["sol"]
        self.assertFalse(sol[4]["found"])
        self.assertTrue(sol[5]["found"])
        self.assertEqual(sol[5]["row2"], "#....s......#")
        # Opening stays passable in both directions.
        self.assertEqual(sol[13]["pos"], {"x": 5, "y": 2})
        self.assertEqual(sol[13]["row2"], "#....s......#")
        self.assertEqual(sol[14]["pos"], {"x": 4, "y": 2})

    def test_solution_collects_secret_orb_and_wins(self):
        self.assertEqual(self.r["solFinal"],
                         {"pos": {"x": 2, "y": 6},
                          "status": "won", "orbs": 0})

    def test_adversarial_solid_wall_play_one_orb_short(self):
        adv = self.r["adv"]
        # Gate at (3,6) stays shut with one orb left; the player
        # is blocked there, not stranded, and walks away freely.
        self.assertEqual(adv[9]["pos"], {"x": 4, "y": 5})
        self.assertEqual(adv[9]["orbs"], 1)
        self.assertEqual(adv[9]["status"], "playing")
        self.assertEqual(adv[11]["pos"], {"x": 2, "y": 5})
        self.assertEqual(adv[11]["status"], "playing")

    def test_real_wall_never_enterable(self):
        wall = self.r["wall"]
        self.assertEqual(wall[4]["pos"], {"x": 4, "y": 1})

    def test_restart_restores_unfaded_wall(self):
        self.assertEqual(self.r["freshRow2"], "#....S......#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_faded_secret_wall(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'S'", js)
        self.assertIn("secret-wall-faded.png", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/secret-wall/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'down', 'right',
  'right', 'right', 'up', 'right',
  'left', 'down', 'left', 'left', 'left',
  'down', 'down', 'down', 'down', 'left', 'left'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-59-secret-wall-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-59-secret-wall-room', log);
const replayed2 = core.replay(level, 'mech-59-secret-wall-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row2: replayed[replayed.length - 1].grid[2],
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
                         {"pos": {"x": 2, "y": 6},
                          "status": "won", "orbs": 0})
        self.assertEqual(self.r["row2"], "#....s......#")
        self.assertEqual(self.r["replaySteps"], 20)


if __name__ == "__main__":
    unittest.main()
