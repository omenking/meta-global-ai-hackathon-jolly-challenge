#!/usr/bin/env bash
# Make placeholder sprites of the right size and correct name.
#
# Future packs list the assets they need in their candidate mechanic
# file (plans/level-design/candidate-mechanics/*.yml, `assets:`), but
# the art does not exist yet. This script fills each listed name with
# a labelled 512x512 RGBA PNG (the size every level sprite uses; the
# game scales by TILE/512) so a pack can be built and playtested
# before real art lands. Existing files are never overwritten unless
# --force is given, so real art is safe.
#
# Usage:
#   tools/make_placeholder_sprites.sh [--out DIR] [--force] name.png [...]
#   tools/make_placeholder_sprites.sh --candidate terrain-and-hazards.yml 5 [--out DIR]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FFMPEG="${FFMPEG:-ffmpeg}"
command -v "$FFMPEG" >/dev/null || { echo "ffmpeg not found" >&2; exit 1; }

OUT="$ROOT/tools/static/level-sprites"
FORCE=0
CANDIDATE=""
CID=""
NAMES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --candidate) CANDIDATE="$2"; CID="$3"; shift 3 ;;
    --) shift; while [ $# -gt 0 ]; do NAMES+=("$1"); shift; done ;;
    -*) echo "unknown option $1" >&2; exit 1 ;;
    *) NAMES+=("$1"); shift ;;
  esac
done

if [ -n "$CANDIDATE" ]; then
  while IFS= read -r name; do
    [ -n "$name" ] && NAMES+=("$name")
  done < <(python3 - "$ROOT/plans/level-design/candidate-mechanics/$CANDIDATE" "$CID" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as fh:
    data = yaml.safe_load(fh)
mech = next((m for m in data.get("mechanics", [])
             if str(m.get("id")) == sys.argv[2]), None)
if mech is None:
    sys.exit(f"mechanic {sys.argv[2]} not found in {sys.argv[1]}")
for kind in ("tiles", "jolly_states", "gui", "blocks"):
    for entry in (mech.get("assets") or {}).get(kind) or []:
        name = entry.get("file") if isinstance(entry, dict) else entry
        if name:
            print(name)
PY
)
fi
[ "${#NAMES[@]}" -gt 0 ] || {
  echo "usage: $0 [--out DIR] [--force] name.png [...] | --candidate <file> <id>" >&2
  exit 1
}

mkdir -p "$OUT"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
[ -f "$FONT" ] || FONT=""

# Distinct flat colour per file name (stable across runs and order).
PALETTE=(0xB08968 0x5B8C5A 0x4A6FA5 0xC1666B 0x7D5BA6 0x2A9D8F 0xE9C46A 0x9C6644)
for name in "${NAMES[@]}"; do
  case "$name" in
    *.png) ;;
    *) echo "skip $name: placeholders are .png files" >&2; continue ;;
  esac
  dest="$OUT/$name"
  if [ -f "$dest" ] && [ "$FORCE" -eq 0 ]; then
    echo "exists, skipped: $dest (use --force to remake)"
    continue
  fi
  hash=$(printf '%s' "$name" | md5sum | cut -c1-2)
  color="${PALETTE[$((16#$hash % ${#PALETTE[@]}))]}"
  label="${name%.png}"
  vf="format=rgba"
  if [ -n "$FONT" ]; then
    vf="drawtext=fontfile=$FONT:text='$label':fontsize=40:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2,format=rgba"
  fi
  "$FFMPEG" -y -nostdin -v error -f lavfi \
    -i "color=c=$color:s=512x512" -frames:v 1 -vf "$vf" \
    -pix_fmt rgba "$dest"
  echo "wrote placeholder $dest"
done
