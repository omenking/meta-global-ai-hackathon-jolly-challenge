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
    path = session_path(root, session_id)
    if not path.is_file():
        raise SessionError(f"session {session_id!r} does not exist")
    return parse_session(path.read_text(encoding="utf-8"))
