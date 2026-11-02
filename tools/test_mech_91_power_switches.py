"""Checks for the power switches recipe (mech-91-power-switches-recipe).

The recipe lives in the pure GameCore step (packs/power-switches);
driven here under Node against the teaching room. Rules: one floor
switch, one weight switch and one toggle wired to one elevator gate;
the HUD counter (state.counters['power:count']) reaches 3/3 only
while all three are on together and only then is the elevator
called; stepping off the floor switch drops the counter, and a
block left on a plate holds it. The floor/toggle/weight/block packs
(mechanics 21/22/29/81) are not on main, so this pack provides
those switch tiles itself and every YAML test_cases entry is
exercised for real. Restart (fresh state) restores 0/3.

Run with: python -m unittest tools.test_mech_91_power_switches -v
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

LEVEL_ID = "mech-91-power-switches-recipe-room"
PACK = ROOT / "tools" / "static" / "packs" / "power-switches"


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class PowerRoomLevelTests(unittest.TestCase):
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
        for ch in "PFTWBEX*":
            self.assertIn(ch, grid)
        self.assertEqual(grid.count("F"), 1)
        self.assertEqual(grid.count("W"), 1)
        self.assertEqual(grid.count("T"), 1)
        self.assertEqual(grid.count("B"), 2)
        self.assertEqual(grid.count("E"), 1)
        # Blocks start directly below their plates, so one push
        # north holds either plate.
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "B":
                    self.assertIn(rows[y - 1][x], "FW")


class PowerPackAssetTests(unittest.TestCase):
    def test_manifest_lists_every_yaml_asset_bundled(self):
        manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pack"], "power-switches")
        files = [a["file"] for a in manifest["gui"]]
        self.assertEqual(files, ["power-counter-0.png", "power-counter-1.png",
                                 "power-counter-2.png", "power-counter-3.png"])
        for entry in manifest["gui"]:
            self.assertTrue(entry["bundled"], entry["file"])
            path = PACK / "assets" / entry["file"]
            self.assertTrue(path.is_file(), entry["file"])
            self.assertEqual(_png_size(path), (512, 512), entry["file"])


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
  let s = core.initialState(level, 'mech-91-power-switches-recipe-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    count: s.counters['power:count'], called: !!s.flags['power:called'],
    orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const SOL = ['down','down','down','down','right','right','right','right',
  'up','down','left','left','up','down','right','up','up','up','up',
  'down','right','right','right','down','right','right','right',
  'up','up','right','right'];
const sol = run(SOL);
const NAIVE = ['right','right','right','down','down','down','down',
  'right','up','left','up','up','left','down'];
const naive = run([...NAIVE, 'right', 'up', 'right', 'right', 'right',
  'down', 'right']);
const revoke = run([...SOL.slice(0, 19), 'down', 'up']);
const wStand = run(['down', 'right', 'right', 'right', 'right', 'down']);
const fStand = run(['down', 'down', 'right', 'right']);
const s0 = core.initialState(level, 'mech-91-power-switches-recipe-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  sol: sol.snaps, naive: naive.snaps, revoke: revoke.snaps,
  wStand: wStand.snaps, fStand: fStand.snaps,
  fresh: core.initialState(level,
    'mech-91-power-switches-recipe-room').counters['power:count'],
  pure: JSON.stringify(s0) === before,
  assets: core.assetPathsForLevel(level)
    .filter((a) => a.name.indexOf('power') === 0),
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class PowerSwitchesMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_solution_all_three_on_together(self):
        sol = self.r["sol"]
        self.assertEqual(sol[19]["count"], 3)
        self.assertTrue(sol[19]["called"])
        self.assertEqual(sol[-1]["pos"], {"x": 12, "y": 1})
        self.assertEqual(sol[-1]["status"], "won")
        self.assertEqual(sol[-1]["orbs"], 0)

    def test_adversarial_stepping_off_the_floor_switch(self):
        n = self.r["naive"]
        # Standing on the floor switch is the third switch: 3/3.
        self.assertEqual(n[14]["pos"], {"x": 3, "y": 3})
        self.assertEqual(n[14]["count"], 3)
        # Stepping off toward the gate drops the counter to 2/3 and
        # the elevator call is revoked; the gate then blocks.
        self.assertEqual(n[15]["count"], 2)
        self.assertFalse(n[15]["called"])
        self.assertEqual(n[-1]["pos"], {"x": 7, "y": 3})
        self.assertEqual(n[-1]["status"], "playing")

    def test_two_of_three_never_calls_the_elevator(self):
        n = self.r["naive"]
        self.assertEqual(n[-1]["count"], 2)
        self.assertFalse(n[-1]["called"])
        # The blocked gate attempt left the player beside the gate,
        # never stranded: the run is still playing and recoverable.
        self.assertEqual(n[-1]["status"], "playing")

    def test_losing_one_switch_revokes_the_call(self):
        r = self.r["revoke"]
        self.assertEqual(r[19]["count"], 3)
        self.assertTrue(r[19]["called"])
        # Pressing the toggle again is losing one switch.
        self.assertEqual(r[-1]["count"], 2)
        self.assertFalse(r[-1]["called"])

    def test_weight_switch_needs_a_block_not_the_player(self):
        w = self.r["wStand"]
        self.assertEqual(w[-1]["pos"], {"x": 5, "y": 3})
        self.assertEqual(w[-1]["count"], 0)

    def test_floor_switch_counts_the_player_standing_on_it(self):
        f = self.r["fStand"]
        self.assertEqual(f[-1]["pos"], {"x": 3, "y": 3})
        self.assertEqual(f[-1]["count"], 1)

    def test_restart_restores_counter_to_zero(self):
        self.assertEqual(self.r["fresh"], 0)

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_counter_assets_load_from_the_pack(self):
        by_name = {a["name"]: a["url"] for a in self.r["assets"]}
        for i in range(4):
            name = f"power-counter-{i}.png"
            self.assertEqual(by_name[name],
                             f"packs/power-switches/assets/{name}")

    def test_game_wires_the_pack_and_counter(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(encoding="utf-8")
        self.assertIn("power-counter-", js)
        html = (ROOT / "tools" / "static" / "game.html").read_text(encoding="utf-8")
        self.assertIn("packs/power-switches/main.js", html)


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['down','down','down','down','right','right','right','right',
  'up','down','left','left','up','down','right','up','up','up','up',
  'down','right','right','right','down','right','right','right',
  'up','up','right','right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-91-power-switches-recipe-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-91-power-switches-recipe-room', log);
const replayed2 = core.replay(level, 'mech-91-power-switches-recipe-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    count: live.counters['power:count'],
    orbs: core.readout(live).orbs_left },
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
                         {"pos": {"x": 12, "y": 1}, "status": "won",
                          "count": 3, "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 31)


if __name__ == "__main__":
    unittest.main()
