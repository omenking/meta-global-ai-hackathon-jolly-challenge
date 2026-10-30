"""Phase 0 regression corpus for the engine refactor.

Replays a fixed seeded log on every level via tools/refactor_corpus.js
and asserts the per-step observable readout matches the golden file
captured from the pre-refactor core. Also asserts replay determinism
(same log -> same digest sequence) within the current engine version.
Golden readout (not raw digests) is the cross-version contract.

Run with: python -m unittest tools.test_refactor_regression -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "tools" / "refactor_corpus.js"
GOLDEN = ROOT / "tools" / "refactor_golden.json"
CORE = ROOT / "tools" / "static" / "game-core.js"

DETERMINISM = """
const core = require(process.argv[1]);
const fs = require('fs');
const level = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const dirs = ['up','right','down','left'];
let s = 0x12345678; const log = [];
for (let i = 0; i < 60; i++) { s = (Math.imul(s, 1103515245) + 12345) >>> 0;
  log.push({ t_ms: i * 250, input: dirs[(s >>> 16) % 4] }); }
const a = core.replay(level, 'chip1', log).map(core.stateDigest);
const b = core.replay(level, 'chip1', JSON.parse(JSON.stringify(log))).map(core.stateDigest);
console.log(JSON.stringify({ same: JSON.stringify(a) === JSON.stringify(b) }));
"""


@unittest.skipUnless(shutil.which("node"), "node not available")
class RefactorRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(DRIVER)], capture_output=True,
                             text=True, check=True)
        cls.actual = json.loads(out.stdout)

    def test_corpus_matches_golden_readout(self):
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(sorted(golden), sorted(self.actual),
                         "level set changed; regenerate golden deliberately")
        for level_id, expected in golden.items():
            self.assertEqual(expected, self.actual[level_id],
                             f"observable readout diverged on {level_id}")

    def test_replay_is_deterministic(self):
        out = subprocess.run(
            ["node", "-e", DETERMINISM, str(CORE),
             str(ROOT / "levels" / "chip1.json")],
            capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(out.stdout.strip().splitlines()[-1])["same"])


if __name__ == "__main__":
    unittest.main()
