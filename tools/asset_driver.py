#!/usr/bin/env python3
"""Bookkeeping CLI for the Muse asset driver.

The judgement loop itself runs in a Muse session: Muse generates
images with the Muse image tool, views them, and decides. This CLI
owns only the records around that loop, talking to a running asset
server over HTTP (the backend stays the sole writer of its YAML):

  brief      compose a turn prompt from a pack manifest entry
  import-turn upload generated files and import them as one turn
  judge      record Claude verdicts on outputs (API + report)
  publish    publish the winning output (API + report)
  status     print a session's outputs, verdicts and spend vs cap

With --report, import-turn/judge/publish also append to a structured
YAML run report at the moment they happen, so the report is captured
live during the loop, not reconstructed afterwards.

Run from the project root, for example:
  python tools/asset_driver.py brief --manifest \\
    .worktrees/mech-5-crumbling-tile/tools/static/packs/crumbling/manifest.json \\
    --file crumbling.png --dry-run
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

CHECKLIST = (
    "texture must fill the entire frame edge to edge with no margin/border; "
    "sharp square 90-degree corners, no rounding/bevel; "
    "opposite edges must match so 3x3 tiling shows no seams"
)

# Style ground, per plans/ai-asset-driver/GROUNDING.md: real sprites the
# generation call must carry as reference files, never text substitutes.
GROUND_SPRITES = ("tools/static/level-sprites/floor_default.png",
                  "tools/static/level-sprites/wall.png")


def compose_brief(manifest: dict, file_name: str, extra: str = "") -> str:
    """Turn prompt for one bundled pack asset from its manifest entry."""
    entry = next((a for a in manifest.get("assets", [])
                  if a.get("file") == file_name), None)
    if entry is None:
        raise SystemExit(f"{file_name} not in manifest for "
                         f"pack {manifest.get('pack')!r}")
    style = ("Top-down 2D puzzle-game tile, flat clean PC-98 game-art "
             "style, single square tile filling the frame, no text, "
             "no characters, muted stone palette matching a light gray "
             "stone floor with dark wall tiles")
    brief = (f"{style}. Subject: {entry.get('shows')}. {CHECKLIST}."
             " This tile is shown at 64px in game, so the read at small"
             " size matters more than fine detail. Ground the surface on"
             " the attached reference files "
             + " and ".join(GROUND_SPRITES)
             + " (the game's real floor and wall sprites): match their"
             " stone, speckle and grout exactly, ideally by editing the"
             " floor sprite itself. Marks must be exaggerated and"
             " high-contrast, bold near-black strokes about 8-12px wide"
             " at 512px, not realistic hairlines: a crack that vanishes"
             " at 64px does not exist.")
    if extra:
        brief += " " + extra
    return brief


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _load_report(path: Path) -> dict:
    if path.is_file():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def _save_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(report, sort_keys=False),
                    encoding="utf-8")


def cost_session_id(asset: str, session: str) -> str:
    """Cost-centre session id grouping one asset run's image usage."""
    return f"asset-driver-{asset}-{session}"


def cost_record_cmd(asset: str, session: str, turn_seq: int, images: int,
                    project: str, name: str, parent: str = "") -> list:
    """`meta-cost record` call capturing one turn's images as a new,
    named session in the Muse cost centre (its ingestion only counts
    muse-image model records, which the image tool never emits). The
    parent is the Muse session driving the loop, so the run rolls up
    under it in the cost centre's session tree."""
    cmd = ["meta-cost", "record", "--model", "muse-image-1.0",
           "--images", str(images), "--project", project,
           "--session", cost_session_id(asset, session),
           "--name", name, "--label", "asset-driver",
           "--tool", "asset-driver", "--billing-mode", "subscription",
           "--id", f"asset-{session}-t{turn_seq}"]
    if parent:
        cmd += ["--parent", parent]
    return cmd


def report_turn(path: Path, header: dict, turn: dict) -> dict:
    """Append one imported turn to the live YAML run report."""
    report = _load_report(path)
    if not report:
        report = dict(header)
        report["turns"] = []
    report["turns"].append(turn)
    report["spend_usd"] = str(round(sum(
        float(t.get("cost_total", 0)) for t in report["turns"]), 2))
    _save_report(path, report)
    return report


def report_judgements(path: Path, seq: int, verdicts: dict,
                      preferred: str = "") -> dict:
    """Record verdicts on one turn's outputs in the live YAML report."""
    report = _load_report(path)
    for turn in report.get("turns", []):
        if turn.get("seq") != seq:
            continue
        for out in turn.get("outputs", []):
            if out["key"] in verdicts:
                out["verdict"] = verdicts[out["key"]]
                out["author"] = "claude"
                out["preferred"] = out["key"] == preferred
    _save_report(path, report)
    return report


def report_publish(path: Path, output_key: str, pack_file: str) -> dict:
    """Record the published winner in the live YAML report."""
    report = _load_report(path)
    report["winner"] = output_key
    report["pack_file"] = pack_file
    report["finished"] = _now()
    _save_report(path, report)
    return report


def _call(base: str, method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:8322",
                    help="asset server base URL")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("brief")
    b.add_argument("--manifest", required=True)
    b.add_argument("--file", required=True)
    b.add_argument("--extra", default="")
    b.add_argument("--dry-run", action="store_true",
                   help="print the brief and loop plan, spend nothing")

    i = sub.add_parser("import-turn")
    i.add_argument("--session", required=True)
    i.add_argument("--prompt", required=True)
    i.add_argument("--muse-session", default="")
    i.add_argument("--references", default="",
                   help="comma-separated output file names")
    i.add_argument("--report", default="",
                   help="YAML run report to append this turn to, live")
    i.add_argument("--asset", default="")
    i.add_argument("--pack-target", default="")
    i.add_argument("--cost-name", default="",
                   help="cost-centre session name (default: derived)")
    i.add_argument("files", nargs="+", help="generated image files")

    j = sub.add_parser("judge")
    j.add_argument("--session", required=True)
    j.add_argument("--report", required=True)
    j.add_argument("--turn", type=int, required=True)
    j.add_argument("--preferred", default="")
    j.add_argument("verdicts", nargs="+", help="KEY=verdict text")

    p = sub.add_parser("publish")
    p.add_argument("--session", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--pack-target", default="")

    s = sub.add_parser("status")
    s.add_argument("--session", required=True)
    s.add_argument("--cap", type=float, default=2.0)

    args = ap.parse_args()
    if args.cmd == "brief":
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        print(compose_brief(manifest, args.file, args.extra))
        if args.dry_run:
            print("loop: turn1 x10 images -> verdicts -> turn2 x4 "
                  "with preferred references -> turn3 x4 if needed; "
                  "stop on checklist pass or budget cap")
        return 0
    if args.cmd == "import-turn":
        names = []
        for f in args.files:
            data = Path(f).read_bytes()
            rec = _call(args.base, "POST", "/api/uploads", {
                "filename": Path(f).name,
                "data_b64": base64.b64encode(data).decode()})
            names.append(rec["file"])
        refs = [r for r in args.references.split(",") if r]
        turn = _call(args.base, "POST",
                     f"/api/sessions/{args.session}/turns/import", {
                         "prompt": args.prompt,
                         "references": refs,
                         "files": names,
                         "muse_session_id": args.muse_session})
        view = _call(args.base, "GET", f"/api/sessions/{args.session}")
        asset = args.asset or view["asset_name"]
        root = Path(__file__).resolve().parent.parent
        cost_name = args.cost_name or (
            f"Asset driver: {asset} — session {args.session}")
        cost_cmd = cost_record_cmd(asset, args.session, turn["seq"],
                                   len(turn["outputs"]), root.name,
                                   cost_name, parent=args.muse_session)
        try:
            done = subprocess.run(cost_cmd, capture_output=True, text=True,
                                  timeout=30)
            cost_recorded = done.returncode == 0
            if not cost_recorded:
                print(f"warning: meta-cost record failed: "
                      f"{done.stderr.strip()}", file=sys.stderr)
        except OSError as exc:
            cost_recorded = False
            print(f"warning: meta-cost not recorded ({exc}); image spend "
                  f"exists only in the asset session", file=sys.stderr)
        if args.report:
            report_turn(Path(args.report), {
                "asset": args.asset or view["asset_name"],
                "session": args.session,
                "muse_session": args.muse_session,
                "project": root.name,
                "project_root": str(root),
                "capture": "live, appended by asset_driver as turns happen",
                "started": _now(),
                "budget": {"target_usd": "1.00", "cap_usd": "2.00"},
            }, {
                "seq": turn["seq"], "at": _now(), "prompt": args.prompt,
                "references": refs,
                "generated_files": [str(f) for f in args.files],
                "outputs": [{"key": o["key"], "path": o["path"]}
                            for o in turn["outputs"]],
                "cost_total": turn["cost_total"],
                "cost_centre_session": cost_session_id(asset, args.session),
                "cost_centre_name": cost_name,
                "cost_centre_parent": args.muse_session,
                "cost_centre_recorded": cost_recorded,
            })
        print(json.dumps({"seq": turn["seq"],
                          "outputs": [o["key"] for o in turn["outputs"]],
                          "cost_total": turn["cost_total"]}, indent=1))
        return 0
    if args.cmd == "judge":
        verdicts = {}
        for item in args.verdicts:
            key, _, text = item.partition("=")
            verdicts[key] = text
        for key, text in verdicts.items():
            _call(args.base, "PUT", f"/api/judgements/{key}", {
                "human_review": text, "author": "claude",
                "preferred": key == args.preferred})
        report_judgements(Path(args.report), args.turn, verdicts,
                          args.preferred)
        print(json.dumps({"judged": len(verdicts),
                          "preferred": args.preferred}, indent=1))
        return 0
    if args.cmd == "publish":
        _call(args.base, "POST", f"/api/sessions/{args.session}/publish",
              {"output_key": args.key})
        report_publish(Path(args.report), args.key, args.pack_target)
        print(json.dumps({"published": args.key}, indent=1))
        return 0
    if args.cmd == "status":
        view = _call(args.base, "GET", f"/api/sessions/{args.session}")
        judged = sum(1 for t in view["turns"] for o in t["outputs"]
                     if o.get("human_review"))
        print(json.dumps({"session": view["id"], "spend": view["spend"],
                          "cap_usd": f"{args.cap:.2f}",
                          "outputs_judged": judged,
                          "over_cap": float(view["spend"]["spend_usd"]) > args.cap},
                         indent=1))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
