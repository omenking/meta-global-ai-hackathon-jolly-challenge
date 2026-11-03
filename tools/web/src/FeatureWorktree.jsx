import { Button, Card, Chip } from '@heroui/react';
import { useEffect, useState } from 'react';
import { api } from './api.js';
import { findFeatureWorktree, featureGamePath } from './featureWorktree.js';

export default function FeatureWorktree({ feature }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    let pending = false;
    async function refresh() {
      if (pending) return;
      pending = true;
      try {
        const result = await api('GET', '/api/worktrees');
        if (active) setData(result);
      } catch (e) { if (active) setError(e.message); }
      finally { pending = false; }
    }
    setData(null);
    setError('');
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [feature.id, feature.worktree]);
  const wt = data && findFeatureWorktree(data, feature);
  const servers = wt?.servers || [];
  const live = servers.filter((s) => s.listening);
  const gamePath = featureGamePath(feature);
  async function launch() {
    setBusy(true); setError('');
    try {
      const server = await api('POST', '/api/worktrees/start', { path: wt.path });
      setData((current) => ({ ...current, worktrees: current.worktrees.map((w) =>
        w.path === wt.path ? { ...w, servers: [{ ...server, listening: true }] } : w) }));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function stop(server) {
    if (!confirm(`Stop ${feature.title} on port ${server.port}?`)) return;
    setBusy(true); setError('');
    try {
      await api('POST', '/api/worktrees/stop', { pid: server.pid });
      setData(await api('GET', '/api/worktrees'));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return (
    <Card className="space-y-3 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex-1 text-lg font-semibold">Worktree &amp; playtest</h2>
        <Chip variant="soft" color={live.length ? 'success' : 'default'}>
          {!data ? 'Loading…' : !wt?.exists ? 'Unavailable' : live.length ? 'Running' : 'Not running'}
        </Chip>
      </div>
      <p className="break-all font-mono text-sm">{wt?.path || feature.worktree || `.worktrees/${feature.id}`}</p>
      <p className="text-sm text-black dark:text-neutral-100">Branch: {wt?.branch || feature.branch || `feat/${feature.id}`}</p>
      <p className="break-all text-sm">Feature path: <code>{gamePath}</code></p>
      {!feature.test_level && <p className="text-sm text-black dark:text-neutral-100">No test level assigned. Open the game to choose a map.</p>}
      {data && !wt?.exists && <p className="text-sm text-black dark:text-neutral-100">The associated worktree is missing or no longer registered.</p>}
      {wt?.exists && !wt.bare && !wt.prunable && !live.length &&
        <Button isDisabled={busy} isPending={busy} onPress={launch}>Launch worktree</Button>}
      {servers.map((server) => {
        const url = new URL(gamePath, server.url).href;
        return <div key={server.pid} className="space-y-2">
          {server.listening && <a className="block break-all text-blue-700 underline dark:text-blue-300"
            href={url} target="_blank" rel="noreferrer">Open {feature.test_level || 'game'} ↗<span className="block text-sm">{url}</span></a>}
          <Button variant="danger-soft" isDisabled={busy || server.is_self}
            onPress={() => stop(server)}>Stop :{server.port}</Button>
          {server.is_self && <p className="text-sm text-black dark:text-neutral-100">This server is serving this page; stop it from another server.</p>}
        </div>;
      })}
      {error && <p role="alert" className="whitespace-pre-wrap text-sm text-red-600">{error}</p>}
    </Card>
  );
}
