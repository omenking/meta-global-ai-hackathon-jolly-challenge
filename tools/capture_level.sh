#!/usr/bin/env bash
# Capture a level-preview render to screenshots/.
# Usage: tools/capture_level.sh [--url URL] [--outdir DIR] [--compare] <level>
#        tools/capture_level.sh --page game --feature <feature-id> \
#          [--url http://127.0.0.1:<worktree-port>] <test-level>
# Picks a Python with Playwright available, then delegates.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for PY in "$ROOT/.venv/bin/python" python3; do
  if "$PY" -c "import playwright.sync_api" >/dev/null 2>&1; then
    exec "$PY" "$ROOT/tools/capture_level.py" "$@"
  fi
done
echo "capture_level.sh: no python with playwright found" >&2
exit 1
