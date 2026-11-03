export function featureGamePath(feature) {
  return '/game' + (feature.test_level ? '?level=' + encodeURIComponent(feature.test_level) : '');
}

export function findFeatureWorktree(data, feature) {
  const configured = feature.worktree || `.worktrees/${feature.id}`;
  const root = data.worktrees.find((wt) => wt.is_main)?.path;
  const path = configured.startsWith('/') ? configured : root && `${root}/${configured.replace(/^\.\//, '')}`;
  return data.worktrees.find((wt) => wt.path === path) || null;
}
