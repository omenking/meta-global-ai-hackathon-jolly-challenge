"""Checks for the ice bridge (mech-50-ice-bridge).

The mechanic lives in the pure GameCore step (packs/ice-bridge);
driven here under Node against the teaching room. Rules: shallow
water alone cannot be entered and is not lethal; a bridge tile over
it can be crossed without stopping; ending a full move on the same
bridge tile (wait or blocked push) melts it, you fall, and you
return to the room start (the checkpoint fallback until mech 48
lands); a bridge next to fire melts (fire spread is mech 43);
restart (fresh state) restores every bridge tile.

YAML test_cases coverage (terrain-and-hazards.yml #50):
- formed by an ice block: blocked-by 82 (ice block) -> skipped.
- keep-moving crossing: verified below.
- adversarial standing still: melt + return to room start verified;
  the checkpoint-tile semantics are blocked-by 48 -> skipped.
- restart and replay: verified below (SanityReplayTests).

Run with: python -m unittest tools.test_mech_50_ice_bridge -v
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

LEVEL_ID = "mech-50-ice-bridge-room"


class IceBridgeRoomLevelTests(unittest.TestCase):
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
        bridge_row = next(r for r in rows if "III" in r)
        self.assertEqual(bridge_row.count("I"), 3)
        # Shallow channel above and below the bridge, far bank in view.
        self.assertIn("~~~", rows[1])
        self.assertIn("~~~", rows[3])
        far_orb = [(x, y) for y, r in enumerate(rows)
                   for x, ch in enumerate(r) if ch == "*"]
        bridge_xs = [x for x, ch in enumerate(bridge_row) if ch == "I"]
        self.assertTrue(any(x > max(bridge_xs) for x, _ in far_orb),
                        "no orb beyond the bridge")


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
  let s = core.initialState(level, 'mech-50-ice-bridge-room');
  const snap = () => ({ pos: { ...s.player }, row: s.grid[2],
    status: s.status, orbs: core.readout(s).orbs_left });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return { snaps, final: s };
}
const toBridge = ['right', 'right', 'right', 'down'];
// A: cross without stopping, take the far orb.
const a = run([...toBridge, 'right', 'right', 'right', 'right',
  'right', 'right', 'up']);
// B: stand on the middle bridge tile and push into the water (blocked).
const b = run([...toBridge, 'right', 'right', 'up']);
// C: shallow water alone cannot be entered from the west bank.
const c = run(['right', 'right', 'right', 'right']);
// F: synthetic fire adjacency (fire spread itself is mech 43).
let fs = core.initialState(level, 'mech-50-ice-bridge-room');
fs.objects[1][5] = 'fire:fire';
fs = core.step(fs, { t_ms: 100, input: 'right' });
const fireRow = fs.grid[2];
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-50-ice-bridge-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a.snaps, b: b.snaps, c: c.snaps, fireRow,
  freshRow: core.initialState(level,
    'mech-50-ice-bridge-room').grid[2],
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class IceBridgeMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_keep_moving_crossing_reaches_far_bank_bridge_survives(self):
        a = self.r["a"]
        self.assertEqual(a[4]["pos"], {"x": 4, "y": 2})
        self.assertEqual(a[8]["pos"], {"x": 8, "y": 2})
        self.assertEqual(a[11]["pos"], {"x": 10, "y": 1})
        self.assertEqual(a[11]["orbs"], 1)
        self.assertEqual(a[11]["row"], "#....III....#")
        self.assertEqual(a[11]["status"], "playing")

    def test_standing_still_melts_and_returns_to_room_start(self):
        b = self.r["b"]
        # On the middle bridge tile, then a blocked push: a full
        # stopped move melts the tile and returns the player to the
        # room start, never stranded mid-water and not a loss.
        self.assertEqual(b[6]["pos"], {"x": 6, "y": 2})
        self.assertEqual(b[7]["pos"], {"x": 1, "y": 1})
        self.assertEqual(b[7]["status"], "playing")
        self.assertEqual(b[7]["row"], "#....I~I....#")

    def test_shallow_water_alone_cannot_be_entered(self):
        c = self.r["c"]
        self.assertEqual(c[4]["pos"], {"x": 4, "y": 1})
        self.assertEqual(c[4]["status"], "playing")

    def test_fire_adjacency_melts_bridge(self):
        # Only the fire-adjacent bridge tile melts; spread is mech 43.
        self.assertEqual(self.r["fireRow"], "#....~II....#")

    def test_restart_restores_the_bridge(self):
        self.assertEqual(self.r["freshRow"], "#....III....#")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_pack_is_wired_into_the_game(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/ice-bridge/main.js", html)
        core = (ROOT / "tools" / "static" / "game-core.js").read_text(
            encoding="utf-8")
        self.assertIn("registerIceBridgePack", core)

    def test_formed_by_an_ice_block(self):
        self.skipTest("blocked-by: 82 (ice block): pushable ice "
                      "blocks are not built yet, so bridge formation "
                      "by pushing cannot be verified; the teaching "
                      "room starts already bridged per its teaching "
                      "moment")

    def test_checkpoint_tile_semantics(self):
        self.skipTest("blocked-by: 48 (checkpoint): checkpoint tiles "
                      "are not built yet; melt returns the player to "
                      "the room start, verified above, and checkpoint "
                      "touch/timer semantics run when mech 48 lands")

    def test_fire_spread(self):
        self.skipTest("blocked-by: 43 (fire tile): fire spread is "
                      "not built yet; only fire-adjacency melting is "
                      "verified above")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'right', 'down',
  'right', 'right', 'right', 'right', 'right', 'right', 'up'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-50-ice-bridge-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-50-ice-bridge-room', log);
const replayed2 = core.replay(level, 'mech-50-ice-bridge-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player },
    orbs: core.readout(live).orbs_left },
  liveDigest: core.stateDigest(live),
  replayDigest: core.stateDigest(replayed[replayed.length - 1]),
  replay2Digest: core.stateDigest(replayed2[replayed2.length - 1]),
  replaySteps: replayed.length - 1,
  row: replayed[replayed.length - 1].grid[2],
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
                         {"pos": {"x": 10, "y": 1}, "orbs": 1})
        self.assertEqual(self.r["row"], "#....III....#")
        self.assertEqual(self.r["replaySteps"], 11)


if __name__ == "__main__":
    unittest.main()
