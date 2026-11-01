"""Checks for the heavy block (mech-87-heavy-block).

The mechanic lives in the pure GameCore step (packs/heavy-block);
driven here under Node against the teaching room and synthetic
mini-rooms. Rules (blocks.yml #87): it moves only onto empty
floor or a switch plate exactly as a push block (81) — water,
deep water, void, fire and lava block it; the first push input
budges it in place while Jolly strains, the second consecutive
push moves it one tile; time and enemies keep running while you
strain; wearing power gloves moves it in a single push; restart
(fresh state) restores it with no budge pending.

YAML test_cases coverage: "solution two pushes onto the switch"
is marked blocked-by 29 (weight switch), "adversarial caught
while straining" blocked-by 31 (patroller) and "blocked
destinations and gloves boundary" blocked-by 89 (power gloves):
those mechanics are not on main yet, so the pack carries local
stand-ins (switch plate/gate, patroller, gloves, hazard terrains)
that exercise every rule for real below, and the integrations
with the real mechanics are explicit skips with reasons.

Run with: python -m unittest tools.test_mech_87_heavy_block -v
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

LEVEL_ID = "mech-87-heavy-block-room"
CORE = ROOT / "tools" / "static" / "game-core.js"
LEVEL = ROOT / "levels" / f"{LEVEL_ID}.json"
PACK = ROOT / "tools" / "static" / "packs" / "heavy-block"

CORRECTED = (["wait"] * 4 + ["right"] * 11
             + ["up", "right", "right", "right", "down",
                "right", "right"])


class HeavyBlockRoomLevelTests(unittest.TestCase):
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
        self.assertEqual(grid.count("H"), 1)
        self.assertEqual(grid.count("S"), 1)
        self.assertEqual(grid.count("E"), 1)
        self.assertEqual(grid.count("V"), 1)
        block = [(x, y) for y, r in enumerate(rows)
                 for x, ch in enumerate(r) if ch == "H"][0]
        player = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "P"][0]
        switch = [(x, y) for y, r in enumerate(rows)
                  for x, ch in enumerate(r) if ch == "S"][0]
        patroller = [(x, y) for y, r in enumerate(rows)
                     for x, ch in enumerate(r) if ch == "E"][0]
        # Block between player and switch on one row; the patroller
        # shares the pushing column behind the block.
        self.assertEqual(player[1], block[1])
        self.assertEqual(block[1], switch[1])
        self.assertLess(player[0], block[0])
        self.assertLess(block[0], switch[0])
        self.assertEqual(patroller[0], block[0] - 1)


class HeavyBlockPackAssetTests(unittest.TestCase):
    def test_manifest_lists_every_yaml_asset_bundled_with_file(self):
        manifest = json.loads((PACK / "manifest.json").read_text())
        self.assertEqual(manifest["pack"], "heavy-block")
        shows = {a["file"]: a["shows"] for a in manifest["assets"]}
        for name in ("heavy-block.png", "heavy-block-budging.png",
                     "jolly-straining.png", "jolly-pushing-heavy.png"):
            self.assertIn(name, shows)
            self.assertTrue(shows[name])
            entry = next(a for a in manifest["assets"]
                         if a["file"] == name)
            self.assertTrue(entry["bundled"])
            f = PACK / "assets" / name
            self.assertTrue(f.is_file(), f"missing bundled asset {f}")
            self.assertEqual(f.read_bytes()[:8],
                             b"\x89PNG\r\n\x1a\n")

    def test_main_declares_assets_via_define_asset(self):
        js = (PACK / "main.js").read_text(encoding="utf-8")
        for name in ("heavy-block.png", "heavy-block-budging.png",
                     "jolly-straining.png", "jolly-pushing-heavy.png"):
            self.assertIn(f"defineAsset(name", js)
            self.assertIn(name, js)
        self.assertIn("packs/heavy-block/main.js",
                      (ROOT / "tools/static/game.html").read_text())
        self.assertIn("registerHeavyBlockPack",
                      (ROOT / "tools/static/game-core.js").read_text())


def run_core(script):
    out = subprocess.run(["node", "-e", script, str(CORE), str(LEVEL)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


BEHAVIOUR_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
function blockOf(s) {
  for (let y = 0; y < s.height; y++)
    for (let x = 0; x < s.width; x++)
      if (s.objects[y][x] === 'heavy:heavy-block') return { x, y };
  return null;
}
function snap(s) {
  const pat = s.actors.find((a) => a.id !== 'player');
  return { pos: { ...s.player }, block: blockOf(s), status: s.status,
    pending: s.flags.heavy_pending || null,
    budge: (s.meta[(blockOf(s) || {}).x + ',' + (blockOf(s) || {}).y] || {}).heavy_budge || null,
    pat: pat ? { x: pat.x, y: pat.y } : null,
    orbs: core.readout(s).orbs_left };
}
function run(lv, name, seq) {
  let s = core.initialState(lv, name);
  const snaps = [snap(s)];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap(s));
  });
  return { snaps, final: s };
}
const naive = run(level, 'mech-87-heavy-block-room', ['right', 'right']);
const corrected = run(level, 'mech-87-heavy-block-room',
  [...Array(4).fill('wait'), ...Array(11).fill('right'),
   'up', 'right', 'right', 'right', 'down', 'right', 'right']);
// Synthetic mini-rooms: no patroller, one rule each.
const LEG = { '.': { label: 'floor' }, '#': { label: 'wall' },
  'P': { label: 'player' },
  'H': { label: 'heavy', def: 'heavy:heavy-block' },
  'S': { label: 'switch', def: 'heavy:switch-plate' },
  'V': { label: 'gloves', def: 'heavy:power-gloves' } };
function mini(rows, extra) {
  return { name: 'mini', time_limit: 120, legend: Object.assign({}, LEG, extra || {}), rows };
}
const budgeRoom = mini(['#####', '#PH.#', '#####']);
const nonConsec = run(budgeRoom, 'mini', ['right', 'wait', 'right']);
const blockedRooms = {};
for (const [key, def] of [['water', 'water:water'], ['deep', 'heavy:deep'],
  ['fire', 'heavy:fire'], ['lava', 'heavy:lava'], ['void', 'heavy:void']]) {
  blockedRooms[key] = run(mini(['#####', '#PH?#', '#####'],
    { '?': { label: key, def } }), 'mini', ['right', 'right']);
}
const wallDest = run(mini(['#####', '#PH##', '#####']), 'mini', ['right', 'right']);
const glovesRoom = mini(['########', '#PV.HS.#', '########']);
const gloves = run(glovesRoom, 'mini', ['right', 'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-87-heavy-block-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  naive: naive.snaps, corrected: corrected.snaps,
  correctedFinal: { status: corrected.final.status,
    orbs: core.readout(corrected.final).orbs_left },
  nonConsec: nonConsec.snaps,
  blocked: Object.fromEntries(Object.entries(blockedRooms)
    .map(([k, v]) => [k, v.snaps])),
  wallDest: wallDest.snaps, gloves: gloves.snaps,
  fresh: snap(core.initialState(level, 'mech-87-heavy-block-room')),
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class HeavyBlockMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_first_push_budges_second_consecutive_push_moves(self):
        c = self.r["corrected"]
        # snaps[5]: entered the pushing tile; snaps[6]: strain push.
        self.assertEqual(c[5]["pos"], {"x": 2, "y": 2})
        self.assertEqual(c[6]["block"], {"x": 3, "y": 2})
        self.assertEqual(c[6]["pos"], {"x": 2, "y": 2})
        self.assertEqual(c[6]["budge"], "right")
        self.assertIsNotNone(c[6]["pending"])
        # snaps[7]: second consecutive push moves it exactly one tile.
        self.assertEqual(c[7]["block"], {"x": 4, "y": 2})
        self.assertEqual(c[7]["pos"], {"x": 3, "y": 2})
        self.assertIsNone(c[7]["pending"])
        self.assertIsNone(c[7]["budge"])

    def test_non_consecutive_pushes_do_not_move_the_block(self):
        n = self.r["nonConsec"]
        self.assertEqual(n[1]["block"], {"x": 2, "y": 1})
        self.assertIsNotNone(n[1]["pending"])
        # The wait clears the pending, so the next push strains again.
        self.assertIsNone(n[2]["pending"])
        self.assertEqual(n[3]["block"], {"x": 2, "y": 1})
        self.assertIsNotNone(n[3]["pending"])

    def test_solution_two_pushes_per_tile_onto_the_switch(self):
        c = self.r["corrected"]
        # After 4 waits + entry + 10 pushes the block sits on the
        # switch (8,2) and the run can finish through the gate.
        self.assertEqual(c[15]["block"], {"x": 8, "y": 2})
        self.assertEqual(self.r["correctedFinal"],
                         {"status": "won", "orbs": 0})

    def test_adversarial_caught_while_straining(self):
        n = self.r["naive"]
        self.assertEqual(n[1]["pos"], {"x": 2, "y": 2})
        self.assertEqual(n[1]["status"], "playing")
        # The strain step still advances the patroller onto the
        # player's tile: caught, run lost, block never moved.
        self.assertEqual(n[2]["status"], "lost")
        self.assertEqual(n[2]["block"], {"x": 3, "y": 2})
        self.assertEqual(n[2]["pat"], n[2]["pos"])

    def test_blocked_destinations_never_move_the_block(self):
        for key, snaps in self.r["blocked"].items():
            self.assertEqual(snaps[2]["block"], {"x": 2, "y": 1}, key)
            self.assertEqual(snaps[2]["pos"], {"x": 1, "y": 1}, key)
            self.assertIsNone(snaps[2]["pending"], key)
        w = self.r["wallDest"]
        self.assertEqual(w[2]["block"], {"x": 2, "y": 1})
        self.assertEqual(w[2]["pos"], {"x": 1, "y": 1})

    def test_power_gloves_move_it_in_a_single_push(self):
        g = self.r["gloves"]
        # Pickup, step up to the block, one push onto the switch.
        self.assertEqual(g[3]["block"], {"x": 5, "y": 1})
        self.assertEqual(g[3]["pos"], {"x": 4, "y": 1})
        self.assertIsNone(g[3]["pending"])

    def test_restart_restores_block_with_no_budge_pending(self):
        f = self.r["fresh"]
        self.assertEqual(f["block"], {"x": 3, "y": 2})
        self.assertIsNone(f["pending"])
        self.assertIsNone(f["budge"])
        self.assertEqual(f["status"], "playing")

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_renders_budging_block_and_straining_jolly(self):
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'H'", js)
        self.assertIn("heavy-block-budging.png", js)
        self.assertIn("jolly-straining.png", js)
        self.assertIn("jolly-pushing-heavy.png", js)


class BlockedByIntegrationTests(unittest.TestCase):
    """Explicit skips: the rules run for real on pack stand-ins
    above; only the cross-mechanic integrations wait on main."""

    def test_weight_switch_integration(self):
        self.skipTest("blocked-by: 29 (weight switch) — no weight "
                      "switch on main; switch plate/gate stand-in "
                      "exercised for real in HeavyBlockMechanicTests")

    def test_patroller_integration(self):
        self.skipTest("blocked-by: 31 (patroller) — no patroller on "
                      "main; pack patroller stand-in exercised for "
                      "real in HeavyBlockMechanicTests")

    def test_power_gloves_and_real_hazard_tiles_integration(self):
        self.skipTest("blocked-by: 89 (power gloves), 41/43/44 "
                      "(deep water/fire/lava) — not on main; gloves "
                      "and hazard stand-ins exercised for real in "
                      "HeavyBlockMechanicTests")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = [...Array(4).fill('wait'), ...Array(11).fill('right'),
  'up', 'right', 'right', 'right', 'down', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-87-heavy-block-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-87-heavy-block-room', log);
const replayed2 = core.replay(level, 'mech-87-heavy-block-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
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
                         {"pos": {"x": 12, "y": 2}, "status": "won",
                          "orbs": 0})
        self.assertEqual(self.r["replaySteps"], 22)


if __name__ == "__main__":
    unittest.main()
