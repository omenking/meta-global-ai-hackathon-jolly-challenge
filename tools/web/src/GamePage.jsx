import { Button, Card, Chip } from '@heroui/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';

// Fullscreen game canvas with the outside-game UI as a HeroUI overlay.
// The canvas (embedded game page in an iframe) fills 100% of the page;
// overlay wrappers are pointer-events-none so they never block play —
// only the header bar, the collapsed panel and the replay bar take
// input. The side panel is fixed, higher z-index, collapsed by default
// and scrolls internally, so it can never run off the page.
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

  // Sessions narrow to the level already selected in the game; the
  // level is not a search field. Search + label stay visible, the
  // remaining filters live under More filters.
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
  function openSession(id) {
    setSelected(id);
    const g = game();
    if (g && g.loadReplay) g.loadReplay(id);
  }
  async function annotate() {
    const target = selected || (replay && replay.id);
    if (!target) { setStatus('Pick a session first.'); return; }
    try {
      await api('POST', '/api/game/sessions/' + encodeURIComponent(target) +
        '/annotations', { author: 'human', body: note, labels: noteLabels });
      setStatus('Annotation added to ' + target);
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
  const inputCls = 'w-full rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900';

  return (
    <div className="fixed inset-0 bg-neutral-950">
      <iframe ref={frameRef} title="Game" src={frameSrc}
        className="h-full w-full border-0" style={{ width: '100%', height: '100%' }} />
      <div className="pointer-events-none absolute inset-0 z-40 flex flex-col">
        <header className="pointer-events-auto flex items-center gap-2 bg-neutral-900/90 px-4 py-2 text-white">
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
        <div className="flex flex-1 items-start justify-end p-3">
          {collapsed ? (
            <Button className="pointer-events-auto" size="md"
              onPress={() => setCollapsed(false)}>Sessions</Button>
          ) : (
            <Card className="pointer-events-auto z-50 flex max-h-[calc(100vh-140px)] w-[340px] flex-col p-4">
              <div className="mb-2 flex items-center gap-2">
                <h2 className="flex-1 text-base font-semibold">Sessions</h2>
                <Chip size="sm" variant="soft">{level}</Chip>
                <Button size="sm" variant="ghost" onPress={() => setCollapsed(true)}>Collapse</Button>
              </div>
              <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
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
                        {s.id} ({s.created_by}, {s.result || 'open'})
                        {s.labels && s.labels.length ? ' [' + s.labels.join(', ') + ']' : ''}
                      </Button>
                    </li>
                  ))}
                  {!sessions.length && <li className="text-sm text-neutral-500">No sessions for {level} yet — play a few moves first.</li>}
                </ul>
                <div className="space-y-2 border-t border-neutral-200 pt-3 dark:border-neutral-700">
                  <h3 className="text-sm font-semibold">Annotate {selected || ''}</h3>
                  <input className={inputCls} placeholder="Note" value={note}
                    onChange={(e) => setNote(e.target.value)} />
                  <input className={inputCls} placeholder="Labels (bug, failed)" value={noteLabels}
                    onChange={(e) => setNoteLabels(e.target.value)} />
                  <Button size="sm" onPress={annotate}>Add annotation</Button>
                </div>
                {status && <p className="text-sm text-neutral-500" role="status">{status}</p>}
              </div>
            </Card>
          )}
        </div>
        <div className="pointer-events-auto mx-auto mb-3 w-auto max-w-full">
          <Card className="flex flex-wrap items-center gap-2 px-3 py-2">
            <Button size="sm" onPress={() => { const g = game(); if (g) g.playReplay(); }}>Play</Button>
            <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g) g.pauseReplay(); }}>Pause</Button>
            <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g && replay) g.showReplay(replay.index - 1); }}>Step back</Button>
            <Button size="sm" variant="outline" onPress={() => { const g = game(); if (g && replay) g.showReplay(replay.index + 1); }}>Step forward</Button>
            <input aria-label="Scrub replay" type="range" min="0"
              max={replay ? replay.steps : 0} value={replay ? replay.index : 0}
              onChange={(e) => { const g = game(); if (g) g.showReplay(Number(e.target.value)); }} />
            <Button size="sm" onPress={fork}>Fork from here</Button>
            <span className="text-sm">{replay && replay.active ? replay.readout : 'Pick a session to replay it here.'}</span>
            {replay && replay.warning ? <span className="text-sm text-amber-600">{replay.warning}</span> : null}
          </Card>
        </div>
      </div>
    </div>
  );
}
