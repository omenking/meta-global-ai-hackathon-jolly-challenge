"""Checks for the toggle switch (mech-22-toggle-switch).

The mechanic lives in the pure GameCore step (packs/toggle-switch);
driven here under Node against the teaching room. Rules: stepping
onto the toggle swaps its two linked doors (open<->closed) and the
state persists after leaving; each entry is one press, standing
on it does not repeat; pressing again swaps them back; restart
(fresh state) restores the placed states.

Run with: python -m unittest tools.test_mech_22_toggle_switch -v
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

LEVEL_ID = "mech-22-toggle-switch-room"


class ToggleRoomLevelTests(unittest.TestCase):
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
        self.assertIn("T", grid)
        # Two linked doors in the divider, one per east compartment.
        self.assertEqual(grid.count("a"), 1)
        self.assertEqual(grid.count("b"), 1)
        toggle = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "T"]
        doors = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch in "ab"]
        self.assertTrue(all(x > toggle[0][0] for x, _ in doors),
                        "toggle is not west of its doors")
        # The orb and the exit sit beyond the initially closed door.
        self.assertGreaterEqual(grid.count("*"), 1)
        self.assertIn("X", grid)


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
  let s = core.initialState(level, 'mech-22-toggle-switch-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    sw: s.objects[3][3], doorA: s.objects[2][6], doorB: s.objects[6][6],
    gridA: s.grid[2], gridB: s.grid[6] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toToggle = ['right', 'right', 'down', 'down'];
// S: press once, walk away through the swapped-open south door, win.
const sol = run([...toToggle,
  'down', 'down', 'down', 'right', 'right', 'right',
  'right', 'right', 'right', 'up', 'right', 'right', 'down']);
// A: press, step off, press again to be sure, find the exit closed,
//    then press once more and proceed. Never stranded.
const adv = run([...toToggle, 'left', 'right',
  'down', 'down', 'down', 'right', 'right', 'right',
  'left', 'left', 'up', 'up', 'up',
  'down', 'down', 'down', 'right', 'right', 'right', 'right']);
// W: stand on the toggle (non-move inputs) — no repeat swap.
const wait = run([...toToggle, 'wait', 'wait', 'left']);
// P: press once, make ten moves elsewhere, doors never change.
const persist = run([...toToggle,
  'left', 'up', 'up', 'right', 'right', 'down',
  'left', 'up', 'down', 'left']);
// B: south door is closed before any press.
const blocked = run(['down', 'down', 'down', 'down', 'down',
  'right', 'right', 'right', 'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-22-toggle-switch-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, adv: adv.snaps, wait: wait.snaps,
  persist: persist.snaps, blocked: blocked.snaps,
  solFinal: { pos: { ...sol.final.player },
    status: sol.final.status,
    orbs: core.readout(sol.final).orbs_left },
  fresh: (() => { const f = core.initialState(level,
    'mech-22-toggle-switch-room');
    return { sw: f.objects[3][3], doorA: f.objects[2][6],
      doorB: f.objects[6][6] }; })(),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class ToggleMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_initial_doors_one_open_one_closed(self):
        s = self.r["sol"][0]
        self.assertEqual(s["doorA"], "toggle:door-open")
        self.assertEqual(s["doorB"], "toggle:door-closed")
        self.assertEqual(s["sw"], "toggle:switch-a")

    def test_closed_door_blocks_before_any_press(self):
        b = self.r["blocked"]
        self.assertEqual(b[-1]["pos"], {"x": 5, "y": 6})
        self.assertEqual(b[-1]["status"], "playing")

    def test_solution_press_once_and_walk_away(self):
        sol = self.r["sol"]
        # snaps[4] stands on the toggle after the single press.
        self.assertEqual(sol[4]["pos"], {"x": 3, "y": 3})
        self.assertEqual(sol[4]["doorA"], "toggle:door-closed")
        self.assertEqual(sol[4]["doorB"], "toggle:door-open")
        self.assertEqual(sol[4]["sw"], "toggle:switch-b")
        # Leaving the switch changes nothing: the state persists.
        self.assertEqual(sol[5]["doorB"], "toggle:door-open")
        self.assertEqual(self.r["solFinal"],
                         {"pos": {"x": 11, "y": 6},
                          "status": "won", "orbs": 0})

    def test_adversarial_second_press_swaps_back(self):
        adv = self.r["adv"]
        # Second entry (snaps[6]) restores the placed configuration.
        self.assertEqual(adv[6]["doorA"], "toggle:door-open")
        self.assertEqual(adv[6]["doorB"], "toggle:door-closed")
        self.assertEqual(adv[6]["sw"], "toggle:switch-a")
        # The exit door blocks again, and the player is not stranded.
        self.assertEqual(adv[12]["pos"], {"x": 5, "y": 6})
        self.assertEqual(adv[12]["status"], "playing")
        # One more press reopens it and the player walks through.
        self.assertEqual(adv[-1]["pos"], {"x": 7, "y": 6})
        self.assertEqual(adv[-1]["doorB"], "toggle:door-open")

    def test_standing_on_it_does_not_repeat_the_swap(self):
        w = self.r["wait"]
        self.assertEqual(w[4]["doorB"], "toggle:door-open")
        self.assertEqual(w[5]["doorB"], "toggle:door-open")
        self.assertEqual(w[6]["doorB"], "toggle:door-open")
        self.assertEqual(w[6]["pos"], {"x": 3, "y": 3})

    def test_boundary_state_persists_off_the_switch(self):
        p = self.r["persist"]
        for snap in p[4:]:
            self.assertEqual(snap["doorA"], "toggle:door-closed")
            self.assertEqual(snap["doorB"], "toggle:door-open")

    def test_restart_restores_placed_states(self):
        self.assertEqual(self.r["fresh"],
                         {"sw": "toggle:switch-a",
                          "doorA": "toggle:door-open",
                          "doorB": "toggle:door-closed"})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_toggle_pack(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'T'", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/toggle-switch/main.js", html)

    def test_pack_assets_bundled_and_512(self):
        pack = ROOT / "tools" / "static" / "packs" / "toggle-switch"
        manifest = json.loads((pack / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "toggle-switch")
        for entry in manifest["assets"]:
            self.assertTrue(entry["bundled"], entry["file"])
            path = pack / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]),
                             (512, 512), entry["file"])


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'down', 'down',
  'down', 'down', 'down', 'right', 'right', 'right',
  'right', 'right', 'right', 'up', 'right', 'right', 'down'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-22-toggle-switch-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-22-toggle-switch-room', log);
const replayed2 = core.replay(level, 'mech-22-toggle-switch-room',
  JSON.parse(JSON.stringify(log)));
// A recorded two-press session also replays to the same end state.
const twoPress = ['right', 'right', 'down', 'down', 'left', 'right',
  'down', 'down', 'down', 'right', 'right', 'right',
  'left', 'left', 'up', 'up', 'up'];
const log2 = twoPress.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live2 = core.initialState(level, 'mech-22-toggle-switch-room');
for (const stepIn of log2) live2 = core.step(live2, stepIn);
const replayed3 = core.replay(level, 'mech-22-toggle-switch-room', log2);
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  twoPressDigest: core.stateDigest(live2),
  twoPressReplayDigest: core.stateDigest(
    replayed3[replayed3.length - 1]),
  twoPressFinal: { pos: { ...live2.player },
    doorB: live2.objects[6][6] },
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
                         {"pos": {"x": 11, "y": 6},
                          "status": "won", "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 17)

    def test_two_press_session_replays_to_same_end_state(self):
        self.assertEqual(self.r["twoPressReplayDigest"],
                         self.r["twoPressDigest"])
        self.assertEqual(self.r["twoPressFinal"],
                         {"pos": {"x": 3, "y": 3},
                          "doorB": "toggle:door-open"})


if __name__ == "__main__":
    unittest.main()
