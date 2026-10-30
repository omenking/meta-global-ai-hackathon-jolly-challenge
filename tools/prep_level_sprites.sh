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
# The stamp must start with a digit: a bare "$1-*" glob would also match
# longer asset names sharing the prefix (jolly-fall-* as "jolly").
latest() {
  local match
  match=$(ls "$SRC/$1"-[0-9]*.png 2>/dev/null | sort | tail -n 1)
  [ -n "$match" ] || { echo "no published version of $1 in $SRC" >&2; exit 1; }
  printf '%s' "$match"
}

# Full-bleed tiles: normalize to RGBA without touching colors.
for tile in floor_default wall portal; do
  "$FFMPEG" -y -nostdin -v error -i "$(latest "$tile")" -vf "format=rgba" "$OUT/$tile.png"
done

# Green-screen sprites (#00FF00 backgrounds, measured corners ~0,253-255,0-32).
for sprite in jolly jolly-fall orb; do
  "$FFMPEG" -y -nostdin -v error -i "$(latest "$sprite")" \
    -vf "colorkey=0x00FF00:0.20:0.10,format=rgba" "$OUT/$sprite.png"
done

# Gate: sprite on a near-white margin (measured border ~253-254).
"$FFMPEG" -y -nostdin -v error -i "$(latest gate)" \
  -vf "colorkey=0xFFFFFF:0.15:0.10,format=rgba" "$OUT/gate.png"

# Keys and locks: real per-colour art in assets/published/lock_and_keys
# (5 combos, no colour shifting). Keys sit on green screen; keyhole
# tiles are full-bleed. The silver files are spelled "sliver" on disk.
# The generic key.png / wall_keyhole.png come from the gold combo.
LK="$SRC/lock_and_keys"
while read -r color filecolor; do
  "$FFMPEG" -y -nostdin -v error -i "$LK/key_$filecolor.png" \
    -vf "colorkey=0x00FF00:0.20:0.10,format=rgba" "$OUT/key_$color.png"
  "$FFMPEG" -y -nostdin -v error -i "$LK/keyhold_$filecolor.png" \
    -vf "format=rgba" "$OUT/wall_keyhole_$color.png"
done <<'COLORS'
red red
gold gold
green green
blue blue
silver sliver
COLORS
"$FFMPEG" -y -nostdin -v error -i "$LK/key_gold.png" \
  -vf "colorkey=0x00FF00:0.20:0.10,format=rgba" "$OUT/key.png"
"$FFMPEG" -y -nostdin -v error -i "$LK/keyhold_gold.png" \
  -vf "format=rgba" "$OUT/wall_keyhole.png"

# HUD sprites: the gui art in assets/published/gui is green-screen
# RGB (blue seven-segment digits, black labels, a black backplate
# with green outside its rounded corners). Key the green out to
# RGBA in tools/static/gui-sprites for the right-hand HUD column.
GUI="$SRC/gui"
GOUT="$ROOT/tools/static/gui-sprites"
mkdir -p "$GOUT"
for d in 0 1 2 3 4 5 6 7 8 9; do
  "$FFMPEG" -y -nostdin -v error -i "$GUI/$d.png" \
    -vf "colorkey=0x00FF00:0.20:0.10,format=rgba" "$GOUT/digit-$d.png"
done
for label in level time orbs; do
  "$FFMPEG" -y -nostdin -v error -i "$GUI/${label}_label.png" \
    -vf "colorkey=0x00FF00:0.20:0.10,format=rgba" "$GOUT/label-$label.png"
done
"$FFMPEG" -y -nostdin -v error -i "$GUI/backplate.png" \
  -vf "colorkey=0x00FF00:0.20:0.10,format=rgba" "$GOUT/backplate.png"

cp "$ROOT/levels/"*.json "$LVL/"
echo "wrote $(ls "$OUT" | wc -l) sprites to $OUT"
