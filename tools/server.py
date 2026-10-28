#!/usr/bin/env python3
"""Local UI tool for iterative game-asset design.

Serves the three-pane frontend and a JSON API over the backend-owned
``assets/manifest.yml`` and ``assets/judgements.yml``. Generation runs go
through ``scripts/gen-image`` one at a time (single-run lock) so spend is
recorded exactly once per call in Meta Cost Center.

Run from the project root::

    source .venv/bin/activate
    python tools/server.py [--port 8321]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from asset_store import (StoreError, add_version, build_prompt_draft,
                         create_asset, get_version, load_judgements,
                         load_manifest, lottery_keys, mark_failed,
                         normalize_run_count, record_output, save_judgement,
                         save_judgements, save_manifest, split_cost_per_output,
                         update_asset, update_version, validate_references,
                         validate_run_not_noop)

GEN_SCRIPT = ROOT / "scripts" / "gen-image"
OUTPUTS_DIR = ROOT / "assets" / "outputs"
STATIC_DIR = Path(__file__).resolve().parent / "static"

COST_RE = re.compile(r"~\$(\d+\.\d+) recorded in Cost Center")
ORIG_RE = re.compile(r"^saved original (.+)$", re.M)
DIMS_RE = re.compile(r"requested=(\d+)x(\d+), raw=(\d+x\d+|unknown), saved=(\d+x\d+|unknown)")
REQUESTED_RE = re.compile(r"requested=(\d+)x(\d+)")
FILE_DIMS_RE = re.compile(r"^\s*(.+): raw=(\d+x\d+|unknown), saved=(\d+x\d+|unknown)\s*$", re.M)
RUN_TIMEOUT_S = 600

STATE_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()
RUNS: dict[str, dict] = {}
RUN_SEQ = 0


class State:
    def __init__(self) -> None:
        self.assets, self.header = load_manifest()
        self.judgements, self.jheader = load_judgements()
        # Persist the migrated versions shape on first tool run.
        save_manifest(self.assets, self.header)

    def save_all(self) -> None:
        save_manifest(self.assets, self.header)
        save_judgements(self.judgements, self.jheader)


STATE = State()


def _send(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    try:
        data = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise StoreError("request body must be JSON")
    return data if isinstance(data, dict) else {}


def _asset_view(name: str) -> dict:
    asset = STATE.assets[name]
    versions = []
    for version in asset["versions"]:
        outputs = []
        for output in version["outputs"]:
            record = dict(output)
            judge = STATE.judgements.get(output["key"], {})
            record["human_review"] = judge.get("human_review", "")
            record["checklist"] = judge.get("checklist") or {}
            record["preferred"] = bool(judge.get("preferred"))
            outputs.append(record)
        view = dict(version)
        view["outputs"] = outputs
        versions.append(view)
    return {"name": name, "width": asset["width"],
            "height": asset["height"], "versions": versions}


def _relativize_output_path(text: str) -> str:
    """Return a repo-relative path when possible, else the raw text."""
    try:
        return str(Path(text.strip()).resolve().relative_to(ROOT.resolve()))
    except (ValueError, OSError):
        return text.strip()


def _run_generation(asset_name: str, slug: str, references: list | None,
                    num: object = None) -> dict:
    """Run scripts/gen-image once for a version; caller holds no locks.

    Lottery mode: num 1-10 produces that many outputs in one API call.
    N=1 keeps the legacy bare key; N>1 uses <base>-1..-N keys.
    References of None runs with the version's stored selection; an
    explicit list (possibly empty) overrides it and is saved back to the
    version so the record shows what actually ran.
    """
    global RUN_SEQ
    count = normalize_run_count(num)
    asset = STATE.assets.get(asset_name)
    if asset is None:
        raise StoreError(f"asset {asset_name!r} does not exist")
    version = get_version(asset, slug)
    if references is None:
        cleaned_refs = validate_references(version.get("references"))
        save_refs_back = False
    else:
        cleaned_refs = validate_references(references)
        save_refs_back = True
    prompt = (version.get("prompt") or "").strip()
    if not prompt:
        raise StoreError("prompt must not be empty")
    parent = None
    if version.get("parent"):
        try:
            parent = get_version(asset, version["parent"])
        except StoreError:
            parent = None
    validate_run_not_noop(version, parent, cleaned_refs)
    width = version.get("width") or asset.get("width")
    height = version.get("height") or asset.get("height")
    if not width or not height:
        raise StoreError("asset needs width and height before running")

    ref_paths = []
    for ref in cleaned_refs:
        candidate = (OUTPUTS_DIR / str(ref)).resolve()
        if OUTPUTS_DIR.resolve() not in candidate.parents and candidate != OUTPUTS_DIR.resolve():
            raise StoreError(f"reference {ref!r} is outside assets/outputs")
        if not candidate.is_file():
            raise StoreError(f"reference image not found: {ref!r}")
        ref_paths.append(str(candidate))

    if save_refs_back and cleaned_refs != list(version.get("references") or []):
        with STATE_LOCK:
            version["references"] = cleaned_refs
            STATE.save_all()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = f"{asset_name}-{slug}-{stamp}"
    keys = lottery_keys(base, count)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    if count == 1:
        out_base_abs = OUTPUTS_DIR / f"{base}.png"
        expected_abs = [OUTPUTS_DIR / f"{keys[0]}.png"]
    else:
        out_base_abs = OUTPUTS_DIR / f"{base}.png"
        expected_abs = [OUTPUTS_DIR / f"{k}.png" for k in keys]

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(prompt)
        prompt_file = fh.name
    try:
        cmd = [sys.executable, str(GEN_SCRIPT), "--prompt-file", prompt_file,
               "--width", str(width), "--height", str(height),
               "--num", str(count),
               "-o", str(out_base_abs)]
        for ref in ref_paths:
            cmd += ["-i", ref]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=RUN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        with STATE_LOCK:
            mark_failed(STATE.assets, asset_name, slug)
            STATE.save_all()
        raise StoreError(f"generation timed out after {RUN_TIMEOUT_S}s")
    finally:
        Path(prompt_file).unlink(missing_ok=True)

    stdout, stderr = proc.stdout or "", proc.stderr or ""
    if proc.returncode != 0:
        with STATE_LOCK:
            mark_failed(STATE.assets, asset_name, slug)
            STATE.save_all()
        raise StoreError(f"generation failed: {(stderr or stdout).strip()[-500:]}")

    missing = [str(p) for p in expected_abs if not p.is_file()]
    if missing:
        with STATE_LOCK:
            mark_failed(STATE.assets, asset_name, slug)
            STATE.save_all()
        raise StoreError(
            f"generation returned {count - len(missing)} of {count} images; "
            f"missing: {', '.join(missing)}")

    cost_match = COST_RE.search(stdout)
    total_usd = cost_match.group(1) if cost_match else None
    per_output_usd = split_cost_per_output(total_usd, count)
    recording_warning = next(
        (line for line in stderr.splitlines() if "Cost Center" in line), "")

    orig_texts = ORIG_RE.findall(stdout)
    file_dims = list(FILE_DIMS_RE.finditer(stdout))
    requested_fallback = REQUESTED_RE.search(stdout)

    outputs_info: list[dict] = []
    for idx, key in enumerate(keys):
        if count == 1:
            dims_match = DIMS_RE.search(stdout)
            if dims_match:
                requested_width = int(dims_match.group(1))
                requested_height = int(dims_match.group(2))
                raw_text = dims_match.group(3)
                if "x" in raw_text:
                    raw_width, raw_height = (int(v) for v in raw_text.split("x"))
                else:
                    raw_width, raw_height = None, None
            elif requested_fallback:
                requested_width, requested_height = int(requested_fallback.group(1)), int(requested_fallback.group(2))
                raw_width, raw_height = None, None
            else:
                requested_width, requested_height, raw_width, raw_height = width, height, None, None
            original_path = _relativize_output_path(orig_texts[0]) if orig_texts else None
        else:
            if requested_fallback:
                requested_width, requested_height = int(requested_fallback.group(1)), int(requested_fallback.group(2))
            else:
                requested_width, requested_height = width, height
            raw_width, raw_height = None, None
            for m in file_dims:
                if key in (m.group(1) or ""):
                    raw_text, saved_text = m.group(2), m.group(3)
                    if "x" in raw_text:
                        raw_width, raw_height = (int(v) for v in raw_text.split("x"))
                    break
            original_path = None
            if len(orig_texts) == len(keys):
                original_path = _relativize_output_path(orig_texts[idx])
            else:
                for text in orig_texts:
                    if key in text:
                        original_path = _relativize_output_path(text)
                        break
        outputs_info.append({
            "key": key,
            "path": f"assets/outputs/{key}.png",
            "original_path": original_path,
            "requested_width": requested_width,
            "requested_height": requested_height,
            "raw_width": raw_width,
            "raw_height": raw_height,
            "estimated_usd": per_output_usd,
        })

    with STATE_LOCK:
        stored_outputs = []
        for info in outputs_info:
            stored = record_output(
                STATE.assets, asset_name, slug, info["key"], info["path"],
                info["estimated_usd"], original_path=info["original_path"],
                requested_width=info["requested_width"],
                requested_height=info["requested_height"],
                raw_width=info["raw_width"], raw_height=info["raw_height"])
            stored_outputs.append(stored)
        STATE.save_all()
        RUN_SEQ += 1
        run_id = f"run-{RUN_SEQ}"
        first = stored_outputs[0]
        record = {
            "id": run_id,
            "asset": asset_name,
            "version": slug,
            "num": count,
            "keys": [o["key"] for o in stored_outputs],
            "outputs": stored_outputs,
            "total_estimated_usd": total_usd,
            # Back-compat single-output fields (first output).
            "key": first["key"],
            "path": first["path"],
            "original_path": first.get("original_path"),
            "requested_width": first.get("requested_width"),
            "requested_height": first.get("requested_height"),
            "raw_width": first.get("raw_width"),
            "raw_height": first.get("raw_height"),
            "estimated_usd": total_usd,
            "recording_warning": recording_warning,
            "log": (stdout + stderr)[-2000:],
        }
        RUNS[run_id] = record
    return record


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "AssetTool/1.0"

    def log_message(self, fmt, *args):  # quieter stderr logging
        sys.stderr.write("asset-tool: " + fmt % args + "\n")

    def _serve_file(self, path: Path) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            _send(self, 404, {"error": "not found"})
            return
        ctype = CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            if not parts:
                return self._serve_file(STATIC_DIR / "index.html")
            if parts[0] == "static":
                target = (STATIC_DIR / "/".join(parts[1:])).resolve()
                if STATIC_DIR.resolve() not in target.parents:
                    return _send(self, 404, {"error": "not found"})
                return self._serve_file(target)
            if parts[0] == "outputs":
                target = (OUTPUTS_DIR / "/".join(parts[1:])).resolve()
                if OUTPUTS_DIR.resolve() not in target.parents:
                    return _send(self, 404, {"error": "not found"})
                return self._serve_file(target)
            if parts == ["api", "assets"]:
                with STATE_LOCK:
                    names = sorted(STATE.assets)
                    payload = [_asset_view(n) for n in names]
                return _send(self, 200, {"assets": payload})
            if len(parts) == 3 and parts[:2] == ["api", "assets"]:
                name = urllib.parse.unquote(parts[2])
                with STATE_LOCK:
                    if name not in STATE.assets:
                        return _send(self, 404, {"error": f"asset {name!r} not found"})
                    return _send(self, 200, _asset_view(name))
            if len(parts) == 3 and parts[:2] == ["api", "runs"]:
                record = RUNS.get(parts[2])
                if record is None:
                    return _send(self, 404, {"error": "run not found"})
                return _send(self, 200, record)
            if parts[:1] == ["api"]:
                return _send(self, 404, {"error": "not found"})
            return self._serve_file(STATIC_DIR / "index.html")
        except StoreError as exc:
            return _send(self, 400, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            body = _read_json(self)
            if parts == ["api", "assets"]:
                with STATE_LOCK:
                    asset = create_asset(STATE.assets, body.get("name", ""),
                                         body.get("width", 512),
                                         body.get("height", 512))
                    STATE.save_all()
                    return _send(self, 201, _asset_view(body["name"]))
            if len(parts) == 4 and parts[:2] == ["api", "assets"] and parts[3] == "versions":
                name = urllib.parse.unquote(parts[2])
                with STATE_LOCK:
                    if name not in STATE.assets:
                        return _send(self, 404, {"error": f"asset {name!r} not found"})
                    version = add_version(
                        STATE.assets, name, body.get("slug", ""),
                        body.get("desc", ""), body.get("prompt", ""),
                        parent=body.get("parent"),
                        width=body.get("width"), height=body.get("height"),
                        references=body.get("references", None))
                    STATE.save_all()
                return _send(self, 201, version)
            if parts == ["api", "runs"]:
                if not RUN_LOCK.acquire(blocking=False):
                    return _send(self, 409,
                                 {"error": "a generation is already running"})
                try:
                    record = _run_generation(body.get("asset", ""),
                                             body.get("version", ""),
                                             body.get("references", None),
                                             body.get("num", None))
                finally:
                    RUN_LOCK.release()
                return _send(self, 201, record)
            return _send(self, 404, {"error": "not found"})
        except StoreError as exc:
            return _send(self, 400, {"error": str(exc)})

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            if len(parts) == 3 and parts[:2] == ["api", "assets"]:
                name = urllib.parse.unquote(parts[2])
                body = _read_json(self)
                with STATE_LOCK:
                    if name not in STATE.assets:
                        return _send(self, 404, {"error": f"asset {name!r} not found"})
                    try:
                        update_asset(STATE.assets, name,
                                     body.get("width", 512),
                                     body.get("height", 512))
                    except StoreError as exc:
                        return _send(self, 400, {"error": str(exc)})
                    STATE.save_all()
                return _send(self, 200, _asset_view(name))
            if len(parts) == 5 and parts[:2] == ["api", "assets"] and parts[3] == "versions":
                name = urllib.parse.unquote(parts[2])
                slug = urllib.parse.unquote(parts[4])
                body = _read_json(self)
                with STATE_LOCK:
                    if name not in STATE.assets:
                        return _send(self, 404, {"error": f"asset {name!r} not found"})
                    try:
                        version = update_version(
                            STATE.assets, name, slug,
                            body.get("desc", ""), body.get("prompt", ""),
                            body.get("width"), body.get("height"),
                            body.get("references", None))
                    except StoreError as exc:
                        if "does not exist" in str(exc):
                            return _send(self, 404, {"error": str(exc)})
                        raise
                    STATE.save_all()
                return _send(self, 200, version)
            if len(parts) == 3 and parts[:2] == ["api", "judgements"]:
                key = urllib.parse.unquote(parts[2])
                body = _read_json(self)
                with STATE_LOCK:
                    preferred = body.get("preferred")
                    if preferred:
                        # Only one preferred output per version.
                        for asset in STATE.assets.values():
                            for ver in asset["versions"]:
                                if any(o["key"] == key for o in ver["outputs"]):
                                    for other in ver["outputs"]:
                                        if other["key"] != key and \
                                                other["key"] in STATE.judgements:
                                            STATE.judgements[other["key"]]["preferred"] = False
                    record = save_judgement(
                        STATE.judgements, key, body.get("human_review", ""),
                        checklist=body.get("checklist"),
                        preferred=preferred if isinstance(preferred, bool) else None)
                    STATE.save_all()
                return _send(self, 200, {"key": key, **record})
            return _send(self, 404, {"error": "not found"})
        except StoreError as exc:
            return _send(self, 400, {"error": str(exc)})


def main(argv: list[str] | None = None) -> int:
    port = 8321
    args = list(argv if argv is not None else sys.argv[1:])
    if "--port" in args:
        idx = args.index("--port")
        try:
            port = int(args[idx + 1])
        except (IndexError, ValueError):
            print("error: --port needs an integer", file=sys.stderr)
            return 2
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"asset-tool: serving on http://127.0.0.1:{port}/ "
          f"({len(STATE.assets)} assets)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
