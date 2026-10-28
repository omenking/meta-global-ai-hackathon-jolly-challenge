# Meta-Global-AI-Hackathon Jolly's Challenge

- [Technical Uncertainty](./docs/technical-uncertainty.md)
- [Technical Limitations](.docs/technical-limitations.md)
- [Game Environment](./docs/game-env.md)
- [Game Testing Research](./docs/game-testing-research.md)
- [Game Lore and Mechanics](./docs/game-lore-and-mechanics.md)
- [Community Tools to Track Usage](./docs/community-tools-to-track-usage.md)
- [Mininal Graphical Assets](./docs/minimal-graphical-assets.md)

## Asset Design Tool

Iterate on generated tile art from a local UI instead of hand-editing YAML.
The backend owns `assets/manifest.yml` and `assets/judgements.yml`; every
run goes through `scripts/gen-image` once and is reported to Meta Cost Center
(needs a `meta-cost` with the `record` command; otherwise you get a warning
and the image still saves).

```sh
source .venv/bin/activate
python tools/server.py
```

Then open http://127.0.0.1:8321/ in a browser. See
[plans/iterative-asset-design-tool.md](./plans/iterative-asset-design-tool.md).

### Lottery runs (1–10 images)

On the Run page choose N (default 4). One action makes one Meta Image 1.0
call producing N images (~$0.01/image); the run log shows the total and each
image shows its share. There is no parent picker: on the version itself
(New/Edit version form) tick up to 10 specific images from any prior run —
nothing is pre-ticked. Each chosen image shows its judgement with a "bring
judgement" toggle plus a per-image note field; "Build prompt from selected
images" composes notes and judgement constraints into the prompt (repeat
builds replace their own previous output, hand edits are kept). A live
edit-vs-text-only mode line confirms what will run. The Run page just
confirms the version's stored selection and N, then runs. N=1 behaves
exactly as before.

After a batch, the Judge view shows a clickable grid; judge each, then
"Save + create next version" marks the winner preferred and opens a new
version with that winner pre-ticked.