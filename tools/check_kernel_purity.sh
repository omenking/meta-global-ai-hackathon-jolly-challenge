#!/bin/sh
# Kernel purity gate (refactor Phase 0 baseline; Phases 1-3 shrink to zero).
# Counts mechanic-specific literals in kernel-bound files. Kernel files
# must eventually contain no orb/gate/warp/key-lock/colour knowledge.
# Usage: tools/check_kernel_purity.sh [--strict] [file ...]
#   --strict  exit 1 when any hit remains (target state after Phase 3).
set -u
strict=0
if [ "${1:-}" = "--strict" ]; then strict=1; shift; fi
if [ "$#" -gt 0 ]; then files="$*"; else
  # Kernel scope only: packs legitimately own mechanic literals, and
  # game-core.js is a compatibility facade (legacy char helpers).
  files="tools/static/engine/kernel.js tools/static/engine/registry.js tools/static/engine/camera.js"
fi
patterns="isOrb|isWarp|countOrbs|key_color|lock_color|KEY_COLORS|orbs_left|gate_open"
total=0
for f in $files; do
  [ -f "$f" ] || continue
  n=$(grep -Ec "$patterns" "$f" || true)
  echo "$f: $n mechanic-pattern line(s)"
  total=$((total + n))
done
echo "total: $total"
if [ "$strict" = "1" ] && [ "$total" -gt 0 ]; then exit 1; fi
exit 0
