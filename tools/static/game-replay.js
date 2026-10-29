// Replay helpers: pure functions over recorded session JSONL records.
// Annotations and the end line are ignored for state; playback timing
// uses recorded t_ms spacing scaled only by viewer speed (1x/2x/5x/10x,
// no idle-gap compression, so the timer reads exactly as recorded).
(function (root) {
  'use strict';
  function stepsOf(records) {
    return (records || []).filter((r) => r.type === 'step');
  }
  function stepIndexAtTime(records, tSeconds) {
    const target = Number(tSeconds) * 1000;
    let idx = 0;
    const steps = stepsOf(records);
    for (let i = 0; i < steps.length; i++) {
      if (steps[i].t_ms <= target) idx = i + 1; else break;
    }
    return idx;
  }
  function buildStates(core, level, levelName, records) {
    const log = stepsOf(records).map((s) => ({ t_ms: s.t_ms, input: s.input }));
    return core.replay(level, levelName, log);
  }
  function stateAt(core, level, levelName, records, index) {
    const states = buildStates(core, level, levelName, records);
    const i = Math.max(0, Math.min(index, states.length - 1));
    return { state: states[i], states: states, index: i };
  }
  // Delay before step `index` (1-based) at a viewer speed, from t_ms gaps.
  function delayMs(records, index, speed) {
    const steps = stepsOf(records);
    if (index < 1 || index > steps.length) return 0;
    const prev = index === 1 ? 0 : steps[index - 2].t_ms;
    return Math.max(0, (steps[index - 1].t_ms - prev) / (speed || 1));
  }
  function warnings(header, currentLevelHash, currentEngine, currentCommit, levelHashFn, levelData) {
    const out = [];
    const recHash = header && header.level_source && header.level_source.hash;
    const curHash = currentLevelHash ||
      (levelHashFn && levelData ? levelHashFn(levelData) : null);
    if (curHash && recHash && curHash !== recHash) {
      out.push('level mismatch: recorded level hash ' + recHash +
        ' != current ' + curHash + '; replay may diverge');
    }
    const recEngine = header && header.engine_version;
    if (recEngine && currentEngine && recEngine !== currentEngine) {
      out.push('engine mismatch: recorded ' + recEngine +
        ' != current ' + currentEngine + '; replay may diverge');
    }
    if (!recEngine) out.push('no engine version recorded; replay may diverge');
    const recCommit = header && header.commit;
    if (currentCommit && recCommit && currentCommit !== recCommit) {
      out.push('commit mismatch: recorded ' + recCommit +
        ' != current ' + currentCommit);
    }
    return out;
  }
  const api = { stepsOf, stepIndexAtTime, buildStates, stateAt, delayMs, warnings };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameReplay = api;
})(typeof window !== 'undefined' ? window : globalThis);
