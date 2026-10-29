#!/usr/bin/env bash
# Derive keyed RGBA preview sprites from assets/published.
#
# Published assets are versioned by UTC stamp: <name>-YYYYMMDD-HHMMSS.png
# (file mtime at lift time). Lift a new version alongside the old ones and
# this script picks the newest stamp per asset; history is never overwritten.
#
# Reads assets/published/*.png (never modifies them) and writes:
#   tools/static/level-sprites/*.png  - keyed RGBA tiles + hue placeholders
#   tools/static/levels/chip1.json    - staged copy of levels/chip1.json
#
# The staged copy exists because tools/server.py only serves /static/* and
# /outputs/*, so a repo-root levels/ file would 404 under it. The canonical
# level file stays at levels/chip1.json; re-run this script after editing it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/assets/published"
OUT="$ROOT/tools/static/level-sprites"
LVL="$ROOT/tools/static/levels"
FFMPEG="${FFMPEG:-ffmpeg}"

command -v "$FFMPEG" >/dev/null || { echo "ffmpeg not found" >&2; exit 1; }
mkdir -p "$OUT" "$LVL"

# Newest stamped file wins; lexicographic sort == chronological for this stamp.
latest() {
  local match
  match=$(ls "$SRC/$1"-*.png 2>/dev/null | sort | tail -n 1)
  [ -n "$match" ] || { echo "no published version of $1 in $SRC" >&2; exit 1; }
  printf '%s' "$match"
}

# Full-bleed tiles: normalize to RGBA without touching colors.
for tile in floor_default wall portal wall_keyhole; do
  "$FFMPEG" -y -nostdin -v error -i "$(latest "$tile")" -vf "format=rgba" "$OUT/$tile.png"
done

# Green-screen sprites (#00FF00 backgrounds, measured corners ~0,253-255,0-32).
for sprite in jolly key orb; do
  "$FFMPEG" -y -nostdin -v error -i "$(latest "$sprite")" \
    -vf "colorkey=0x00FF00:0.20:0.10,format=rgba" "$OUT/$sprite.png"
done

# Gate: sprite on a near-white margin (measured border ~253-254).
"$FFMPEG" -y -nostdin -v error -i "$(latest gate)" \
  -vf "colorkey=0xFFFFFF:0.15:0.10,format=rgba" "$OUT/gate.png"

# Placeholder color variants by hue rotation. Base gold median hue is ~39
# degrees, so offsets land red ~0, yellow ~55, green ~130, blue ~205.
# Verified: hue after colorkey preserves the alpha channel.
while read -r color offset; do
  "$FFMPEG" -y -nostdin -v error -i "$(latest key)" \
    -vf "colorkey=0x00FF00:0.20:0.10,hue=h=$offset,format=rgba" \
    "$OUT/key_$color.png"
  "$FFMPEG" -y -nostdin -v error -i "$(latest wall_keyhole)" \
    -vf "hue=h=$offset,format=rgba" "$OUT/wall_keyhole_$color.png"
done <<'VARIANTS'
red -40
yellow 15
green 90
blue 165
VARIANTS

cp "$ROOT/levels/chip1.json" "$LVL/chip1.json"
echo "wrote $(ls "$OUT" | wc -l) sprites to $OUT"
