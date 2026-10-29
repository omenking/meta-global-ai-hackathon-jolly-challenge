import { Button, Card, Chip } from '@heroui/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';

// Fullscreen game canvas with the outside-game UI as a HeroUI overlay.
// Header and footer take real layout space; the canvas fills the rest.
// The side panel is fixed, collapsed by default and scrolls internally.
// Its top block is always the current session: which recording is
// loaded, how long it is, playback controls, and annotate directly
// under it — annotation never lives at the bottom of the panel.
export default function GamePage() {
  const params = new URLSearchParams(location.search);
  const [level, setLevel] = useState(params.get('level') || 'movement-room');
  const [levels, setLevels] = useState([]);
  const [collapsed, setCollapsed] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [q, setQ] = useState('');
  const [label, setLabel] = useState('');
  const [creator, setCreator] = useState('');
  const [feature, setFeature] = useState('');
  const [date, setDate] = useState('');
  const [result, setResult] = useState('');
  const [selected, setSelected] = useState(params.get('replay') || '');
  const [replay, setReplay] = useState(null);
  const [speed, setSpeed] = useState('1');
  const [note, setNote] = useState('');
  const [noteLabels, setNoteLabels] = useState('');
  const [status, setStatus] = useState('');
  const frameRef = useRef(null);
  const frameSrc = '/static/game.html?embed=1&level=' +
    encodeURIComponent(level) +
    (params.get('replay') ? '&replay=' + encodeURIComponent(params.get('replay')) : '') +
    (params.get('t') ? '&t=' + encodeURIComponent(params.get('t')) : '') +
    (params.get('fork') ? '&fork=' + encodeURIComponent(params.get('fork')) : '');

  useEffect(() => {
    api('GET', '/api/game/levels').then((d) =>
      setLevels((d.levels || []).filter((l) => l.test))).catch(() => {});
  }, []);

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

  useEffect(() => {
    const id = setInterval(() => {
      const w = frameRef.current && frameRef.current.contentWindow;
      if (w && w.__game && w.__game.getReplay) setReplay(w.__game.getReplay());
    }, 300);
    return () => clearInterval(id);
  }, []);

  const game = () => frameRef.current && frameRef.current.contentWindow &&
    frameRef.current.contentWindow.__game;
  const current = sessions.find((s) => s.id === selected) || null;
  function openSession(id) {
    setSelected(id);
    const g = game();
    if (g && g.loadReplay) g.loadReplay(id);
  }
  async function annotate() {
    if (!selected) { setStatus('Pick a session first.'); return; }
    try {
      await api('POST', '/api/game/sessions/' + encodeURIComponent(selected) +
        '/annotations', { author: 'human', body: note, labels: noteLabels });
      setStatus('Annotation added to ' + selected);
      setNote(''); setNoteLabels(''); refresh();
    } catch (e) { setStatus(e.message); }
  }
  async function fork() {
    const g = game();
    if (!g || !g.forkFromReplay) return;
    const newId = await g.forkFromReplay();
    if (newId) location.search = '?level=' + encodeURIComponent(level) +
      '&fork=' + encodeURIComponent(newId);
  }
  function applySpeed(v) {
    setSpeed(v);
    const g = game();
    if (g && g.setReplaySpeed) g.setReplaySpeed(v);
  }
  const inputCls = 'w-full rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900';

  return (
    <div className="flex h-screen flex-col bg-neutral-950">
      <header className="flex items-center gap-2 bg-neutral-900 px-4 py-2 text-white">
        <span className="text-base font-semibold">Game</span>
        <select aria-label="Test Level" className="rounded bg-neutral-800 px-2 py-1 text-sm"
          value={level} onChange={(e) => {
            setLevel(e.target.value);
            location.search = '?level=' + encodeURIComponent(e.target.value);
          }}>
          {levels.map((l) => <option key={l.id} value={l.id}>{l.name || l.id}</option>)}
        </select>
        <Chip size="sm" variant="soft">level: {level}</Chip>
        <span className="flex-1" />
        <a className="text-sm text-neutral-300 hover:underline" href="/pm">Project Manager</a>
        <a className="text-sm text-neutral-300 hover:underline"
          href={'/static/game.html?level=' + encodeURIComponent(level)}>Standalone game page</a>
      </header>
      <div className="relative min-h-0 flex-1">
        <iframe ref={frameRef} title="Game" src={frameSrc}
          className="absolute inset-0 h-full w-full border-0" style={{ width: '100%', height: '100%' }} />
        <div className="pointer-events-none absolute inset-0 z-40 flex items-start justify-end p-3">
          {collapsed ? (
            <Button className="pointer-events-auto" size="md"
              onPress={() => setCollapsed(false)}>
              Sessions{selected ? ' — ' + selected : ''}
            </Button>
          ) : (
            <Card className="pointer-events-auto z-50 flex max-h-[calc(100vh-140px)] w-[340px] flex-col p-4">
              <div className="mb-2 flex items-center gap-2">
                <h2 className="flex-1 text-base font-semibold">Sessions</h2>
                <Chip size="sm" variant="soft">{level}</Chip>
                <Button size="sm" variant="ghost" onPress={() => setCollapsed(true)}>Collapse</Button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto pr-1">
              <div className="mb-3 rounded-lg bg-neutral-100 p-3 dark:bg-neutral-800">
                <h3 className="text-sm font-semibold">Current session</h3>
                {selected ? (
                  <div className="mt-1 space-y-2">
                    <p className="break-all text-sm font-medium">{selected}</p>
                    <p className="flex flex-wrap gap-1">
                      {current && <Chip size="sm" variant="soft">{current.steps} steps</Chip>}
                      {current && <Chip size="sm" variant="soft">{current.duration_s}s</Chip>}
                      {current && <Chip size="sm" variant="soft">{current.created_by}</Chip>}
                      {current && <Chip size="sm" variant="soft">{current.result || 'open'}</Chip>}
                      {replay && replay.active && <Chip size="sm" color="accent" variant="soft">step {replay.index}/{replay.steps}</Chip>}
                    </p>
                    <div className="flex flex-wrap items-center gap-1">
                      <Button size="sm" onPress={() => { const g = game(); if (g) g.playReplay(); }}>Play</Button>
                      <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g) g.pauseReplay(); }}>Pause</Button>
                      <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g && replay) g.showReplay(replay.index - 1); }}>Back</Button>
                      <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g && replay) g.showReplay(replay.index + 1); }}>Forward</Button>
                      <select aria-label="Replay speed" className={inputCls + ' w-auto'}
                        value={speed} onChange={(e) => applySpeed(e.target.value)}>
                        <option value="1">1x</option><option value="2">2x</option>
                        <option value="5">5x</option><option value="10">10x</option>
                      </select>
                      <Button size="sm" variant="outline" onPress={fork}>Fork from here</Button>
                    </div>
                    <input aria-label="Scrub replay" type="range" className="w-full" min="0"
                      max={replay ? replay.steps : 0} value={replay ? replay.index : 0}
                      onChange={(e) => { const g = game(); if (g) g.showReplay(Number(e.target.value)); }} />
                    {replay && replay.active && <p className="text-sm">{replay.readout}</p>}
                    {replay && replay.warning ? <p className="text-sm text-amber-600">{replay.warning}</p> : null}
                    <div className="space-y-2 border-t border-neutral-300 pt-2 dark:border-neutral-600">
                      <h4 className="text-sm font-semibold">Annotate this session</h4>
                      <input className={inputCls} placeholder="Note" value={note}
                        onChange={(e) => setNote(e.target.value)} />
                      <input className={inputCls} placeholder="Labels (bug, failed)" value={noteLabels}
                        onChange={(e) => setNoteLabels(e.target.value)} />
                      <Button size="sm" onPress={annotate}>Add annotation</Button>
                      {current && current.labels && current.labels.length > 0 &&
                        <p className="text-sm">Labels: {current.labels.join(', ')}</p>}
                    </div>
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-neutral-500">None loaded — pick one from the list below and it appears here with playback and annotate.</p>
                )}
                {status && <p className="mt-2 text-sm" role="status">{status}</p>}
              </div>
              <div className="space-y-3">
                <input className={inputCls} placeholder="Search session id"
                  value={q} onChange={(e) => setQ(e.target.value)} />
                <input className={inputCls} placeholder="Label (e.g. bug)"
                  value={label} onChange={(e) => setLabel(e.target.value)} />
                <details>
                  <summary className="cursor-pointer text-sm font-medium">More filters</summary>
                  <div className="mt-2 space-y-2">
                    <select className={inputCls} value={creator}
                      onChange={(e) => setCreator(e.target.value)}>
                      <option value="">any creator</option><option>human</option><option>agent</option>
                    </select>
                    <input className={inputCls} placeholder="Feature" value={feature}
                      onChange={(e) => setFeature(e.target.value)} />
                    <input className={inputCls} type="date" value={date}
                      onChange={(e) => setDate(e.target.value)} />
                    <input className={inputCls} placeholder="Result (e.g. quit)" value={result}
                      onChange={(e) => setResult(e.target.value)} />
                  </div>
                </details>
                <Button size="sm" onPress={refresh}>Filter sessions</Button>
                <ul className="space-y-1">
                  {sessions.map((s) => (
                    <li key={s.id}>
                      <Button size="sm" variant={s.id === selected ? 'primary' : 'outline'}
                        className="h-auto w-full justify-start whitespace-normal py-1.5 text-left"
                        onPress={() => openSession(s.id)}>
                        <span>
                          <span className="block break-all">{s.id}</span>
                          <span className="block text-xs opacity-80">
                            {s.steps} steps · {s.duration_s}s · {s.created_by} · {s.result || 'open'}
                            {s.labels && s.labels.length ? ' · [' + s.labels.join(', ') + ']' : ''}
                          </span>
                        </span>
                      </Button>
                    </li>
                  ))}
                  {!sessions.length && <li className="text-sm text-neutral-500">No sessions for {level} yet — play a few moves first.</li>}
                </ul>
              </div>
              </div>
            </Card>
          )}
        </div>
      </div>
      <footer className="flex h-12 items-center justify-center bg-neutral-950 px-3">
        {replay && replay.active ? (
          <div className="flex max-w-full flex-nowrap items-center gap-2 overflow-x-auto rounded-lg bg-white px-3 py-1.5 dark:bg-neutral-900">
            <Button size="sm" onPress={() => { const g = game(); if (g) g.playReplay(); }}>Play</Button>
            <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g) g.pauseReplay(); }}>Pause</Button>
            <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g && replay) g.showReplay(replay.index - 1); }}>Step back</Button>
            <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g && replay) g.showReplay(replay.index + 1); }}>Step forward</Button>
            <input aria-label="Scrub replay" type="range" min="0"
              max={replay ? replay.steps : 0} value={replay ? replay.index : 0}
              onChange={(e) => { const g = game(); if (g) g.showReplay(Number(e.target.value)); }} />
            <Button size="sm" onPress={fork}>Fork from here</Button>
            <span className="whitespace-nowrap text-sm">{replay.readout}</span>
            {replay.warning ? <span className="whitespace-nowrap text-sm text-amber-600">{replay.warning}</span> : null}
          </div>
        ) : (
          <span className="text-sm text-neutral-400">Open Sessions to pick a recording — the replay bar appears here.</span>
        )}
      </footer>
    </div>
  );
}
