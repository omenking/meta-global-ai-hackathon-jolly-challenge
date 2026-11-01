# Grounding for AI-generated pack assets

This document is the ground the asset driver must stand on before any
image is generated. It exists because the first crumbling run broke both
rules below and still passed its own judging: the art was plausible
stone, but it was not this game's stone, and its cracks were realistic
at 512px and nearly invisible at the size the game actually shows.

## Rule 1: generate from the game's real sprites, never from a description

The style ground is the shipped sprite set in
`tools/static/level-sprites/`:

- `floor_default.png` — the floor every tile sits on: light grey stone,
  average RGB about (204, 205, 205), fine dark speckle, subtle grout
  edge. A floor-family tile must read as this exact surface, damaged.
- `wall.png` — the wall: dark grey, average RGB about (70, 74, 77),
  same speckle language at the opposite end of the value scale.
- `orb.png`, `jolly.png` — accent and character art; useful only as a
  palette/feel reference, never as a surface to imitate.

What this means in the loop:

- Every generation call for a floor-family asset passes
  `floor_default.png` (and `wall.png` when the asset touches walls) as
  actual reference image files to the image tool. A text description
  such as "light gray stone matching the floor" is not grounding; the
  first crumbling run used only text and produced a similar-but-wrong
  stone, with different speckle and no grout relationship.
- For staged damage (crumbling and its successors), prefer editing the
  ground sprite itself: pass `floor_default.png` as the base image and
  ask for cracks on that tile, so stage zero is the game's floor by
  construction and each later stage inherits the identical surface.
- Stage-to-stage references (winner of the previous stage) are in
  addition to the ground sprite, never instead of it.

## Rule 2: judge at camera scale, with exaggerated marks

Tiles render at 64px in game. One pixel at 64px is eight pixels at
512px, so a realistic 2-3px hairline crack at 512px is sub-pixel in
game and does not exist. Realism is the wrong target; legibility is.

- Crack strokes must be bold and near-black on the light stone:
  roughly 8-12px wide at 512px or wider for major damage, so they
  survive the downscale as clear dark lines.
- Each stage must be identifiable at 64px, side by side with its
  neighbours and in a room screenshot, within a glance. If intact,
  minor and major cannot be told apart at 64px without zooming, the
  run has failed even if every 512px image is beautiful.
- The first crumbling run accepted exactly that failure: the intact
  winner's single hairline and the minor web were realistic, and both
  nearly vanish at camera scale beside the plain floor. Judge harsher:
  when in doubt at 64px, reject and regenerate bolder.

## Pre-flight checklist for the driver

1. Reference files attached to the generation call include the ground
   sprite(s) named above, recorded by file name in the turn and in
   the YAML run report.
2. The brief states the display size (64px) and demands exaggerated,
   high-contrast marks, not realistic ones.
3. Judging views every candidate downscaled to 64px, beside the real
   floor sprite and the neighbouring stages, before any verdict.
4. The final check is an in-room screenshot at playing scale, not the
   512px files.
