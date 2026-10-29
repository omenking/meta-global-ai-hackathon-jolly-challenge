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

import base64
import binascii
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

from asset_store import (SESSION_CONTEXT_MAX, UPLOAD_EXTENSIONS,
                         UPLOAD_MAX_BYTES, StoreError, add_turn, add_version,
                         build_prompt_draft, create_asset, create_session,
                         find_session_output, get_session, get_version,
                         load_judgements, load_manifest, load_sessions,
                         lottery_keys, mark_failed, mark_turn_failed,
                         normalize_run_count, publish_slug, record_output,
                         record_turn_outputs, save_judgement, save_judgements,
                         save_manifest, save_sessions, session_context_refs,
                         split_cost_per_output, update_asset, update_version,
                         validate_references, validate_run_not_noop,
                         validate_upload)
import pm_store
from pm_store import StoreError as PMStoreError
import game_sessions
from game_sessions import SessionError
import game_levels
from game_levels import LevelError

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


PM_EXPORT_DIR = ROOT / "plans" / "simple-game-engine" / "features"


class State:
    def __init__(self) -> None:
        self.assets, self.header = load_manifest()
        self.judgements, self.jheader = load_judgements()
        self.sessions, self.sheader = load_sessions()
        self.pm, self.pm_header = pm_store.load_pm()
        # Persist the migrated versions shape on first tool run.
        save_manifest(self.assets, self.header)
        save_sessions(self.sessions, self.sheader)
        pm_store.save_pm(self.pm, self.pm_header)

    def save_all(self) -> None:
        save_manifest(self.assets, self.header)
        save_judgements(self.judgements, self.jheader)
        save_sessions(self.sessions, self.sheader)

    def save_pm(self) -> None:
        pm_store.save_pm(self.pm, self.pm_header)


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


def _session_view(sid: str) -> dict:
    session = STATE.sessions[sid]
    turns = []
    for turn in session["turns"]:
        outputs = []
        for output in turn["outputs"]:
            record = dict(output)
            judge = STATE.judgements.get(output["key"], {})
            record["human_review"] = judge.get("human_review", "")
            record["checklist"] = judge.get("checklist") or {}
            record["preferred"] = bool(judge.get("preferred"))
            outputs.append(record)
        view = dict(turn)
        view["outputs"] = outputs
        turns.append(view)
    return {"id": sid, "asset_name": session["asset_name"],
            "title": session.get("title", ""),
            "created": session.get("created", ""), "turns": turns}


def _pm_feature_view(feature: dict) -> dict:
    view = dict(feature)
    view["progress"] = pm_store.feature_progress(feature)
    view["unblocks"] = pm_store.derived_unblocks(STATE.pm, feature["id"])
    return view


def _pm_not_found(fid: str):
    return {"error": f"feature {fid!r} not found"}


def _save_pm_evidence(fid: str, filename: object, data: bytes) -> dict:
    cleaned = validate_upload(filename, len(data))
    folder = pm_store.EVIDENCE_ROOT / "features" / fid
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{cleaned}"
    target = folder / name
    suffix = 2
    while target.exists():
        name = f"{stamp}-{suffix}-{cleaned}"
        target = folder / name
        suffix += 1
    target.write_bytes(data)
    rel = f"screenshots/features/{fid}/{name}"
    return {"path": rel, "url": f"/api/pm/evidence/features/{fid}/{name}",
            "size": len(data)}


def _new_session_id() -> str:
    base = "s" + time.strftime("%Y%m%d-%H%M%S")
    sid = base
    suffix = 2
    while sid in STATE.sessions:
        sid = f"{base}-{suffix}"
        suffix += 1
    return sid


def _turn_count(num: object) -> int:
    """Turn lottery size N (1-10). Missing/blank means 1 for turns."""
    if num is None:
        return 1
    if isinstance(num, str) and not num.strip():
        return 1
    return normalize_run_count(num)


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


def _run_turn(session_id: str, prompt: object, references: object,
              num: object = None) -> dict:
    """Run scripts/gen-image once for a session turn; caller holds no locks.

    No provider session exists (see asset_store spike note), so continuity is
    emulated: references of None auto-carries session context (preferred
    first, newest first, capped at 10) and is saved back onto the turn so the
    record shows what actually ran. An explicit list (possibly empty) wins.
    Turn lottery N defaults to 1 (unlike version runs, which default to 4).
    """
    global RUN_SEQ
    count = _turn_count(num)
    session = STATE.sessions.get(session_id)
    if session is None:
        raise StoreError(f"session {session_id!r} does not exist")
    text = (prompt or "").strip() if isinstance(prompt, str) else ""
    if not text:
        raise StoreError("turn prompt must not be empty")
    asset_name = session.get("asset_name", "")
    asset = STATE.assets.get(asset_name)
    if asset is None:
        raise StoreError(f"asset {asset_name!r} does not exist")
    if references is None:
        cleaned_refs = session_context_refs(session, STATE.judgements)
    else:
        cleaned_refs = validate_references(references)
    width = asset.get("width")
    height = asset.get("height")
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

    with STATE_LOCK:
        turn = add_turn(STATE.sessions, session_id, text, cleaned_refs, count)
        seq = turn["seq"]
        STATE.save_all()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = f"{asset_name}-{session_id}-t{seq}-{stamp}"
    keys = lottery_keys(base, count)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_base_abs = OUTPUTS_DIR / f"{base}.png"
    if count == 1:
        expected_abs = [OUTPUTS_DIR / f"{keys[0]}.png"]
    else:
        expected_abs = [OUTPUTS_DIR / f"{k}.png" for k in keys]

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(text)
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
            mark_turn_failed(STATE.sessions, session_id, seq)
            STATE.save_all()
        raise StoreError(f"generation timed out after {RUN_TIMEOUT_S}s")
    finally:
        Path(prompt_file).unlink(missing_ok=True)

    stdout, stderr = proc.stdout or "", proc.stderr or ""
    if proc.returncode != 0:
        with STATE_LOCK:
            mark_turn_failed(STATE.sessions, session_id, seq)
            STATE.save_all()
        raise StoreError(f"generation failed: {(stderr or stdout).strip()[-500:]}")

    missing = [str(p) for p in expected_abs if not p.is_file()]
    if missing:
        with STATE_LOCK:
            mark_turn_failed(STATE.sessions, session_id, seq)
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
                    raw_text = m.group(2)
                    if "x" in raw_text:
                        raw_width, raw_height = (int(v) for v in raw_text.split("x"))
                    break
            original_path = None
            if len(orig_texts) == len(keys):
                original_path = _relativize_output_path(orig_texts[idx])
            else:
                for ot in orig_texts:
                    if key in ot:
                        original_path = _relativize_output_path(ot)
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
        turn = record_turn_outputs(
            STATE.sessions, session_id, seq, outputs_info, total_usd,
            full_prompt_sent=text)
        STATE.save_all()
        RUN_SEQ += 1
        run_id = f"run-{RUN_SEQ}"
        stored_outputs = [dict(o) for o in turn["outputs"][-len(outputs_info):]]
        first = stored_outputs[0]
        record = {
            "id": run_id,
            "asset": asset_name,
            "session": session_id,
            "turn": seq,
            "version": None,
            "num": count,
            "keys": [o["key"] for o in stored_outputs],
            "outputs": stored_outputs,
            "total_estimated_usd": total_usd,
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


def _strip_png(name: str) -> str:
    return name[:-4] if name.endswith(".png") else name


def _publish_output(session_id: str, output_key: object,
                    asset_name: object) -> tuple[str, dict]:
    """Publish a session turn output to the official asset list.

    Same-name publish appends a new version (never overwrites); a missing
    target asset is created with the source asset's dimensions. The published
    version reuses the turn output's key/path so judgements carry over.
    Caller must hold STATE_LOCK.
    """
    session = get_session(STATE.sessions, session_id)
    key = (output_key or "").strip() if isinstance(output_key, str) else ""
    key = _strip_png(key)
    if not key:
        raise StoreError("output_key must not be empty")
    turn = None
    output = None
    for cand in session.get("turns") or []:
        for cand_out in cand.get("outputs") or []:
            if cand_out.get("key") == key:
                turn, output = cand, cand_out
                break
        if output is not None:
            break
    if turn is None or output is None:
        raise StoreError(f"output {key!r} not found in session {session_id!r}")
    if asset_name is None or (isinstance(asset_name, str) and not asset_name.strip()):
        target = session.get("asset_name", "")
    elif isinstance(asset_name, str):
        target = asset_name.strip()
    else:
        raise StoreError("asset_name must be a string")
    if not target:
        raise StoreError("publish needs an asset name")
    source = STATE.assets.get(session.get("asset_name", ""))
    if target not in STATE.assets:
        if source is None:
            raise StoreError(
                f"asset {session.get('asset_name')!r} does not exist")
        create_asset(STATE.assets, target, source.get("width"),
                     source.get("height"))
    asset = STATE.assets[target]
    if not isinstance(asset.get("width"), int) or not isinstance(asset.get("height"), int):
        # create_asset validated ints; a legacy record missing dims fails here.
        raise StoreError(f"asset {target!r} needs width and height before publishing")
    slug = publish_slug(session_id, turn["seq"])
    taken = {v["slug"] for v in asset["versions"]}
    suffix = 2
    unique = slug
    while unique in taken:
        unique = f"{slug}-{suffix}"
        suffix += 1
    slug = unique
    parent = asset["versions"][-1]["slug"] if asset["versions"] else None
    prompt = (turn.get("full_prompt_sent") or turn.get("prompt") or "").strip()
    if not prompt:
        raise StoreError("turn has no prompt to publish")
    version = add_version(
        STATE.assets, target, slug,
        f"Published from session {session_id} turn {turn['seq']} ({key})",
        prompt, parent=parent,
        references=list(turn.get("references") or []))
    record_output(
        STATE.assets, target, slug, output["key"], output["path"],
        output.get("estimated_usd"), original_path=output.get("original_path"),
        requested_width=output.get("requested_width"),
        requested_height=output.get("requested_height"),
        raw_width=output.get("raw_width"),
        raw_height=output.get("raw_height"))
    return target, version


def _save_upload(filename: object, data: bytes) -> dict:
    """Validate and store an upload under assets/outputs; return its record."""
    cleaned = validate_upload(filename, len(data))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"uploads-{stamp}-{cleaned}"
    target = OUTPUTS_DIR / name
    suffix = 2
    while target.exists():
        name = f"uploads-{stamp}-{suffix}-{cleaned}"
        target = OUTPUTS_DIR / name
        suffix += 1
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"file": name, "path": f"assets/outputs/{name}",
            "url": f"/outputs/{name}", "size": len(data)}


def _list_uploads() -> list:
    try:
        files = sorted(OUTPUTS_DIR.glob("uploads-*"))
    except OSError:
        return []
    records = []
    for path in files:
        if not path.is_file():
            continue
        if path.suffix.lower() not in UPLOAD_EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        records.append({"file": path.name, "path": f"assets/outputs/{path.name}",
                        "url": f"/outputs/{path.name}", "size": size})
    return records


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
                app_index = STATIC_DIR / "app" / "index.html"
                if app_index.is_file():
                    return self._serve_file(app_index)
                return self._serve_file(STATIC_DIR / "home.html")
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
            if parts == ["api", "sessions"]:
                query = urllib.parse.parse_qs(parsed.query or "")
                wanted = (query.get("asset") or [None])[0]
                with STATE_LOCK:
                    sids = sorted(STATE.sessions)
                    if wanted:
                        sids = [s for s in sids
                                if STATE.sessions[s]["asset_name"] == wanted]
                    payload = [_session_view(s) for s in sids]
                return _send(self, 200, {"sessions": payload})
            if len(parts) == 3 and parts[:2] == ["api", "sessions"]:
                sid = urllib.parse.unquote(parts[2])
                with STATE_LOCK:
                    if sid not in STATE.sessions:
                        return _send(self, 404, {"error": f"session {sid!r} not found"})
                    return _send(self, 200, _session_view(sid))
            if parts == ["api", "uploads"]:
                return _send(self, 200, {"uploads": _list_uploads()})
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
            if parts == ["api", "game", "levels"]:
                return _send(self, 200,
                             {"levels": game_levels.list_levels(ROOT / "levels")})
            if len(parts) == 4 and parts[:3] == ["api", "game", "levels"]:
                return _send(self, 200, game_levels.load_level(
                    ROOT / "levels", urllib.parse.unquote(parts[3])))
            if len(parts) == 4 and parts[:3] == ["api", "game", "sessions"]:
                records = game_sessions.read_session(
                    pm_store.SESSIONS_ROOT, urllib.parse.unquote(parts[3]))
                return _send(self, 200, {"records": records})
            if parts == ["api", "pm", "features"]:
                with STATE_LOCK:
                    payload = [_pm_feature_view(f) for f in STATE.pm["features"]]
                return _send(self, 200, {"features": payload})
            if len(parts) == 4 and parts[:3] == ["api", "pm", "features"]:
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    return _send(self, 200, _pm_feature_view(feature))
            if len(parts) == 5 and parts[:3] == ["api", "pm", "features"] and parts[4] == "rollup":
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    return _send(self, 200, pm_store.review_rollup(STATE.pm, fid))
            if len(parts) >= 4 and parts[:3] == ["api", "pm", "evidence"]:
                rel = "/".join(urllib.parse.unquote(p) for p in parts[3:])
                target = (pm_store.EVIDENCE_ROOT / rel).resolve()
                try:
                    target.relative_to(pm_store.EVIDENCE_ROOT.resolve())
                except ValueError:
                    return _send(self, 404, {"error": "not found"})
                return self._serve_file(target)
            if parts[:1] == ["api"]:
                return _send(self, 404, {"error": "not found"})
            if parts and parts[0] == "pm":
                app_index = STATIC_DIR / "app" / "index.html"
                if app_index.is_file():
                    return self._serve_file(app_index)
                return self._serve_file(STATIC_DIR / "home.html")
            return self._serve_file(STATIC_DIR / "index.html")
        except (StoreError, PMStoreError, SessionError, LevelError) as exc:
            return _send(self, 400, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            body = _read_json(self)
            if parts == ["api", "game", "sessions"]:
                path = game_sessions.write_session(
                    pm_store.SESSIONS_ROOT, body.get("id", ""),
                    body.get("content", ""))
                return _send(self, 201, {
                    "id": body.get("id"),
                    "path": f"sessions/{path.name}"})
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
            if parts == ["api", "sessions"]:
                asset_name = body.get("asset", "")
                if not isinstance(asset_name, str) or not asset_name.strip():
                    raise StoreError("session needs an asset name")
                with STATE_LOCK:
                    if asset_name.strip() not in STATE.assets:
                        return _send(self, 404,
                                     {"error": f"asset {asset_name.strip()!r} not found"})
                    sid = _new_session_id()
                    session = create_session(
                        STATE.sessions, sid, asset_name.strip(),
                        title=body.get("title", "") if isinstance(
                            body.get("title", ""), str) else "",
                        created=time.strftime("%Y-%m-%dT%H:%M:%S"))
                    STATE.save_all()
                    return _send(self, 201, _session_view(session["id"]))
            if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] == "turns":
                sid = urllib.parse.unquote(parts[2])
                with STATE_LOCK:
                    if sid not in STATE.sessions:
                        return _send(self, 404, {"error": f"session {sid!r} not found"})
                if not RUN_LOCK.acquire(blocking=False):
                    return _send(self, 409,
                                 {"error": "a generation is already running"})
                try:
                    record = _run_turn(sid, body.get("prompt", ""),
                                       body.get("references", None),
                                       body.get("num", None))
                finally:
                    RUN_LOCK.release()
                return _send(self, 201, record)
            if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] == "publish":
                sid = urllib.parse.unquote(parts[2])
                with STATE_LOCK:
                    if sid not in STATE.sessions:
                        return _send(self, 404, {"error": f"session {sid!r} not found"})
                    target, version = _publish_output(
                        sid, body.get("output_key", ""),
                        body.get("asset_name", None))
                    STATE.save_all()
                    return _send(self, 201, {"asset": _asset_view(target),
                                             "version": version})
            if parts == ["api", "uploads"]:
                filename = body.get("filename", "")
                data_b64 = body.get("data_b64", "")
                if not isinstance(data_b64, str) or not data_b64.strip():
                    raise StoreError("upload needs base64 data")
                try:
                    data = base64.b64decode(data_b64, validate=True)
                except (binascii.Error, ValueError):
                    raise StoreError("upload data is not valid base64")
                record = _save_upload(filename, data)
                return _send(self, 201, record)
            if parts == ["api", "pm", "seed"]:
                with STATE_LOCK:
                    result = pm_store.seed_pm(STATE.pm)
                    STATE.save_pm()
                    payload = [_pm_feature_view(f) for f in STATE.pm["features"]]
                return _send(self, 200, {**result, "features": payload})
            if parts == ["api", "pm", "export"]:
                with STATE_LOCK:
                    written = pm_store.export_all(STATE.pm, PM_EXPORT_DIR)
                return _send(self, 200,
                             {"exported": [str(p.relative_to(ROOT)) for p in written]})
            if parts == ["api", "pm", "features"]:
                with STATE_LOCK:
                    feature = pm_store.create_feature(
                        STATE.pm, body.get("id"), body.get("title", ""),
                        summary=body.get("summary", ""),
                        priority=body.get("priority", "medium"),
                        status=body.get("status", "proposed"),
                        requires=body.get("requires"),
                        spec=body.get("spec"),
                        test_level=body.get("test_level"),
                        branch=body.get("branch"),
                        worktree=body.get("worktree"))
                    STATE.save_pm()
                    return _send(self, 201, _pm_feature_view(feature))
            if len(parts) == 5 and parts[:3] == ["api", "pm", "features"] and parts[4] == "tasks":
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    task = pm_store.create_task(
                        STATE.pm, fid, body.get("id"), body.get("title", ""),
                        description=body.get("description", ""),
                        acceptance=body.get("acceptance", ""),
                        status=body.get("status", "proposed"),
                        priority=body.get("priority", "medium"),
                        requires=body.get("requires"),
                        kind=body.get("kind", "work"),
                        order=body.get("order"))
                    STATE.save_pm()
                    return _send(self, 201, task)
            if len(parts) == 7 and parts[:3] == ["api", "pm", "features"] and parts[4] == "tasks" and parts[6] in ("move", "claim"):
                fid = urllib.parse.unquote(parts[3])
                tid = urllib.parse.unquote(parts[5])
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    try:
                        pm_store.get_task(feature, tid)
                    except PMStoreError as exc:
                        return _send(self, 404, {"error": str(exc)})
                    if parts[6] == "claim":
                        task = pm_store.claim_task(STATE.pm, fid, tid)
                        if body.get("body"):
                            pm_store.add_task_comment(
                                STATE.pm, fid, tid,
                                body.get("author", "agent"), body["body"],
                                attachments=body.get("attachments"),
                                session_refs=body.get("session_refs"))
                    else:
                        task = pm_store.move_task(
                            STATE.pm, fid, tid, body.get("status", ""),
                            order=body.get("order"))
                    STATE.save_pm()
                    return _send(self, 200, task)
            if len(parts) == 5 and parts[:3] == ["api", "pm", "features"] and parts[4] == "comments":
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    comment = pm_store.add_feature_comment(
                        STATE.pm, fid, body.get("author", "human"),
                        body.get("body", ""), attachments=body.get("attachments"),
                        session_refs=body.get("session_refs"))
                    STATE.save_pm()
                    return _send(self, 201, comment)
            if len(parts) == 7 and parts[:3] == ["api", "pm", "features"] and parts[4] == "tasks" and parts[6] == "comments":
                fid = urllib.parse.unquote(parts[3])
                tid = urllib.parse.unquote(parts[5])
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    try:
                        pm_store.get_task(feature, tid)
                    except PMStoreError as exc:
                        return _send(self, 404, {"error": str(exc)})
                    comment = pm_store.add_task_comment(
                        STATE.pm, fid, tid, body.get("author", "human"),
                        body.get("body", ""), attachments=body.get("attachments"),
                        session_refs=body.get("session_refs"))
                    STATE.save_pm()
                    return _send(self, 201, comment)
            if len(parts) == 5 and parts[:3] == ["api", "pm", "features"] and parts[4] == "evidence":
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                data_b64 = body.get("data_b64", "")
                if not isinstance(data_b64, str) or not data_b64.strip():
                    raise PMStoreError("evidence upload needs base64 data")
                try:
                    raw = base64.b64decode(data_b64, validate=True)
                except (binascii.Error, ValueError):
                    raise PMStoreError("evidence data is not valid base64")
                record = _save_pm_evidence(fid, body.get("filename", ""), raw)
                return _send(self, 201, record)
            if len(parts) == 5 and parts[:3] == ["api", "pm", "features"] and parts[4] == "review":
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    feature = pm_store.set_review(
                        STATE.pm, fid, body.get("decision", ""),
                        body.get("by", "human"),
                        comment_body=body.get("comment") or body.get("body"))
                    if body.get("comment") or body.get("body"):
                        pm_store.add_feature_comment(
                            STATE.pm, fid, body.get("by", "human"),
                            body.get("comment") or body.get("body"),
                            attachments=body.get("attachments"),
                            session_refs=body.get("session_refs"))
                    STATE.save_pm()
                    return _send(self, 200, _pm_feature_view(feature))
            if len(parts) == 5 and parts[:3] == ["api", "pm", "features"] and parts[4] == "sessions":
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    ref = pm_store.link_session(STATE.pm, fid, body,
                                                tid=body.get("task"))
                    STATE.save_pm()
                    return _send(self, 201, ref)
            if len(parts) == 5 and parts[:3] == ["api", "pm", "features"] and parts[4] == "merge":
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    feature = pm_store.record_merge(
                        STATE.pm, fid, body.get("commit", ""))
                    STATE.save_pm()
                    return _send(self, 200, _pm_feature_view(feature))
            return _send(self, 404, {"error": "not found"})
        except (StoreError, PMStoreError, SessionError, LevelError) as exc:
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
            if len(parts) == 4 and parts[:3] == ["api", "pm", "features"]:
                fid = urllib.parse.unquote(parts[3])
                body = _read_json(self)
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    feature = pm_store.update_feature(STATE.pm, fid, body)
                    STATE.save_pm()
                    return _send(self, 200, _pm_feature_view(feature))
            if len(parts) == 6 and parts[:3] == ["api", "pm", "features"] and parts[4] == "tasks":
                fid = urllib.parse.unquote(parts[3])
                tid = urllib.parse.unquote(parts[5])
                body = _read_json(self)
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    try:
                        pm_store.get_task(feature, tid)
                    except PMStoreError as exc:
                        return _send(self, 404, {"error": str(exc)})
                    task = pm_store.update_task(STATE.pm, fid, tid, body)
                    STATE.save_pm()
                    return _send(self, 200, task)
            if len(parts) == 6 and parts[:3] == ["api", "pm", "features"] and parts[4] == "comments":
                fid = urllib.parse.unquote(parts[3])
                cid = urllib.parse.unquote(parts[5])
                body = _read_json(self)
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    comment = pm_store.update_comment(
                        feature["comments"], cid, body.get("body", ""),
                        attachments=body.get("attachments"),
                        session_refs=body.get("session_refs"))
                    STATE.save_pm()
                    return _send(self, 200, comment)
            if len(parts) == 8 and parts[:3] == ["api", "pm", "features"] and parts[4] == "tasks" and parts[6] == "comments":
                fid = urllib.parse.unquote(parts[3])
                tid = urllib.parse.unquote(parts[5])
                cid = urllib.parse.unquote(parts[7])
                body = _read_json(self)
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    try:
                        task = pm_store.get_task(feature, tid)
                    except PMStoreError as exc:
                        return _send(self, 404, {"error": str(exc)})
                    comment = pm_store.update_comment(
                        task["comments"], cid, body.get("body", ""),
                        attachments=body.get("attachments"),
                        session_refs=body.get("session_refs"))
                    STATE.save_pm()
                    return _send(self, 200, comment)
            return _send(self, 404, {"error": "not found"})
        except (StoreError, PMStoreError, SessionError, LevelError) as exc:
            return _send(self, 400, {"error": str(exc)})

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            if len(parts) == 4 and parts[:3] == ["api", "pm", "features"]:
                fid = urllib.parse.unquote(parts[3])
                with STATE_LOCK:
                    if pm_store.find_feature(STATE.pm, fid) is None:
                        return _send(self, 404, _pm_not_found(fid))
                    feature = pm_store.archive_feature(STATE.pm, fid)
                    STATE.save_pm()
                    return _send(self, 200, _pm_feature_view(feature))
            if len(parts) == 6 and parts[:3] == ["api", "pm", "features"] and parts[4] == "tasks":
                fid = urllib.parse.unquote(parts[3])
                tid = urllib.parse.unquote(parts[5])
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    try:
                        pm_store.get_task(feature, tid)
                    except PMStoreError as exc:
                        return _send(self, 404, {"error": str(exc)})
                    task = pm_store.archive_task(STATE.pm, fid, tid)
                    STATE.save_pm()
                    return _send(self, 200, task)
            if len(parts) == 6 and parts[:3] == ["api", "pm", "features"] and parts[4] == "comments":
                fid = urllib.parse.unquote(parts[3])
                cid = urllib.parse.unquote(parts[5])
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    pm_store.delete_comment(feature["comments"], cid)
                    STATE.save_pm()
                    return _send(self, 200, {"deleted": cid})
            if len(parts) == 8 and parts[:3] == ["api", "pm", "features"] and parts[4] == "tasks" and parts[6] == "comments":
                fid = urllib.parse.unquote(parts[3])
                tid = urllib.parse.unquote(parts[5])
                cid = urllib.parse.unquote(parts[7])
                with STATE_LOCK:
                    feature = pm_store.find_feature(STATE.pm, fid)
                    if feature is None:
                        return _send(self, 404, _pm_not_found(fid))
                    try:
                        task = pm_store.get_task(feature, tid)
                    except PMStoreError as exc:
                        return _send(self, 404, {"error": str(exc)})
                    pm_store.delete_comment(task["comments"], cid)
                    STATE.save_pm()
                    return _send(self, 200, {"deleted": cid})
            return _send(self, 404, {"error": "not found"})
        except (StoreError, PMStoreError, SessionError, LevelError) as exc:
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
