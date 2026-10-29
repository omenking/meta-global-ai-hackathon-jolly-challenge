"""Server-side writer for recorded game sessions (JSONL).

One file per session under sessions/: a header line
{type:"session", id, created_at, created_by, label, level,
 level_source:{file, hash}, feature, task, branch, commit}, one line
per step {type:"step", n, t_ms, input}, a closing line
{type:"end", result, steps, orbs_left, time_left}, then optional
{type:"annotation", ...} lines. The game posts the full file content
on start, on every step, and on end, so a session file exists from
the first playable moment and no play is ever unrecorded.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class SessionError(ValueError):
    """Raised for invalid session ids or malformed JSONL."""


def validate_session_id(value: object) -> str:
    if not isinstance(value, str) or not SLUG_RE.match(value):
        raise SessionError(f"invalid session id {value!r}")
    return value


def parse_session(text: str) -> list[dict]:
    if not isinstance(text, str) or not text.strip():
        raise SessionError("session content must be non-empty JSONL text")
    records = []
    for i, line in enumerate(text.strip().splitlines(), 1):
        try:
            rec = json.loads(line)
        except ValueError:
            raise SessionError(f"session line {i} is not valid JSON")
        if not isinstance(rec, dict) or "type" not in rec:
            raise SessionError(f"session line {i} needs a 'type'")
        records.append(rec)
    header = records[0]
    if header.get("type") != "session":
        raise SessionError("first session line must be the session header")
    validate_session_id(header.get("id"))
    for rec in records[1:]:
        if rec["type"] == "step":
            if not isinstance(rec.get("n"), int) or \
                    not isinstance(rec.get("t_ms"), (int, float)):
                raise SessionError("step lines need integer n and numeric t_ms")
        elif rec["type"] not in ("end", "annotation"):
            raise SessionError(f"unknown session line type {rec['type']!r}")
    return records


def session_path(root: Path, session_id: str) -> Path:
    validate_session_id(session_id)
    path = (Path(root) / f"{session_id}.jsonl").resolve()
    if path.parent != Path(root).resolve():
        raise SessionError("session path escapes the sessions root")
    return path


def write_session(root: Path, session_id: str, text: str) -> Path:
    records = parse_session(text)
    if records[0].get("id") != session_id:
        raise SessionError("session header id does not match the target id")
    path = session_path(root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                               prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def read_session(root: Path, session_id: str) -> list[dict]:
    return read_session_any(root, session_id)

ENGINE_VERSION = "game-core-1"
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
import datetime as _dt


def normalize_labels(values) -> list:
    if values is None:
        return []
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",")]
    if not isinstance(values, (list, tuple)):
        raise SessionError("labels must be a list or comma-separated string")
    out = []
    for v in values:
        if not isinstance(v, str):
            raise SessionError("labels must be strings")
        lab = v.strip().lower()
        if not lab:
            continue
        if not LABEL_RE.match(lab):
            raise SessionError(f"invalid label {v!r} (free-form lowercase)")
        if lab not in out:
            out.append(lab)
    return out


def find_session_path(root: Path, session_id: str) -> Path:
    validate_session_id(session_id)
    root = Path(root)
    flat = root / f"{session_id}.jsonl"
    if flat.is_file():
        return flat
    for cand in sorted(root.rglob(f"{session_id}.jsonl")) if root.is_dir() else []:
        return cand
    raise SessionError(f"session {session_id!r} does not exist")


def labels_of(records: list) -> list:
    out = []
    for rec in records:
        if rec.get("type") == "annotation":
            for lab in normalize_labels(rec.get("labels") or []):
                if lab not in out:
                    out.append(lab)
    header = records[0] if records else {}
    if header.get("label"):
        lab = str(header["label"]).strip().lower()
        if lab and lab not in out:
            out.insert(0, lab)
    return out


def summarize(records: list, path: str = "") -> dict:
    header = records[0]
    end = next((r for r in reversed(records) if r.get("type") == "end"), {})
    steps = [r for r in records if r.get("type") == "step"]
    return {
        "id": header.get("id"), "created_at": header.get("created_at"),
        "created_by": header.get("created_by"), "label": header.get("label", ""),
        "labels": labels_of(records), "level": header.get("level"),
        "feature": header.get("feature"), "task": header.get("task"),
        "result": end.get("result"), "steps": len(steps),
        "forked_by": header.get("forked_by"),
        "forked_from": header.get("forked_from"),
        "fork_step": header.get("fork_step"), "path": path,
    }


def _iter_session_files(root: Path):
    root = Path(root)
    if not root.is_dir():
        return
    seen = set()
    for path in sorted(root.rglob("*.jsonl")):
        sid = path.stem
        if sid in seen or not SLUG_RE.match(sid):
            continue
        seen.add(sid)
        yield path


def list_sessions(root: Path, level=None, creator=None, feature=None,
                  date=None, result=None, label=None, query=None) -> list:
    out = []
    for path in _iter_session_files(root):
        try:
            records = parse_session(path.read_text(encoding="utf-8"))
        except (SessionError, OSError):
            continue
        s = summarize(records)
        try:
            s["path"] = str(path.relative_to(Path(root)))
        except ValueError:
            s["path"] = path.name
        if level and s["level"] != level:
            continue
        if creator and s["created_by"] != creator:
            continue
        if feature and s["feature"] != feature:
            continue
        if date and not str(s["created_at"] or "").startswith(date):
            continue
        if result and s["result"] != result:
            continue
        if label and label.lower() not in s["labels"]:
            continue
        if query and query.lower() not in str(s["id"]).lower():
            continue
        out.append(s)
    out.sort(key=lambda s: str(s["created_at"] or ""), reverse=True)
    return out


def append_annotation(root: Path, session_id: str, author: str,
                      body: str = "", labels=None, at: str = None) -> dict:
    if author not in ("human", "agent"):
        raise SessionError("annotation author must be 'human' or 'agent'")
    if not isinstance(body, str):
        raise SessionError("annotation body must be text")
    labs = normalize_labels(labels)
    if not body.strip() and not labs:
        raise SessionError("annotation needs a note or at least one label")
    path = find_session_path(root, session_id)
    parse_session(path.read_text(encoding="utf-8"))
    rec = {"type": "annotation", "author": author,
           "at": at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
           "body": body.strip(), "labels": labs}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def step_index_at_time(records: list, t_seconds) -> int:
    """Deep links are time-based: index = steps with t_ms <= t*1000."""
    try:
        target = float(t_seconds) * 1000
    except (TypeError, ValueError):
        raise SessionError("t must be seconds (a number)")
    idx = 0
    for i, rec in enumerate([r for r in records if r.get("type") == "step"], 1):
        if rec["t_ms"] <= target:
            idx = i
        else:
            break
    return idx


def fork_records(records: list, fork_step: int, new_id: str,
                 forked_by: str, created_at: str = None) -> list:
    validate_session_id(new_id)
    if forked_by not in ("human", "agent"):
        raise SessionError("forked_by must be 'human' or 'agent'")
    steps = [r for r in records if r.get("type") == "step"]
    if not isinstance(fork_step, int) or fork_step < 0 or fork_step > len(steps):
        raise SessionError(f"fork_step must be between 0 and {len(steps)}")
    header = dict(records[0])
    orig_id, orig_creator = header.get("id"), header.get("created_by")
    header.update({"id": new_id,
                   "created_at": created_at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
                   "created_by": orig_creator, "forked_by": forked_by,
                   "forked_from": orig_id, "fork_step": fork_step})
    return [header] + [dict(r) for r in steps[:fork_step]]


def write_fork(root: Path, session_id: str, fork_step: int, new_id: str,
               forked_by: str, created_at: str = None) -> list:
    records = read_session_any(root, session_id)
    forked = fork_records(records, fork_step, new_id, forked_by, created_at)
    text = "".join(json.dumps(r) + "\n" for r in forked)
    write_session(root, new_id, text)
    return forked


def read_session_any(root: Path, session_id: str) -> list:
    path = find_session_path(root, session_id)
    return parse_session(path.read_text(encoding="utf-8"))


def version_warnings(header: dict, level_hash=None, engine_version=None,
                     commit=None) -> list:
    warnings = []
    recorded_hash = (header.get("level_source") or {}).get("hash")
    if level_hash and recorded_hash and level_hash != recorded_hash:
        warnings.append(
            f"level mismatch: recorded level hash {recorded_hash} "
            f"!= current {level_hash}; replay may diverge")
    recorded_engine = header.get("engine_version")
    if recorded_engine and engine_version and recorded_engine != engine_version:
        warnings.append(
            f"engine mismatch: recorded {recorded_engine} "
            f"!= current {engine_version}; replay may diverge")
    if not recorded_engine:
        warnings.append("no engine version recorded; replay may diverge")
    recorded_commit = header.get("commit")
    if commit and recorded_commit and commit != recorded_commit:
        warnings.append(
            f"commit mismatch: recorded {recorded_commit} != current {commit}")
    return warnings
