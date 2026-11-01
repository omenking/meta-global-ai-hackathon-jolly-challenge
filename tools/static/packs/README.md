# Packs

A pack is a folder, not a single js file:

```
packs/<pack-id>/
  main.js        the pack: tile/item defs, hooks, controllers
  manifest.json  every asset the pack uses, grouped by kind
  assets/        bundled asset files (only what the manifest marks bundled)
```

`manifest.json` mirrors the `assets:` list in the pack's candidate
mechanic file (`plans/level-design/candidate-mechanics/*.yml`). Each
entry names a `file`, its `kind` (`tiles`, `items`, `jolly_states`,
`gui`, `blocks`), what it `shows`, and whether it is `bundled`:

- `bundled: true` — the file lives in this pack's `assets/` and the
  game loads it from the pack: `packs/<pack-id>/assets/<file>`.
  Placeholder art comes from `tools/make_placeholder_sprites.sh`.
- `bundled: false` — shared art the pack reuses; the game loads it
  from `level-sprites/<file>` (derived from `assets/published` by
  `tools/prep_level_sprites.sh`).

`main.js` declares the same files through `defineAsset(name,
{pack, bundled})`; the registry turns that into the load URL, so no
loader keeps a hardcoded list. To add a pack: create the folder,
write the manifest first, generate or place its assets, then write
`main.js`.
