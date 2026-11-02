"""Checks for the info tile (mech-58-info-tile).

The mechanic lives in the pure GameCore step (packs/info-tile);
driven here under Node against the teaching room. Rules: stepping
on the marked tile shows its one-line banner once and does nothing
else; it never blocks movement; later steps in the same attempt
show nothing. Restart (fresh state) restores the untriggered tile.

The two YAML cases that press chain switches in the banner's
order are blocked-by mechanic 28 (chain switch), which is not
built on main: they are explicit skipped-with-reason checks here,
never fake passes. The room realises the same naive-fails /
corrected-succeeds teaching shape with the core gate and chips,
and those plays are checked for real below.

Run with: python -m unittest tools.test_mech_58_info_tile -v
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

LEVEL_ID = "mech-58-info-tile-room"
PACK = ROOT / "tools" / "static" / "packs" / "info-tile"
BANNER = ("Collect both chips first - the gate only opens "
          "when none are left.")


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class InfoRoomLevelTests(unittest.TestCase):
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

        def at(ch):
            return [(x, y) for y, r in enumerate(rows)
                    for x, c in enumerate(r) if c == ch]

        spawn, info, gate, warp = at("P")[0], at("i")[0], at("G")[0], at("X")[0]
        # The info tile sits on the direct spawn-to-gate route.
        self.assertEqual(info[1], spawn[1])
        self.assertLess(spawn[0], info[0])
        self.assertLess(info[0], gate[0])
        self.assertGreater(warp[0], gate[0])
        # Both chips are on the spawn side of the gate, off the
        # direct row, so ignoring the banner fails at the shut gate.
        orbs = at("*")
        self.assertEqual(len(orbs), 2)
        self.assertTrue(all(x < gate[0] for x, _ in orbs))
        self.assertTrue(all(y != spawn[1] for _, y in orbs))
        # The banner line is level data on the info legend entry.
        entry = self.level["legend"]["i"]
        self.assertEqual(entry["def"], "info:tile")
        self.assertEqual(entry["banner"], BANNER)


class InfoPackFolderTests(unittest.TestCase):
    def test_manifest_mirrors_the_yaml_assets(self):
        manifest = json.loads((PACK / "manifest.json").read_text(
            encoding="utf-8"))
        self.assertEqual(manifest["pack"], "info-tile")
        self.assertEqual(manifest["main"], "main.js")
        self.assertEqual(
            [(a["file"], a["kind"], a["bundled"]) for a in manifest["assets"]],
            [("info.png", "tiles", True),
             ("info-read.png", "tiles", True),
             ("info-banner.png", "gui", True)])

    def test_bundled_assets_exist_and_are_512_pngs(self):
        for name in ("info.png", "info-read.png", "info-banner.png"):
            path = PACK / "assets" / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(_png_size(path), (512, 512), name)

    def test_pack_reads_no_wall_clock(self):
        js = (PACK / "main.js").read_text(encoding="utf-8")
        self.assertNotIn("Date.now", js)
        self.assertNotIn("performance.now", js)


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
  let s = core.initialState(level, 'mech-58-info-tile-room');
  const snap = () => ({ pos: { ...s.player }, status: s.status,
    orbs: core.readout(s).orbs_left,
    shown: s.counters['info:shown'] || 0,
    read: !!((s.meta['3,1'] || {}).info_read),
    banner: (s.meta['3,1'] || {}).banner || null,
    inv: core.readout(s).inventory.length, row: s.grid[1] });
  const snaps = [snap()];
  seq.forEach((input, i) => {
    s = core.step(s, { t_ms: (i + 1) * 100, input });
    snaps.push(snap());
  });
  return snaps;
}
// A: corrected route - read the banner, collect both chips, exit.
const a = run(['right', 'right', 'down', 'down', 'right', 'right',
  'down', 'down', 'up', 'up', 'up', 'up',
  'right', 'right', 'right', 'right', 'right', 'right']);
// B: adversarial - step over the tile unread, straight to the gate.
const b = run(['right', 'right', 'right', 'right', 'right', 'right',
  'right', 'left']);
// C: once-per-tile - on, off, back on, across and back again.
const c = run(['right', 'right', 'right', 'left', 'left', 'left',
  'right', 'right']);
// Purity: stepping must not mutate the state it was given.
const s0 = core.initialState(level, 'mech-58-info-tile-room');
const before = JSON.stringify(s0);
core.step(s0, { t_ms: 100, input: 'right' });
console.log(JSON.stringify({
  a: a, b: b, c: c,
  fresh: { shown: s0.counters['info:shown'] || 0,
    read: !!((s0.meta['3,1'] || {}).info_read), row: s0.grid[1] },
  pure: JSON.stringify(s0) === before,
}));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class InfoMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core(BEHAVIOUR_SCRIPT)

    def test_first_step_shows_the_banner_and_nothing_else(self):
        c = self.r["c"]
        # snaps[2] stands on the info tile after two steps right.
        self.assertEqual(c[2]["pos"], {"x": 3, "y": 1})
        self.assertEqual(c[2]["shown"], 1)
        self.assertTrue(c[2]["read"])
        self.assertEqual(c[2]["banner"], "Collect both chips first"
                         " - the gate only opens when none are left.")
        # Does nothing else: no chip, item, win or loss side effects.
        self.assertEqual(c[2]["orbs"], 2)
        self.assertEqual(c[2]["inv"], 0)
        self.assertEqual(c[2]["status"], "playing")

    def test_once_per_tile_and_never_blocks(self):
        c = self.r["c"]
        # Off the tile and back on: no second banner.
        self.assertEqual(c[3]["pos"], {"x": 4, "y": 1})
        self.assertEqual(c[4]["pos"], {"x": 3, "y": 1})
        self.assertEqual(c[4]["shown"], 1)
        # Straight across in both directions, one tile per step.
        self.assertEqual(c[5]["pos"], {"x": 2, "y": 1})
        self.assertEqual(c[6]["pos"], {"x": 1, "y": 1})
        self.assertEqual(c[7]["pos"], {"x": 2, "y": 1})
        self.assertEqual(c[8]["pos"], {"x": 3, "y": 1})
        self.assertEqual(c[8]["shown"], 1)
        self.assertEqual(c[8]["status"], "playing")
        self.assertEqual(c[8]["row"], "#P.i....G..X#")

    def test_corrected_route_collects_then_exits(self):
        a = self.r["a"]
        self.assertEqual(a[2]["shown"], 1)
        self.assertEqual(a[4]["orbs"], 1)
        self.assertEqual(a[8]["orbs"], 0)
        final = a[-1]
        self.assertEqual(final["pos"], {"x": 11, "y": 1})
        self.assertEqual(final["status"], "won")

    def test_adversarial_straight_to_the_gate_fails_but_never_strands(self):
        b = self.r["b"]
        # snaps[7] pushed into the shut gate and stayed put, still
        # playing with both chips uncollected - the failure the
        # teaching moment warns about, with a way back.
        self.assertEqual(b[6]["pos"], {"x": 7, "y": 1})
        self.assertEqual(b[7]["pos"], {"x": 7, "y": 1})
        self.assertEqual(b[7]["orbs"], 2)
        self.assertEqual(b[7]["status"], "playing")
        self.assertEqual(b[8]["pos"], {"x": 6, "y": 1})

    def test_restart_restores_the_untriggered_tile(self):
        self.assertEqual(self.r["fresh"],
                         {"shown": 0, "read": False, "row": "#P.i....G..X#"})

    def test_step_is_pure(self):
        self.assertTrue(self.r["pure"])

    def test_game_wires_the_info_pack(self):
        html = (ROOT / "tools" / "static" / "game.html").read_text(
            encoding="utf-8")
        self.assertIn("packs/info-tile/main.js", html)
        js = (ROOT / "tools" / "static" / "game.js").read_text(
            encoding="utf-8")
        self.assertIn("dt.ch === 'i'", js)
        self.assertIn("info-banner", js)


class BlockedByChainSwitchTests(unittest.TestCase):
    """YAML cases whose play needs mechanic 28 (chain switch).

    The chain-switch pack is not built on main, so these are
    explicit skipped-with-reason checks. The assertions below
    prove the blocker is real; if the pack lands, they fail and
    the real plays must be written instead of the skips.
    """

    def _assert_blocked(self):
        self.assertFalse(
            (ROOT / "tools" / "static" / "packs" / "chain-switch").exists(),
            "chain-switch pack now exists: replace the skip with a real play")

    def test_solution_read_then_press_in_order(self):
        self._assert_blocked()
        self.skipTest("blocked-by: 28 (chain switch) - pressing the "
                      "chain switches in the banner's order needs the "
                      "chain-switch pack, not built on main")

    def test_adversarial_step_over_without_reading(self):
        self._assert_blocked()
        self.skipTest("blocked-by: 28 (chain switch) - pressing the "
                      "switches in reach order to reset the chain "
                      "needs the chain-switch pack, not built on main")


SANITY_SCRIPT = r"""
const core = require(process.argv[1]);
const level = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const inputs = ['right', 'right', 'down', 'down', 'right', 'right',
  'down', 'down', 'up', 'up', 'up', 'up',
  'right', 'right', 'right', 'right', 'right', 'right'];
const log = inputs.map((input, i) => ({ t_ms: (i + 1) * 100, input }));
let live = core.initialState(level, 'mech-58-info-tile-room');
for (const stepIn of log) live = core.step(live, stepIn);
const replayed = core.replay(level, 'mech-58-info-tile-room', log);
const replayed2 = core.replay(level, 'mech-58-info-tile-room',
  JSON.parse(JSON.stringify(log)));
console.log(JSON.stringify({
  liveFinal: { pos: { ...live.player }, status: live.status,
    orbs: core.readout(live).orbs_left,
    shown: live.counters['info:shown'] || 0 },
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
                         {"pos": {"x": 11, "y": 1}, "status": "won",
                          "orbs": 0, "shown": 1})
        self.assertEqual(self.r["replaySteps"], 18)


if __name__ == "__main__":
    unittest.main()
