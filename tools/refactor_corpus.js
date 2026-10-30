// Refactor regression corpus driver (Phase 0).
// Replays a fixed seeded input log on every level and prints the
// per-step observable readout sequence as JSON. Used to generate
// tools/refactor_golden.json and by tools/test_refactor_regression.py.
// Observable readout only (position/inventory/orbs/gate/status/timer):
// raw digests are version-scoped and checked for determinism in-test.
'use strict';
const fs = require('fs');
const path = require('path');
const core = require(path.join(__dirname, 'static', 'game-core.js'));

const DIRS = ['up', 'right', 'down', 'left'];
function seededLog(n) {
  // Deterministic LCG; same log for every level and every run.
  let s = 0x12345678;
  const log = [];
  for (let i = 0; i < n; i++) {
    s = (Math.imul(s, 1103515245) + 12345) >>> 0;
    log.push({ t_ms: i * 250, input: DIRS[(s >>> 16) % 4] });
  }
  return log;
}
function round(v) { return typeof v === 'number' ? Math.round(v * 1000) / 1000 : v; }

const levelsDir = path.join(__dirname, '..', 'levels');
const out = {};
for (const name of fs.readdirSync(levelsDir).filter((f) => f.endsWith('.json')).sort()) {
  const level = JSON.parse(fs.readFileSync(path.join(levelsDir, name), 'utf8'));
  const id = name.replace(/\.json$/, '');
  const states = core.replay(level, id, seededLog(60));
  out[id] = states.map((st) => {
    const r = core.readout(st);
    return { pos: r.position, inv: r.inventory, orbs: r.orbs_left,
      gate: r.gate_open, status: r.status, next: r.next_level,
      left: round(r.time_left_s), steps: r.step };
  });
}
console.log(JSON.stringify(out, null, 1));
