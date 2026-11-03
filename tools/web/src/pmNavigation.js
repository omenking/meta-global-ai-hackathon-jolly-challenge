// Keep the collection a ticket was opened from throughout its detail/edit pages.
export function pmNavigationState(to, from, state = {}) {
  const ticket = (path) => path.match(/^\/pm\/features\/([^/]+)(?:\/|$)/)?.[1];
  if (!ticket(to)) return null;
  if (/^\/pm\/epics\/[^/]+$/.test(from) || ['/pm', '/pm/epics'].includes(from)) {
    return { pmReturnTo: from };
  }
  if (ticket(to) === ticket(from) && state?.pmReturnTo) {
    return { pmReturnTo: state.pmReturnTo };
  }
  return null;
}

export function pmBackLink(state) {
  const path = state?.pmReturnTo;
  if (/^\/pm\/epics\/[^/]+$/.test(path || '')) return ['← Back to epic', path];
  if (path === '/pm/epics') return ['← Back to epics', path];
  return ['← Feature list', '/pm'];
}
