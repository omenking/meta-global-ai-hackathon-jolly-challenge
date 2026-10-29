import { Button, Card, Chip, Spinner } from '@heroui/react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, evidenceUrl, PM } from './api.js';

const STATUSES = ['proposed', 'approved', 'in_progress', 'in_review', 'completed', 'blocked', 'abandoned'];
// Tasks are agent-managed and have no in_review stage: done means completed.
// Legacy stored in_review tasks display as completed.
const TASK_STATUSES = STATUSES.filter((s) => s !== 'in_review');
export const taskStatus = (t) => (t.status === 'in_review' ? 'completed' : t.status);
const PRIORITIES = ['low', 'medium', 'high', 'urgent'];
const SPEC_KEYS = [
  ['goal', 'Goal'], ['user_story', 'User Story'], ['use_case', 'High-Level Use Case'],
  ['behavior', 'Player-Facing Behavior'], ['edge_cases', 'Edge Cases & Rules'],
  ['ui_feedback', 'UI / Feedback'], ['assets_needed', 'Assets & Level Data Needed'],
  ['acceptance', 'Acceptance Criteria'], ['testing', 'Testing'],
  ['out_of_scope', 'Out of Scope'], ['open_questions', 'Open Questions'],
];
const STATUS_COLOR = {
  proposed: 'default', approved: 'accent', in_progress: 'warning',
  in_review: 'accent', completed: 'success', blocked: 'danger', abandoned: 'default',
};
const PRIORITY_COLOR = { low: 'default', medium: 'default', high: 'warning', urgent: 'danger' };

export function navigate(to) {
  if (location.pathname === to) return;
  history.pushState(null, '', to);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
export function linkProps(to) {
  return {
    href: to,
    onClick: (e) => { e.preventDefault(); navigate(to); },
  };
}

function parseRoute(pathname) {
  const parts = pathname.split('/').filter(Boolean).map(decodeURIComponent);
  if (parts.length === 0) return { view: 'home' };
  if (parts[0] !== 'pm') return { view: 'home' };
  if (parts.length === 1) return { view: 'list' };
  if (parts[1] === 'board') return { view: 'board' };
  if (parts[1] === 'features' && parts[2] === 'new') return { view: 'feature-new' };
  if (parts[1] === 'features' && parts[2]) {
    const fid = parts[2];
    if (parts[3] === 'edit') return { view: 'feature-edit', fid };
    // Review lives on the feature page; old /review links land there.
    if (parts[3] === 'review') return { view: 'feature-show', fid };
    if (parts[3] === 'tasks' && parts[4] === 'new') return { view: 'task-new', fid };
    if (parts[3] === 'tasks' && parts[4] && parts[5] === 'edit') {
      return { view: 'task-edit', fid, tid: parts[4] };
    }
    if (parts[3] === 'tasks' && parts[4]) return { view: 'task-show', fid, tid: parts[4] };
    return { view: 'feature-show', fid };
  }
  return { view: 'list' };
}

export const featurePath = (fid) => `/pm/features/${encodeURIComponent(fid)}`;
export const taskPath = (fid, tid) => `${featurePath(fid)}/tasks/${encodeURIComponent(tid)}`;

function StatusChip({ status }) {
  return <Chip color={STATUS_COLOR[status] || 'default'} variant="soft">{status}</Chip>;
}
function TaskStatusChip({ task }) {
  return <StatusChip status={taskStatus(task)} />;
}
function PriorityChip({ priority }) {
  return <Chip color={PRIORITY_COLOR[priority] || 'default'} variant="soft">{priority}</Chip>;
}
function Progress({ progress }) {
  const p = progress || { done: 0, total: 0, percent: 0 };
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-block h-2.5 w-28 overflow-hidden rounded bg-neutral-200 dark:bg-neutral-700">
        <span className="block h-full bg-emerald-600" style={{ width: `${p.percent}%` }} />
      </span>
      <span className="text-sm text-neutral-500">{p.done}/{p.total} tasks</span>
    </span>
  );
}

function Shell({ route, dark, onToggleDark, children }) {
  const navBtn = (to, label, active) => (
    <Button size="md" variant={active ? 'primary' : 'ghost'}
      onPress={() => navigate(to)}>{label}</Button>
  );
  const pmActive = route.view !== 'home';
  return (
    <div className="min-h-screen bg-neutral-100 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/95 dark:border-neutral-800 dark:bg-neutral-900/95">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-2 px-4 py-3">
          <a className="mr-2 text-lg font-semibold" {...linkProps('/')}>Jolly Tools</a>
          {navBtn('/', 'Home', route.view === 'home')}
          {navBtn('/pm', 'Project Manager', pmActive)}
          <a className="px-2 text-base text-neutral-600 hover:underline dark:text-neutral-300" href="/assets">Asset Design</a>
          <a className="px-2 text-base text-neutral-600 hover:underline dark:text-neutral-300" href="/static/level-preview.html">Level Preview</a>
          <span className="flex-1" />
          <Button size="md" variant="outline" onPress={onToggleDark}>{dark ? 'Light' : 'Dark'}</Button>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 py-5">{children}</main>
    </div>
  );
}

function ToolCard({ to, href, title, desc }) {
  return (
    <Card className="p-5">
      {href
        ? <a className="text-lg font-semibold text-blue-700 hover:underline dark:text-blue-300" href={href}>{title}</a>
        : <a className="text-lg font-semibold text-blue-700 hover:underline dark:text-blue-300" {...linkProps(to)}>{title}</a>}
      <p className="mt-1 text-base text-neutral-600 dark:text-neutral-300">{desc}</p>
    </Card>
  );
}

function Home() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Tools</h1>
        <p className="text-base text-neutral-500">Local tools for the Chip&apos;s Challenge clone. Everything runs from this one server.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <ToolCard to="/pm" title="Project Manager"
          desc="Feature and task board for the game engine: list, kanban, comments, and feature review." />
        <ToolCard href="/assets" title="Asset Design Tool"
          desc="Iterate on generated tile art: versions, lottery runs, sessions, and judging." />
        <ToolCard href="/static/level-preview.html" title="Level Preview"
          desc="Render a level layout (rows plus legend) with its sprites. Add ?level=chip1 to pick a level." />
        <ToolCard to="/pm/features/game-shell" title="Game shell — not built yet"
          desc="The playable game is the game-shell feature on the board. Until it lands, use Level Preview to look at levels." />
      </div>
    </div>
  );
}

export function sortTasks(tasks) {
  return [...(tasks || [])].sort((a, b) => (a.order - b.order) || a.id.localeCompare(b.id));
}
const inputCls = 'w-full rounded-md border border-neutral-300 bg-white px-3 py-2.5 text-base dark:border-neutral-700 dark:bg-neutral-900';
function Field({ label, children }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-semibold">{label}</label>
      {children}
    </div>
  );
}
function PageLinks({ items }) {
  return (
    <p className="text-base">
      {items.map(([label, to], i) => (
        <span key={to}>
          {i > 0 && ' · '}
          <a className="text-blue-700 hover:underline dark:text-blue-300" {...linkProps(to)}>{label}</a>
        </span>
      ))}
    </p>
  );
}

function CommentCard({ comment, scope, onEdit, onDelete }) {
  const canEdit = comment.author === 'human';
  return (
    <div className={`rounded-lg border p-4 ${comment.author === 'agent'
      ? 'border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40'
      : 'border-neutral-200 bg-white dark:border-neutral-700 dark:bg-neutral-900'}`}>
      <div className="text-sm text-neutral-500">
        {comment.created} · {comment.author} · on {scope}
        {!canEdit && ' · read-only (agent)'}
      </div>
      <div className="mt-1 whitespace-pre-wrap text-base leading-relaxed">{comment.body}</div>
      {!!(comment.attachments || []).length && (
        <div className="mt-2 flex flex-wrap gap-2">
          {comment.attachments.map((a) => (
            <a key={a} href={evidenceUrl(a)} target="_blank" rel="noreferrer">
              <img className="h-28 w-44 rounded border object-cover" src={evidenceUrl(a)} alt={a} />
            </a>
          ))}
        </div>
      )}
      {!!(comment.session_refs || []).length && (
        <div className="mt-2 text-sm text-neutral-500">
          {comment.session_refs.map((s, i) => (
            <div key={i}>Session {s.id} · {s.level} · {s.created_by} · {s.result}{s.path ? ` · ${s.path}` : ''}</div>
          ))}
        </div>
      )}
      {canEdit && (
        <div className="mt-3 flex gap-2">
          <Button size="md" variant="outline" onPress={() => onEdit(comment)}>Edit</Button>
          <Button size="md" variant="danger-soft" onPress={() => onDelete(comment)}>Delete</Button>
        </div>
      )}
    </div>
  );
}

function Comments({ feature, task, reload }) {
  const [body, setBody] = useState('');
  const [atts, setAtts] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const list = (task ? task.comments : feature.comments) || [];
  const scope = task ? `${feature.id}/${task.id}` : feature.id;
  const base = task
    ? `${PM}/features/${encodeURIComponent(feature.id)}/tasks/${encodeURIComponent(task.id)}/comments`
    : `${PM}/features/${encodeURIComponent(feature.id)}/comments`;
  async function add() {
    setBusy(true); setErr('');
    try {
      const attachments = atts.split(',').map((s) => s.trim()).filter(Boolean);
      await api('POST', base, { author: 'human', body, attachments });
      setBody(''); setAtts('');
      await reload();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  async function edit(comment) {
    const next = window.prompt('Edit comment', comment.body);
    if (next === null) return;
    try { await api('PUT', `${base}/${encodeURIComponent(comment.id)}`, { body: next }); await reload(); }
    catch (e) { setErr(e.message); }
  }
  async function del(comment) {
    try { await api('DELETE', `${base}/${encodeURIComponent(comment.id)}`); await reload(); }
    catch (e) { setErr(e.message); }
  }
  return (
    <div className="space-y-3">
      {list.map((c) => (
        <CommentCard key={c.id} comment={c} scope={scope} onEdit={edit} onDelete={del} />
      ))}
      {!list.length && <p className="text-base text-neutral-500">No comments yet.</p>}
      {err && <p className="text-base text-red-600">{err}</p>}
      <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900">
        <h4 className="mb-2 text-base font-semibold">Add a comment</h4>
        <Field label="Comment (as human)">
          <textarea className={inputCls} rows={4} value={body}
            onChange={(e) => setBody(e.target.value)} />
        </Field>
        <div className="mt-3">
          <Field label="Attachments (comma-separated evidence paths)">
            <input className={inputCls} value={atts} onChange={(e) => setAtts(e.target.value)} />
          </Field>
        </div>
        <div className="mt-3">
          <Button size="md" isPending={busy} onPress={add}>Add comment</Button>
        </div>
      </div>
    </div>
  );
}

function PmToolbar({ features, query, setQuery, statusFilter, setStatusFilter,
  showArchived, setShowArchived, onSeed, onExport, busy }) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="min-w-60 flex-1">
        <Field label="Search features and tasks">
          <input className={inputCls} placeholder="e.g. keys"
            value={query} onChange={(e) => setQuery(e.target.value)} />
        </Field>
      </div>
      <div>
        <Field label="Status">
          <select className={inputCls} value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
      </div>
      <label className="flex items-center gap-2 pb-3 text-base">
        <input className="h-5 w-5" type="checkbox" checked={showArchived}
          onChange={(e) => setShowArchived(e.target.checked)} /> Show archived
      </label>
      <span className="flex-1" />
      <Button size="md" variant="outline" isPending={busy} onPress={onSeed}>Seed</Button>
      <Button size="md" variant="outline" isPending={busy} onPress={onExport}>Export markdown</Button>
      <Button size="md" onPress={() => navigate('/pm/features/new')}>New feature</Button>
      <span className="pb-3 text-base text-neutral-500">{features.length} feature(s)</span>
    </div>
  );
}

function FeatureCard({ feature, showArchived }) {
  const tasks = sortTasks(feature.tasks).filter((t) => showArchived || !t.archived);
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center gap-2">
        <a className="text-lg font-semibold hover:underline" {...linkProps(featurePath(feature.id))}>
          {feature.title}
        </a>
        <StatusChip status={feature.status} />
        <PriorityChip priority={feature.priority} />
        {feature.review?.decision === 'approved_for_merge'
          && <Chip color="success" variant="soft">approved — awaiting merge</Chip>}
        {feature.archived && <Chip variant="soft">archived</Chip>}
        <Progress progress={feature.progress} />
        <span className="flex-1" />
        <Button size="md" variant="outline" onPress={() => navigate(featurePath(feature.id))}>View</Button>
        <Button size="md" variant="outline" onPress={() => navigate(`${featurePath(feature.id)}/edit`)}>Edit</Button>
      </div>
      <p className="mt-1 text-base text-neutral-600 dark:text-neutral-300">{feature.summary}</p>
      <p className="text-sm text-neutral-500">
        {feature.id} · requires: {(feature.requires || []).join(', ') || '—'}
        {' '}· unblocks: {(feature.unblocks || []).join(', ') || '—'}
        {' '}· branch: {feature.branch || '—'}
      </p>
      <div className="mt-2 divide-y divide-neutral-100 dark:divide-neutral-800">
        {tasks.map((t) => (
          <div key={t.id} className="flex flex-wrap items-center gap-2 py-2">
            <a className="text-base hover:underline" {...linkProps(taskPath(feature.id, t.id))}>{t.title}</a>
            <TaskStatusChip task={t} />
            <PriorityChip priority={t.priority} />
            <span className="text-sm text-neutral-500">
              {feature.id}/{t.id}{t.commit ? ` · ${t.commit}` : ''}{t.archived ? ' · archived' : ''}
            </span>
          </div>
        ))}
        {!tasks.length && <p className="py-1 text-base text-neutral-500">No tasks.</p>}
      </div>
    </Card>
  );
}

function Board({ features, showArchived, featureFilter, setFeatureFilter, reload, setError }) {
  const [over, setOver] = useState('');
  async function handleDrop(status, count, e) {
    e.preventDefault(); setOver('');
    let payload;
    try { payload = JSON.parse(e.dataTransfer.getData('text/plain')); } catch { return; }
    try {
      await api('POST',
        `${PM}/features/${encodeURIComponent(payload.fid)}/tasks/${encodeURIComponent(payload.tid)}/move`,
        { status, order: count });
      await reload();
    } catch (err) { setError(err.message); }
  }
  return (
    <div>
      <div className="mb-3 max-w-sm">
        <Field label="Filter by feature">
          <select className={inputCls} value={featureFilter}
            onChange={(e) => setFeatureFilter(e.target.value)}>
            <option value="">All features</option>
            {features.map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
          </select>
        </Field>
      </div>
      <div className="pm-scroll grid auto-cols-[240px] grid-flow-col gap-3 overflow-x-auto pb-2">
        {TASK_STATUSES.map((status) => {
          const cards = [];
          for (const f of features) {
            if (featureFilter && f.id !== featureFilter) continue;
            for (const t of sortTasks(f.tasks)) {
              if (taskStatus(t) !== status) continue;
              if (!showArchived && t.archived) continue;
              cards.push({ f, t });
            }
          }
          return (
            <div key={status}
              className={`min-h-32 rounded-lg border bg-white p-3 dark:bg-neutral-900 ${over === status
                ? 'border-blue-500 outline-dashed outline-2 outline-blue-400'
                : 'border-neutral-200 dark:border-neutral-700'}`}
              onDragOver={(e) => { e.preventDefault(); setOver(status); }}
              onDragLeave={() => setOver('')}
              onDrop={(e) => handleDrop(status, cards.length, e)}>
              <h3 className="mb-2 text-base font-semibold">{status} ({cards.length})</h3>
              {cards.map(({ f, t }) => (
                <div key={`${f.id}/${t.id}`} draggable
                  className="mb-2 cursor-grab rounded border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-700 dark:bg-neutral-800"
                  onDragStart={(e) => e.dataTransfer.setData('text/plain',
                    JSON.stringify({ fid: f.id, tid: t.id }))}>
                  <div className="text-sm text-neutral-500">{f.id}</div>
                  <a className="text-base hover:underline" {...linkProps(taskPath(f.id, t.id))}>{t.title}</a>
                  <div className="mt-1 flex gap-1">
                    <PriorityChip priority={t.priority} />
                    {t.kind === 'review-fixes' && <Chip variant="soft">review-fixes</Chip>}
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
      <p className="text-sm text-neutral-500">Drag a card to another column to change its status. List and board are two views of the same tasks.</p>
    </div>
  );
}

function SpecShow({ spec }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {SPEC_KEYS.map(([key, title]) => (
        <section key={key} className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900">
          <h3 className="text-lg font-semibold">{title}</h3>
          <div className="mt-1 whitespace-pre-wrap text-base leading-relaxed text-neutral-700 dark:text-neutral-200">
            {(spec || {})[key] || <span className="text-neutral-400">Not written yet.</span>}
          </div>
        </section>
      ))}
    </div>
  );
}

function collectEvidence(feature) {
  const gallery = [];
  const sessions = [];
  const collect = (c) => {
    for (const a of c.attachments || []) if (!gallery.includes(a)) gallery.push(a);
    for (const s of c.session_refs || []) sessions.push(s);
  };
  (feature.comments || []).forEach(collect);
  (feature.tasks || []).forEach((t) => (t.comments || []).forEach(collect));
  (feature.sessions || []).forEach((s) => sessions.push(s));
  return { gallery, sessions };
}

function ReviewPanel({ feature, reload, setError }) {
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const decision = feature.review?.decision || 'pending';
  async function review(dec) {
    if (dec === 'changes_requested' && !comment.trim()) {
      setError('Request changes requires a comment.'); return;
    }
    setBusy(true); setNotice('');
    try {
      await api('POST', `${PM}/features/${encodeURIComponent(feature.id)}/review`,
        { decision: dec, by: 'human', comment });
      setComment('');
      setNotice(dec === 'approved_for_merge'
        ? 'Recorded: approved for merge. The agent merges; only then completed.'
        : 'Recorded: changes requested. The feature is back in progress.');
      await reload();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return (
    <Card className="space-y-3 p-5">
      <h2 className="text-lg font-semibold">Review</h2>
      <p className="text-base text-neutral-600 dark:text-neutral-300">
        Decision: <strong>{decision}</strong>
        {decision === 'approved_for_merge' && ' — approved, awaiting agent merge'}
      </p>
      {notice && <p className="rounded border border-emerald-300 bg-emerald-50 p-3 text-base text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200" role="status">{notice}</p>}
      <Field label="Comment (required for Request changes)">
        <textarea className={inputCls} rows={3} value={comment}
          onChange={(e) => setComment(e.target.value)} />
      </Field>
      <div className="flex flex-wrap gap-2">
        <Button size="md" variant="danger" isPending={busy} isDisabled={busy || !!notice}
          onPress={() => review('changes_requested')}>Request changes</Button>
        <Button size="md" isPending={busy} isDisabled={busy || !!notice}
          onPress={() => review('approved_for_merge')}>Approve for merge</Button>
      </div>
      <p className="text-sm text-neutral-500">
        Tasks are agent-managed: done tasks are completed as the agent reports
        them, so inspect task code/commits above. Approving only records the
        decision; the agent merges and only then the feature is completed.
      </p>
    </Card>
  );
}

function EvidencePanel({ feature }) {
  const { gallery, sessions } = collectEvidence(feature);
  const wt = feature.worktree || `.worktrees/${feature.id}`;
  return (
    <Card className="space-y-3 p-5">
      <h2 className="text-lg font-semibold">Evidence &amp; playtest</h2>
      <div>
        <h3 className="text-base font-semibold">Screenshots</h3>
        {gallery.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {gallery.map((a) => (
              <a key={a} href={evidenceUrl(a)} target="_blank" rel="noreferrer">
                <img className="h-28 w-44 rounded border object-cover" src={evidenceUrl(a)} alt={a} />
              </a>
            ))}
          </div>
        ) : <p className="text-base text-neutral-500">No screenshot evidence yet.</p>}
      </div>
      <div>
        <h3 className="text-base font-semibold">Linked sessions</h3>
        {sessions.length ? sessions.map((s, i) => (
          <p key={i} className="text-base text-neutral-600 dark:text-neutral-300">
            Session {s.id} · level {s.level} · creator {s.created_by} · result {s.result}
            {s.path ? ` · ${s.path}` : ''}
          </p>
        )) : <p className="text-base text-neutral-500">No linked sessions yet.</p>}
      </div>
      <div>
        <h3 className="text-base font-semibold">Playtest</h3>
        <p className="text-base text-neutral-600 dark:text-neutral-300">
          Test Level: {feature.test_level || '—'} (start it from the game menu in the
          worktree build; the manager never starts levels). Worktree: {wt} ·
          branch: {feature.branch || `feat/${feature.id}`}
        </p>
        <pre className="mt-2 overflow-x-auto rounded bg-neutral-900 p-3 text-sm text-emerald-200">
{`cd ${wt} && python tools/server.py --port 8323
Then open http://127.0.0.1:8323/pm/features/${feature.id} and start Test Level ${feature.test_level || '<test_level>'} from the game menu.`}
        </pre>
      </div>
    </Card>
  );
}

function FeatureShow({ feature, reload, setError }) {
  return (
    <div className="space-y-4">
      <PageLinks items={[['← Board list', '/pm'], ['Kanban', '/pm/board']]} />
      <Card className="p-5">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-60 flex-1">
            <h1 className="text-2xl font-semibold leading-snug">{feature.title}</h1>
            <p className="mt-1 text-base text-neutral-600 dark:text-neutral-300">{feature.summary}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="md" onPress={() => navigate(`${featurePath(feature.id)}/edit`)}>Edit feature</Button>
            <Button size="md" variant="outline" onPress={() => navigate(`${featurePath(feature.id)}/tasks/new`)}>New task</Button>
            <Button size="md" variant="danger-soft" onPress={async () => {
              try { await api('DELETE', `${PM}/features/${encodeURIComponent(feature.id)}`); await reload(); navigate('/pm'); }
              catch (e) { setError(e.message); }
            }}>Archive</Button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusChip status={feature.status} />
          <PriorityChip priority={feature.priority} />
          {feature.review?.decision === 'approved_for_merge'
            && <Chip color="success" variant="soft">approved — awaiting merge</Chip>}
          {feature.archived && <Chip variant="soft">archived</Chip>}
          <Progress progress={feature.progress} />
        </div>
      </Card>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0 space-y-4">
          <Card className="p-5">
            <div className="flex items-center gap-2">
              <h2 className="flex-1 text-xl font-semibold">Tasks</h2>
              <Button size="md" variant="outline" onPress={() => navigate(`${featurePath(feature.id)}/tasks/new`)}>New task</Button>
            </div>
            <div className="mt-2 divide-y divide-neutral-100 dark:divide-neutral-800">
              {sortTasks(feature.tasks).map((t) => (
                <div key={t.id} className="flex flex-wrap items-center gap-2 py-2.5">
                  <a className="text-base font-medium hover:underline" {...linkProps(taskPath(feature.id, t.id))}>{t.title}</a>
                  <TaskStatusChip task={t} />
                  <PriorityChip priority={t.priority} />
                  {t.kind === 'review-fixes' && <Chip variant="soft">review-fixes</Chip>}
                  <span className="text-sm text-neutral-500">
                    {t.id}{t.commit ? ` · ${t.commit}` : ''}{t.archived ? ' · archived' : ''}
                  </span>
                  <span className="flex-1" />
                  <Button size="md" variant="outline" onPress={() => navigate(`${taskPath(feature.id, t.id)}/edit`)}>Edit</Button>
                </div>
              ))}
              {!feature.tasks?.length && <p className="py-2 text-base text-neutral-500">No tasks yet.</p>}
            </div>
          </Card>

          <div>
            <h2 className="mb-3 text-xl font-semibold">Specification</h2>
            <SpecShow spec={feature.spec} />
          </div>

          <div>
            <h2 className="mb-3 text-xl font-semibold">Comments</h2>
            <Comments feature={feature} task={null} reload={reload} />
          </div>
        </div>

        <div className="space-y-4 xl:sticky xl:top-20">
          <ReviewPanel feature={feature} reload={reload} setError={setError} />
          <EvidencePanel feature={feature} />
          <Card className="p-5">
            <h2 className="text-lg font-semibold">Details</h2>
            <dl className="mt-2 grid gap-x-4 gap-y-2 text-base sm:grid-cols-2 xl:grid-cols-1">
              <div><dt className="font-semibold">Feature id</dt><dd>{feature.id}</dd></div>
              <div><dt className="font-semibold">Test level</dt><dd>{feature.test_level || '—'}</dd></div>
              <div><dt className="font-semibold">Requires</dt><dd>{(feature.requires || []).join(', ') || '—'}</dd></div>
              <div><dt className="font-semibold">Unblocks</dt><dd>{(feature.unblocks || []).join(', ') || '—'}</dd></div>
              <div><dt className="font-semibold">Branch</dt><dd>{feature.branch || '—'}</dd></div>
              <div><dt className="font-semibold">Worktree</dt><dd>{feature.worktree || '—'}</dd></div>
              <div><dt className="font-semibold">Review decision</dt><dd>{feature.review?.decision || 'pending'}</dd></div>
              <div><dt className="font-semibold">Merged</dt><dd>{feature.merged ? `${feature.merged.commit} · ${feature.merged.at}` : '—'}</dd></div>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}

function FeatureEdit({ feature, reload, setError }) {
  const [form, setForm] = useState({
    title: feature.title, summary: feature.summary || '', status: feature.status,
    priority: feature.priority, test_level: feature.test_level || '',
    requires: (feature.requires || []).join(', '), spec: { ...(feature.spec || {}) },
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const back = featurePath(feature.id);
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageLinks items={[['← Back to feature', back], ['Board list', '/pm']]} />
      <Card className="space-y-4 p-5">
        <h1 className="text-2xl font-semibold">Edit feature</h1>
        <Field label="Title"><input className={inputCls} value={form.title} onChange={set('title')} /></Field>
        <Field label="Summary"><input className={inputCls} value={form.summary} onChange={set('summary')} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Status">
            <select className={inputCls} value={form.status} onChange={set('status')}>
              {STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Priority">
            <select className={inputCls} value={form.priority} onChange={set('priority')}>
              {PRIORITIES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Test level"><input className={inputCls} value={form.test_level} onChange={set('test_level')} /></Field>
          <Field label="Requires (comma-separated feature ids)">
            <input className={inputCls} value={form.requires} onChange={set('requires')} />
          </Field>
        </div>
        {SPEC_KEYS.map(([key, title]) => (
          <Field key={key} label={title}>
            <textarea className={inputCls} rows={5} value={form.spec[key] || ''}
              onChange={(e) => setForm({ ...form, spec: { ...form.spec, [key]: e.target.value } })} />
          </Field>
        ))}
        <div className="flex gap-2">
          <Button size="md" variant="outline" onPress={() => navigate(back)}>Cancel</Button>
          <Button size="md" isPending={busy} onPress={async () => {
            setBusy(true);
            try {
              await api('PUT', `${PM}/features/${encodeURIComponent(feature.id)}`, {
                title: form.title, summary: form.summary, status: form.status,
                priority: form.priority, test_level: form.test_level || null,
                requires: form.requires.split(',').map((s) => s.trim()).filter(Boolean),
                spec: form.spec,
              });
              await reload(); navigate(back);
            } catch (e) { setError(e.message); setBusy(false); }
          }}>Save changes</Button>
        </div>
      </Card>
    </div>
  );
}

function FeatureNew({ reload, setError }) {
  const [form, setForm] = useState({ id: '', title: '', summary: '', priority: 'medium' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageLinks items={[['← Board list', '/pm']]} />
      <Card className="space-y-4 p-5">
        <h1 className="text-2xl font-semibold">New feature</h1>
        <Field label="Id (optional, slug)">
          <input className={inputCls} placeholder="keys-and-locks" value={form.id} onChange={set('id')} />
        </Field>
        <Field label="Title"><input className={inputCls} value={form.title} onChange={set('title')} /></Field>
        <Field label="Summary"><input className={inputCls} value={form.summary} onChange={set('summary')} /></Field>
        <Field label="Priority">
          <select className={inputCls} value={form.priority} onChange={set('priority')}>
            {PRIORITIES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <p className="text-base text-neutral-500">New features start at proposed and need human approval before implementation.</p>
        <div className="flex gap-2">
          <Button size="md" variant="outline" onPress={() => navigate('/pm')}>Cancel</Button>
          <Button size="md" isPending={busy} onPress={async () => {
            setBusy(true);
            try {
              const created = await api('POST', `${PM}/features`, {
                id: form.id || undefined, title: form.title,
                summary: form.summary, priority: form.priority,
              });
              await reload(); navigate(featurePath(created.id));
            } catch (e) { setError(e.message); setBusy(false); }
          }}>Create feature</Button>
        </div>
      </Card>
    </div>
  );
}

function TaskShow({ feature, task, reload, setError }) {
  const back = featurePath(feature.id);
  return (
    <div className="space-y-4">
      <PageLinks items={[['← Back to feature', back], ['Board list', '/pm'], ['Kanban', '/pm/board']]} />
      <Card className="p-5">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-60 flex-1">
            <h1 className="text-2xl font-semibold leading-snug">{task.title}</h1>
            <p className="mt-1 text-base text-neutral-500">{feature.id}/{task.id} · in {feature.title}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="md" onPress={() => navigate(`${taskPath(feature.id, task.id)}/edit`)}>Edit task</Button>
            <Button size="md" variant="danger-soft" onPress={async () => {
              try {
                await api('DELETE', `${PM}/features/${encodeURIComponent(feature.id)}/tasks/${encodeURIComponent(task.id)}`);
                await reload(); navigate(back);
              } catch (e) { setError(e.message); }
            }}>Archive</Button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <TaskStatusChip task={task} />
          <PriorityChip priority={task.priority} />
          {task.kind === 'review-fixes' && <Chip variant="soft">review-fixes</Chip>}
          {task.archived && <Chip variant="soft">archived</Chip>}
        </div>
        <dl className="mt-4 grid gap-x-6 gap-y-2 text-base sm:grid-cols-2">
          <div><dt className="font-semibold">Commit</dt><dd>{task.commit || '—'}</dd></div>
          <div><dt className="font-semibold">Requires</dt><dd>{(task.requires || []).join(', ') || '—'}</dd></div>
          <div><dt className="font-semibold">Created</dt><dd>{task.created || '—'}</dd></div>
          <div><dt className="font-semibold">Updated</dt><dd>{task.updated || '—'}</dd></div>
        </dl>
        <h2 className="mt-5 text-lg font-semibold">Description</h2>
        <p className="mt-1 whitespace-pre-wrap text-base leading-relaxed">{task.description || 'No description yet.'}</p>
        <h2 className="mt-5 text-lg font-semibold">Acceptance</h2>
        <p className="mt-1 whitespace-pre-wrap text-base leading-relaxed">{task.acceptance || 'No acceptance note yet.'}</p>
      </Card>
      <div>
        <h2 className="mb-3 text-xl font-semibold">Comments</h2>
        <Comments feature={feature} task={task} reload={reload} />
      </div>
    </div>
  );
}

function TaskEdit({ feature, task, reload, setError }) {
  const [form, setForm] = useState({
    title: task.title, description: task.description || '',
    acceptance: task.acceptance || '', status: taskStatus(task), priority: task.priority,
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const back = taskPath(feature.id, task.id);
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageLinks items={[['← Back to task', back], ['Back to feature', featurePath(feature.id)]]} />
      <Card className="space-y-4 p-5">
        <h1 className="text-2xl font-semibold">Edit task</h1>
        <Field label="Title"><input className={inputCls} value={form.title} onChange={set('title')} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Status">
            <select className={inputCls} value={form.status} onChange={set('status')}>
              {TASK_STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Priority">
            <select className={inputCls} value={form.priority} onChange={set('priority')}>
              {PRIORITIES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Description">
          <textarea className={inputCls} rows={5} value={form.description} onChange={set('description')} />
        </Field>
        <Field label="Acceptance">
          <textarea className={inputCls} rows={5} value={form.acceptance} onChange={set('acceptance')} />
        </Field>
        <div className="flex gap-2">
          <Button size="md" variant="outline" onPress={() => navigate(back)}>Cancel</Button>
          <Button size="md" isPending={busy} onPress={async () => {
            setBusy(true);
            try {
              await api('PUT', `${PM}/features/${encodeURIComponent(feature.id)}/tasks/${encodeURIComponent(task.id)}`, form);
              await reload(); navigate(back);
            } catch (e) { setError(e.message); setBusy(false); }
          }}>Save changes</Button>
        </div>
      </Card>
    </div>
  );
}

function TaskNew({ feature, reload, setError }) {
  const [form, setForm] = useState({ title: '', description: '', acceptance: '' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const back = featurePath(feature.id);
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageLinks items={[['← Back to feature', back]]} />
      <Card className="space-y-4 p-5">
        <h1 className="text-2xl font-semibold">New task in {feature.title}</h1>
        <Field label="Title"><input className={inputCls} value={form.title} onChange={set('title')} /></Field>
        <Field label="Description">
          <textarea className={inputCls} rows={4} value={form.description} onChange={set('description')} />
        </Field>
        <Field label="Acceptance">
          <textarea className={inputCls} rows={4} value={form.acceptance} onChange={set('acceptance')} />
        </Field>
        <div className="flex gap-2">
          <Button size="md" variant="outline" onPress={() => navigate(back)}>Cancel</Button>
          <Button size="md" isPending={busy} onPress={async () => {
            setBusy(true);
            try {
              const created = await api('POST', `${PM}/features/${encodeURIComponent(feature.id)}/tasks`, form);
              await reload(); navigate(taskPath(feature.id, created.id));
            } catch (e) { setError(e.message); setBusy(false); }
          }}>Create task</Button>
        </div>
      </Card>
    </div>
  );
}

function Pm({ route, features, reload, setError }) {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [featureFilter, setFeatureFilter] = useState('');
  const [busy, setBusy] = useState(false);

  async function act(fn) {
    setBusy(true);
    try { await fn(); await reload(); setError(''); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const visible = useMemo(() => features.filter((f) => {
    if (!showArchived && f.archived) return false;
    if (statusFilter && f.status !== statusFilter
      && !(f.tasks || []).some((t) => taskStatus(t) === statusFilter)) return false;
    if (!query) return true;
    const q = query.toLowerCase();
    return f.id.toLowerCase().includes(q) || f.title.toLowerCase().includes(q)
      || (f.tasks || []).some((t) => t.title.toLowerCase().includes(q) || t.id.includes(q));
  }), [features, showArchived, statusFilter, query]);

  if (route.view === 'feature-new') {
    return <FeatureNew reload={reload} setError={setError} />;
  }
  if (['feature-show', 'feature-edit', 'task-new',
    'task-show', 'task-edit'].includes(route.view)) {
    const f = features.find((x) => x.id === route.fid);
    if (!f) {
      return (
        <Card className="p-5 text-base">
          No feature named {route.fid}.{' '}
          <a className="underline" {...linkProps('/pm')}>Back to list</a>
        </Card>
      );
    }
    if (route.view === 'feature-show') return <FeatureShow feature={f} reload={reload} setError={setError} />;
    if (route.view === 'feature-edit') return <FeatureEdit feature={f} reload={reload} setError={setError} />;
    if (route.view === 'task-new') return <TaskNew feature={f} reload={reload} setError={setError} />;
    const task = (f.tasks || []).find((t) => t.id === route.tid);
    if (!task) {
      return (
        <Card className="p-5 text-base">
          No task named {route.tid} in {f.id}.{' '}
          <a className="underline" {...linkProps(featurePath(f.id))}>Back to feature</a>
        </Card>
      );
    }
    if (route.view === 'task-show') return <TaskShow feature={f} task={task} reload={reload} setError={setError} />;
    return <TaskEdit feature={f} task={task} reload={reload} setError={setError} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-semibold">Project Manager</h1>
        <Button size="md" variant={route.view === 'list' ? 'primary' : 'outline'}
          onPress={() => navigate('/pm')}>List</Button>
        <Button size="md" variant={route.view === 'board' ? 'primary' : 'outline'}
          onPress={() => navigate('/pm/board')}>Board</Button>
      </div>
      <PmToolbar features={visible} query={query} setQuery={setQuery}
        statusFilter={statusFilter} setStatusFilter={setStatusFilter}
        showArchived={showArchived} setShowArchived={setShowArchived}
        onSeed={() => act(() => api('POST', `${PM}/seed`))}
        onExport={() => act(() => api('POST', `${PM}/export`))} busy={busy} />
      {route.view === 'board'
        ? <Board features={visible} showArchived={showArchived}
            featureFilter={featureFilter} setFeatureFilter={setFeatureFilter}
            reload={reload} setError={setError} />
        : (
          <div className="space-y-3">
            {visible.map((f) => <FeatureCard key={f.id} feature={f} showArchived={showArchived} />)}
            {!visible.length && <Card className="p-5 text-base">No features match. Use Seed or New feature.</Card>}
          </div>
        )}
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState(() => parseRoute(location.pathname));
  const [features, setFeatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dark, setDark] = useState(() => localStorage.getItem('jolly-theme') === 'dark');

  useEffect(() => {
    const on = () => setRoute(parseRoute(location.pathname));
    window.addEventListener('popstate', on);
    return () => window.removeEventListener('popstate', on);
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('jolly-theme', dark ? 'dark' : 'light');
  }, [dark]);

  const reload = useCallback(async () => {
    try {
      const data = await api('GET', `${PM}/features`);
      setFeatures(data.features || []);
      setError('');
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }, []);
  useEffect(() => { reload(); }, [reload]);

  return (
    <Shell route={route} dark={dark} onToggleDark={() => setDark(!dark)}>
      {error && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 p-4 text-base text-red-800 dark:bg-red-950 dark:text-red-200"
          role="alert">{error}</div>
      )}
      {loading ? (
        <div className="flex items-center gap-2 p-6 text-base"><Spinner size="md" /> Loading board…</div>
      ) : route.view === 'home' ? <Home />
        : <Pm route={route} features={features} reload={reload} setError={setError} />}
    </Shell>
  );
}
