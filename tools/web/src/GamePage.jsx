import { Leva, button, folder, useControls } from 'leva';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';

// Fullscreen game canvas; every outside-game control lives in the
// Leva GUI panel (pmndrs/leva). The canvas fills the page and Leva
// floats at the top-right, collapsed by default, so play is never
// blocked. Sessions narrow to the level selected in Leva.
export default function GamePage() {
  const params = new URLSearchParams(location.search);
  const [level, setLevel] = useState(params.get('level') || 'movement-room');
  const [levels, setLevels] = useState([]);
  const [panelCollapsed, setPanelCollapsed] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState(params.get('replay') || '');
  const [replay, setReplay] = useState(null);
  const [status, setStatus] = useState('');
  const frameRef = useRef(null);
  const noteRef = useRef({ note: '', labels: '' });
  const frameSrc = '/static/game.html?embed=1&level=' +
    encodeURIComponent(level) +
    (params.get('replay') ? '&replay=' + encodeURIComponent(params.get('replay')) : '') +
    (params.get('t') ? '&t=' + encodeURIComponent(params.get('t')) : '') +
    (params.get('fork') ? '&fork=' + encodeURIComponent(params.get('fork')) : '');

  const game = useCallback(() => frameRef.current && frameRef.current.contentWindow &&
    frameRef.current.contentWindow.__game, []);
  const current = sessions.find((s) => s.id === selected) || null;

  const openSession = useCallback((id) => {
    if (!id) return;
    setSelected(id);
    const g = game();
    if (g && g.loadReplay) g.loadReplay(id);
  }, [game]);

  const fork = useCallback(async () => {
    const g = game();
    if (!g || !g.forkFromReplay) return;
    const newId = await g.forkFromReplay();
    if (newId) location.search = '?level=' + encodeURIComponent(level) +
      '&fork=' + encodeURIComponent(newId);
  }, [game, level]);

  const annotate = useCallback(async () => {
    if (!selected) { setStatus('Pick a session first.'); return; }
    try {
      await api('POST', '/api/game/sessions/' + encodeURIComponent(selected) +
        '/annotations', { author: 'human', body: noteRef.current.note,
          labels: noteRef.current.labels });
      setStatus('Annotation added to ' + selected);
    } catch (e) { setStatus(e.message); }
  }, [selected]);

  useEffect(() => {
    api('GET', '/api/game/levels').then((d) =>
      setLevels((d.levels || []).filter((l) => l.test))).catch(() => {});
  }, []);
  useEffect(() => {
    const id = setInterval(() => {
      const w = frameRef.current && frameRef.current.contentWindow;
      if (w && w.__game && w.__game.getReplay) setReplay(w.__game.getReplay());
    }, 300);
    return () => clearInterval(id);
  }, []);

  const levelOptions = {};
  for (const l of levels) levelOptions[l.name || l.id] = l.id;
  if (!levels.length) levelOptions[level] = level;
  const sessionOptions = { '(pick a session)': '' };
  for (const s of sessions) {
    sessionOptions[s.id + ' — ' + s.steps + ' steps, ' + s.duration_s + 's, ' +
      s.created_by + ', ' + (s.result || 'open')] = s.id;
  }

  const [main, setMain] = useControls('Game', () => ({
    level: { value: level, options: levelOptions, label: 'Level' },
    session: { value: selected, options: sessionOptions, label: 'Session' },
    current: {
      value: current ? current.id + ' · ' + current.steps + ' steps · ' +
        current.duration_s + 's · ' + (current.result || 'open') : 'none loaded',
      editable: false, label: 'Current',
    },
    status: { value: status, editable: false, label: 'Status' },
    'Project Manager': button(() => { location.href = '/pm'; }),
  }), [level, selected, sessions, current, status]);

  const [playback] = useControls('Playback', () => ({
    step: {
      value: replay && replay.active ? replay.index + '/' + replay.steps : '—',
      editable: false, label: 'Step',
    },
    scrub: { value: 0, min: 0, max: replay ? replay.steps : 0, step: 1, label: 'Scrub' },
    speed: { value: '1', options: ['1', '2', '5', '10'], label: 'Speed' },
    Play: button(() => { const g = game(); if (g) g.playReplay(); }),
    Pause: button(() => { const g = game(); if (g) g.pauseReplay(); }),
    'Step back': button(() => { const g = game(); if (g && replay) g.showReplay(replay.index - 1); }),
    'Step forward': button(() => { const g = game(); if (g && replay) g.showReplay(replay.index + 1); }),
    'Fork from here': button(() => fork()),
  }), [replay, game, fork]);

  const [annotateVals] = useControls('Annotate', () => ({
    note: { value: '', label: 'Note' },
    labels: { value: '', label: 'Labels' },
    'Add annotation': button(() => annotate()),
  }), [annotate]);
  noteRef.current = { note: annotateVals.note || '', labels: annotateVals.labels || '' };

  const [filters] = useControls(() => ({
    Filters: folder({
      search: { value: '', label: 'Search id' },
      label: { value: '', label: 'Label' },
      creator: { value: '', options: ['', 'human', 'agent'], label: 'Creator' },
      feature: { value: '', label: 'Feature' },
      date: { value: '', label: 'Date' },
      result: { value: '', label: 'Result' },
    }),
  }));

  const refresh = useCallback(async () => {
    const qs = new URLSearchParams({ level });
    if (filters.search) qs.set('q', filters.search);
    if (filters.label) qs.set('label', filters.label);
    if (filters.creator) qs.set('creator', filters.creator);
    if (filters.feature) qs.set('feature', filters.feature);
    if (filters.date) qs.set('date', filters.date);
    if (filters.result) qs.set('result', filters.result);
    try {
      const d = await api('GET', '/api/game/sessions?' + qs.toString());
      setSessions(d.sessions || []);
    } catch (e) { setStatus(e.message); }
  }, [level, filters]);
  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    setMain({ current: current ? current.id + ' · ' + current.steps +
      ' steps · ' + current.duration_s + 's · ' + (current.result || 'open')
      : 'none loaded', status: status });
  }, [current, status, setMain]);
  useEffect(() => {
    if (main.level && main.level !== level) {
      setLevel(main.level);
      location.search = '?level=' + encodeURIComponent(main.level);
    }
  }, [main.level, level]);
  useEffect(() => { if (main.session && main.session !== selected) openSession(main.session); },
    [main.session, selected, openSession]);
  useEffect(() => {
    const g = game();
    if (g && g.setReplaySpeed) g.setReplaySpeed(playback.speed);
  }, [playback.speed, game]);
  useEffect(() => {
    const g = game();
    if (g && replay && playback.scrub !== replay.index) g.showReplay(playback.scrub);
    // Scrub only drives the replay on user change; replay is read for
    // the comparison, not a dependency, to avoid a feedback loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playback.scrub, game]);

  return (
    <div className="fixed inset-0 bg-neutral-950">
      <iframe ref={frameRef} title="Game" src={frameSrc}
        className="h-full w-full border-0" style={{ width: '100%', height: '100%' }} />
      <Leva collapsed={{ collapsed: panelCollapsed, onChange: setPanelCollapsed }}
        titleBar={{ title: 'Game — Sessions & Replay' }} />
    </div>
  );
}
