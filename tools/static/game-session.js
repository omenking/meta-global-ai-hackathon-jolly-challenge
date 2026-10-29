// Session recorder: builds the JSONL session file for one play.
//
// Layout (fixed by the project-manager plan): header line
// {type:"session", id, created_at, created_by, label, level,
//  level_source:{file,hash}, feature, task, branch, commit}, one
// {type:"step", n, t_ms, input} per step, and a closing
// {type:"end", result, steps, orbs_left, time_left}. Annotations may
// be appended later; replay ignores them.
(function (root) {
  'use strict';

  function levelHash(level) {
    const text = JSON.stringify(level);
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return ('0000000' + h.toString(16)).slice(-8);
  }

  function createRecorder(opts) {
    const header = {
      type: 'session',
      id: opts.id,
      created_at: opts.created_at,
      created_by: opts.created_by || 'human',
      label: opts.label || '',
      level: opts.level,
      level_source: { file: opts.level_file || '', hash: levelHash(opts.level_data || {}) },
      feature: opts.feature || null,
      task: opts.task || null,
      branch: opts.branch || null,
      commit: opts.commit || null,
      engine_version: opts.engine_version || 'game-core-1',
      forked_by: opts.forked_by || null,
      forked_from: opts.forked_from || null,
      fork_step: (opts.fork_step === undefined ? null : opts.fork_step),
    };
    const lines = [header];
    let ended = false;
    return {
      header: header,
      recordStep: function (n, tMs, input) {
        if (ended) throw new Error('session already ended');
        lines.push({ type: 'step', n: n, t_ms: tMs, input: input });
      },
      end: function (result, extra) {
        if (ended) return;
        ended = true;
        const e = extra || {};
        lines.push({
          type: 'end', result: result,
          steps: lines.filter((l) => l.type === 'step').length,
          orbs_left: e.orbs_left === undefined ? null : e.orbs_left,
          time_left: e.time_left === undefined ? null : e.time_left,
        });
      },
      isEnded: function () { return ended; },
      toJSONL: function () {
        return lines.map((l) => JSON.stringify(l)).join('\n') + '\n';
      },
    };
  }

  const api = { createRecorder, levelHash };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.GameSession = api;
})(typeof window !== 'undefined' ? window : globalThis);
