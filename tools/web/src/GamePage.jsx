import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';

// Operator layout for replay/session debugging (review-fixes-5).
// Context bar (what am I looking at) / viewport (never overlaid) /
// step inspector (state + annotate + fork at the shown step) / one
// unified transport timeline. Filters and diagnostics stay behind
// disclosures. Intent: a reviewer at midnight pinpointing one bad
// move; feel: dense, quiet, terminal-like. Focal point: the game.
const btn = 'rounded border border-neutral-700 bg-neutral-800 px-2.5 py-1 text-[13px] text-neutral-100 hover:bg-neutral-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400 disabled:opacity-40';
const btnPrimary = btn + ' border-sky-700 bg-sky-800 hover:bg-sky-700';
const input = 'w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-[13px] text-neutral-100 placeholder:text-neutral-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400';
const chip = 'rounded bg-neutral-800 px-1.5 py-0.5 text-[11px] text-neutral-300';
function fmtClock(s) {
  if (s === null || s === undefined || isNaN(s)) return '—';
  const v = Math.max(0, Math.round(s));
  return Math.floor(v / 60) + ':' + String(v % 60).padStart(2, '0');
}
function fmtLeft(s) {
  if (s === null || s === undefined || isNaN(s)) return '—';
  const v = Math.max(0, Math.floor(s));
  return Math.floor(v / 60) + ':' + String(v % 60).padStart(2, '0');
}

export default function GamePage() {
  const params = new URLSearchParams(location.search);
  const [level, setLevel] = useState(params.get('level') || 'movement-room');
  const [levels, setLevels] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState(params.get('replay') || '');
  const [replay, setReplay] = useState(null);
  const [live, setLive] = useState(null);
  const [clock, setClock] = useState(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(
    () => window.innerWidth >= 1100);
  const [hideEmpty, setHideEmpty] = useState(true);
  const [q, setQ] = useState('');
  const [label, setLabel] = useState('');
  const [creator, setCreator] = useState('');
  const [feature, setFeature] = useState('');
  const [date, setDate] = useState('');
  const [result, setResult] = useState('');
  const [speed, setSpeed] = useState('1');
  const [note, setNote] = useState('');
  const [noteLabels, setNoteLabels] = useState('');
  const [status, setStatus] = useState('');
  const frameRef = useRef(null);
  const frameSrc = '/static/game.html?embed=1&level=' + encodeURIComponent(level) +
    (params.get('replay') ? '&replay=' + encodeURIComponent(params.get('replay')) : '') +
    (params.get('t') ? '&t=' + encodeURIComponent(params.get('t')) : '') +
    (params.get('fork') ? '&fork=' + encodeURIComponent(params.get('fork')) : '');

  useEffect(() => {
    const onResize = () => { if (window.innerWidth < 900) setInspectorOpen(false); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  const game = useCallback(() => frameRef.current && frameRef.current.contentWindow &&
    frameRef.current.contentWindow.__game, []);
  const current = sessions.find((s) => s.id === selected) || null;
  const active = !!(replay && replay.active);
  const orbs = live && live.grid ? live.grid.join('').split('').filter((c) => c === '*' || c === 'O').length : null;
  const runStatus = (live && live.status) || (clock && clock.status) || 'playing';

  useEffect(() => {
    api('GET', '/api/game/levels').then((d) =>
      setLevels((d.levels || []).filter((l) => l.test))).catch(() => {});
  }, []);
  useEffect(() => {
    const id = setInterval(() => {
      const g = game();
      if (!g) return;
      if (g.getReplay) setReplay(g.getReplay());
      if (g.getState) { try { setLive(g.getState()); } catch (e) { /* mid-navigation */ } }
      if (g.getClock) { try { setClock(g.getClock()); } catch (e) { /* mid-navigation */ } }
    }, 100);
    return () => clearInterval(id);
  }, [game]);

  const refresh = useCallback(async () => {
    const qs = new URLSearchParams({ level });
    if (q) qs.set('q', q);
    if (label) qs.set('label', label);
    if (creator) qs.set('creator', creator);
    if (feature) qs.set('feature', feature);
    if (date) qs.set('date', date);
    if (result) qs.set('result', result);
    try {
      const d = await api('GET', '/api/game/sessions?' + qs.toString());
      setSessions(d.sessions || []);
    } catch (e) { setStatus(e.message); }
  }, [level, q, label, creator, feature, date, result]);
  useEffect(() => { refresh(); }, [refresh]);

  const visible = sessions.filter((s) => !hideEmpty || s.steps > 0);
  function openSession(id) {
    setSelected(id);
    const g = game();
    if (g && g.loadReplay) g.loadReplay(id);
  }
  async function annotate() {
    if (!selected) { setStatus('Pick a session first.'); return; }
    try {
      await api('POST', '/api/game/sessions/' + encodeURIComponent(selected) + '/annotations',
        { author: 'human', body: note, labels: noteLabels,
          step: active ? replay.index : null });
      setStatus('Annotation added to ' + selected + ' at step ' + (active ? replay.index : '—'));
      setNote(''); setNoteLabels(''); refresh();
    } catch (e) { setStatus(e.message); }
  }
  async function fork() {
    const g = game();
    if (!g || !g.forkFromReplay) return;
    const newId = await g.forkFromReplay();
    if (newId) location.search = '?level=' + encodeURIComponent(level) + '&fork=' + encodeURIComponent(newId);
  }
  // Parent-side replay keys (iframe keys are handled in game.js).
  useEffect(() => {
    const onKey = (ev) => {
      if (/INPUT|TEXTAREA|SELECT|BUTTON/.test(ev.target.tagName)) return;
      const g = game();
      if (!g) return;
      if (!replay || !replay.active) {
        if ((ev.key === 'r' || ev.key === 'R') && g.restart) {
          ev.preventDefault(); g.restart();
        }
        return;
      }
      if (ev.key === ' ') { ev.preventDefault(); g.togglePlay(); }
      else if (ev.key === 'ArrowLeft') { ev.preventDefault(); g.pauseReplay(); g.showReplay(replay.index - (ev.shiftKey ? 10 : 1)); }
      else if (ev.key === 'ArrowRight') { ev.preventDefault(); g.pauseReplay(); g.showReplay(replay.index + (ev.shiftKey ? 10 : 1)); }
      else if (ev.key === 'Home') { ev.preventDefault(); g.showReplay(0); }
      else if (ev.key === 'End') { ev.preventDefault(); g.showReplay(replay.steps); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [game, replay]);

  return (
    <div className="flex h-screen flex-col bg-neutral-950 text-neutral-100">
      <header className="flex h-11 shrink-0 items-center gap-2 overflow-hidden whitespace-nowrap border-b border-neutral-800 px-3">
        <button type="button" className={btn} aria-expanded={pickerOpen}
          onClick={() => setPickerOpen(!pickerOpen)}>Sessions</button>
        <select aria-label="Level" className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-[13px]"
          value={level} onChange={(e) => { location.search = '?level=' + encodeURIComponent(e.target.value); }}>
          {levels.map((l) => <option key={l.id} value={l.id}>{l.name || l.id}</option>)}
        </select>
        {selected ? (
          <span className="flex min-w-0 items-center gap-1.5">
            <strong className="truncate text-[13px]">{selected}</strong>
            {current && <span className={chip}>{current.steps} steps</span>}
            {current && <span className={chip}>{current.duration_s}s</span>}
            {current && <span className={chip}>{current.created_by}</span>}
            {current && <span className={chip}>{current.result || 'open'}</span>}
          </span>
        ) : <span className="text-[13px] text-neutral-400">No session loaded — open Sessions and pick a recording.</span>}
        <span className="flex-1" />
        <span className="text-[12px] text-neutral-400" role="status" aria-live="polite">{status}</span>
        <button type="button" className={btn} aria-expanded={inspectorOpen}
          onClick={() => setInspectorOpen(!inspectorOpen)}>Inspector</button>
        <button type="button" className={btn} onClick={async () => {
          try {
            const shot = await api('POST', '/api/game/screenshot', {
              level, replay: selected || undefined,
              t: live ? live.t_ms / 1000 : undefined,
              width: window.innerWidth, height: window.innerHeight });
            setStatus('Screenshot saved: ' + shot.path);
            window.open(shot.url, '_blank');
          } catch (e) { setStatus('Screenshot failed: ' + e.message); }
        }}>Screenshot</button>
        <a className="text-[13px] text-neutral-400 hover:underline" href="/pm">Project Manager</a>
      </header>
      {active && replay.warning && (
        <div className="shrink-0 bg-amber-900/60 px-3 py-1 text-[12px] text-amber-200" role="alert">{replay.warning}</div>
      )}
      <div className="flex min-h-0 flex-1">
        {pickerOpen && (
          <aside aria-label="Session picker" className="flex w-[min(320px,38vw)] shrink-0 flex-col gap-2 overflow-y-auto border-r border-neutral-800 p-3">
            <input className={input} placeholder="Search session id" aria-label="Search session id"
              value={q} onChange={(e) => setQ(e.target.value)} />
            <input className={input} placeholder="Label (e.g. bug)" aria-label="Label filter"
              value={label} onChange={(e) => setLabel(e.target.value)} />
            <label className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={hideEmpty} onChange={(e) => setHideEmpty(e.target.checked)} />
              Hide empty (0-step) sessions
            </label>
            <details>
              <summary className="cursor-pointer text-[13px]">More filters</summary>
              <div className="mt-2 flex flex-col gap-2">
                <select className={input} aria-label="Creator" value={creator} onChange={(e) => setCreator(e.target.value)}>
                  <option value="">any creator</option><option>human</option><option>agent</option>
                </select>
                <input className={input} placeholder="Feature" aria-label="Feature" value={feature} onChange={(e) => setFeature(e.target.value)} />
                <input className={input} type="date" aria-label="Date" value={date} onChange={(e) => setDate(e.target.value)} />
                <input className={input} placeholder="Result (e.g. quit)" aria-label="Result" value={result} onChange={(e) => setResult(e.target.value)} />
              </div>
            </details>
            <button type="button" className={btn} onClick={refresh}>Apply filters</button>
            <ul className="flex flex-col gap-1">
              {visible.map((s) => (
                <li key={s.id}>
                  <button type="button" aria-current={s.id === selected}
                    className={(s.id === selected ? btnPrimary : btn) + ' w-full text-left'}
                    onClick={() => openSession(s.id)}>
                    <span className="block break-all text-[12px]">{s.id}</span>
                    <span className="block text-[11px] opacity-80 [font-variant-numeric:tabular-nums]">
                      {s.steps} steps · {s.duration_s}s · {s.created_by} · {s.result || 'open'}
                      {s.labels && s.labels.length ? ' · [' + s.labels.join(', ') + ']' : ''}
                    </span>
                  </button>
                </li>
              ))}
              {!visible.length && <li className="text-[13px] text-neutral-400">No sessions for {level} — play a few moves first, or untick Hide empty.</li>}
            </ul>
          </aside>
        )}
        <main className="relative min-w-0 flex-1 bg-black">
          <iframe ref={frameRef} title="Game" src={frameSrc}
            className="absolute inset-0 h-full w-full border-0" style={{ width: '100%', height: '100%' }} />
        </main>
        {inspectorOpen && (
          <aside aria-label="Step inspector" className="flex w-[min(300px,34vw)] shrink-0 flex-col gap-3 overflow-y-auto border-l border-neutral-800 p-3">
            <h2 className="text-[13px] font-semibold tracking-wide text-neutral-300">STEP INSPECTOR</h2>
            {active && live ? (
              <>
                <p className="text-[22px] font-semibold leading-none [font-variant-numeric:tabular-nums]">
                  Step {replay.index}<span className="text-[14px] text-neutral-400">/{replay.steps}</span>
                </p>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px] [font-variant-numeric:tabular-nums]">
                  <dt className="text-neutral-400">t</dt><dd>{live.t_ms} ms ({live.elapsed_s}s)</dd>
                  <dt className="text-neutral-400">Input</dt><dd>{String(live.last_input)}</dd>
                  <dt className="text-neutral-400">Position</dt><dd>{live.player.x}, {live.player.y}</dd>
                  <dt className="text-neutral-400">Inventory</dt><dd>[]</dd>
                  <dt className="text-neutral-400">Orbs left</dt><dd>{orbs}</dd>
                  <dt className="text-neutral-400">Timer</dt><dd>{fmtLeft(live.time_left_s)} left of {fmtClock(live.time_limit_s)}</dd>
                  <dt className="text-neutral-400">Run</dt><dd>{runStatus}</dd>
                  <dt className="text-neutral-400">State</dt><dd>{replay.playing ? 'playing' : 'paused'}</dd>
                </dl>
                <details>
                  <summary className="cursor-pointer text-[13px] text-neutral-400">Diagnostics</summary>
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-[11px] text-neutral-400">{replay.readout}{'\n'}{JSON.stringify(live)}</pre>
                </details>
                <div className="flex flex-col gap-2 border-t border-neutral-800 pt-3">
                  <h3 className="text-[13px] font-semibold">Annotate this step</h3>
                  <input className={input} placeholder="Note" aria-label="Annotation note" value={note} onChange={(e) => setNote(e.target.value)} />
                  <input className={input} placeholder="Labels (bug, failed)" aria-label="Annotation labels" value={noteLabels} onChange={(e) => setNoteLabels(e.target.value)} />
                  <button type="button" className={btnPrimary} onClick={annotate}>Add annotation at step {replay.index}</button>
                  {current && current.labels && current.labels.length > 0 && <p className="text-[12px] text-neutral-400">Labels: {current.labels.join(', ')}</p>}
                </div>
                <button type="button" className={btn} onClick={fork}>Fork from step {replay.index}</button>
              </>
            ) : (
              <p className="text-[13px] text-neutral-400">No replay loaded. Pick a session from Sessions; the step you land on is inspected here, with annotate and fork bound to it.</p>
            )}
          </aside>
        )}
      </div>
      <footer className="flex h-14 shrink-0 items-center gap-2 border-t border-neutral-800 px-3"
        title="Space play/pause · ←/→ step · Shift+←/→ jump 10 · Home/End">
        <button type="button" className={btn} disabled={!active}
          onClick={() => { const g = game(); if (g) { g.pauseReplay(); g.showReplay(replay.index - 1); } }}>Step back</button>
        <button type="button" className={btnPrimary} disabled={!active}
          onClick={(e) => { e.currentTarget.blur(); const g = game(); if (g) g.togglePlay(); }}>
          {active && replay.playing ? 'Pause' : 'Play'}
        </button>
        <button type="button" className={btn} disabled={!active}
          onClick={() => { const g = game(); if (g) { g.pauseReplay(); g.showReplay(replay.index + 1); } }}>Step forward</button>
        <span className="text-[12px] text-neutral-400">{active ? (replay.playing ? 'playing' : 'paused') : 'no replay'}</span>
        <div role="slider" aria-label="Timeline" aria-valuemin="0"
          aria-valuemax={active ? Math.round(replay.duration_ms / 1000) : 0}
          aria-valuenow={active && live ? Math.round(live.t_ms / 1000) : 0}
          tabIndex={0} className="relative h-8 min-w-24 flex-1 cursor-pointer"
          onPointerDown={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const seek = (x) => { const g = game(); if (g && active) g.seekTime(Math.min(1, Math.max(0, (x - rect.left) / rect.width)) * replay.duration_ms / 1000); };
            seek(e.clientX);
            const move = (ev) => seek(ev.clientX);
            const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
            window.addEventListener('pointermove', move);
            window.addEventListener('pointerup', up);
          }}>
          <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded bg-neutral-700" />
          {active && replay.duration_ms > 0 && (<>
            <div className="absolute top-1/2 h-1 -translate-y-1/2 rounded bg-sky-500"
              style={{ width: ((replay.playing ? replay.playhead_ms : (live ? live.t_ms : 0)) / replay.duration_ms * 100) + '%' }} />
            {replay.step_times.map((ms, i) => (
              <span key={i} title={'Step ' + (i + 1) + ' at ' + (ms / 1000) + 's'}
                className="absolute top-1/2 h-3 w-0.5 -translate-x-1/2 -translate-y-1/2 bg-sky-200"
                style={{ left: (ms / replay.duration_ms * 100) + '%' }} />
            ))}
            <div className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky-400 shadow"
              style={{ left: ((replay.playing ? replay.playhead_ms : (live ? live.t_ms : 0)) / replay.duration_ms * 100) + '%' }} />
          </>)}
        </div>
        <span className="text-[13px] [font-variant-numeric:tabular-nums]">{active ? 'Step ' + replay.index + '/' + replay.steps : 'Step —'}</span>
        <span className="text-[13px] [font-variant-numeric:tabular-nums]">{active && live ? fmtClock(live.t_ms / 1000) + ' / ' + fmtClock(replay.duration_ms / 1000) : ''}</span>
        <span className={chip} title="Countdown from max time">{active && live ? '⏱ ' + fmtLeft(Math.max(0, live.time_limit_s - (replay.playing ? replay.playhead_ms / 1000 : live.elapsed_s))) + ' / ' + fmtClock(live.time_limit_s) : (clock ? '⏱ ' + fmtLeft(clock.time_left_s) + ' / ' + fmtClock(clock.time_limit_s) : '⏱ —')}</span>
        <select aria-label="Speed" className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-[13px]"
          value={speed} onChange={(e) => { setSpeed(e.target.value); const g = game(); if (g && g.setReplaySpeed) g.setReplaySpeed(e.target.value); }}>
          <option value="1">1x</option><option value="2">2x</option><option value="5">5x</option><option value="10">10x</option>
        </select>
      </footer>
    </div>
  );
}
