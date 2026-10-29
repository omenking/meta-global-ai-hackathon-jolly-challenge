"""Backend-owned storage for the project-manager tool.

Store format: one YAML file (plans/simple-game-engine/pm.yml) owned
solely by tools/server.py. The server is the only writer; worktree
sessions go through its HTTP API, so concurrent file writes never
race. Decision: YAML is kept (human-diffable, mirrors asset_store.py).
SQLite (stdlib sqlite3, path plans/simple-game-engine/pm.db) is the
documented fallback behind these same function signatures: switch
only if load testing shows lost updates despite the single-writer
server + STATE_LOCK + atomic replace. That switch changes only the
_load/_save internals; API and UI stay unchanged.

All writes are atomic (temp file + os.replace) and preserve the
leading comment header, mirroring asset_store.py. Rich spec text
maps 1:1 onto plans/simple-game-engine/template.md sections.
"""
from __future__ import annotations

import os
import re
import tempfile
import time
from pathlib import Path

import yaml

PM_PATH = Path(__file__).resolve().parent.parent / "plans" / "simple-game-engine" / "pm.yml"
EVIDENCE_ROOT = Path(__file__).resolve().parent.parent / "screenshots"
SESSIONS_ROOT = Path(__file__).resolve().parent.parent / "sessions"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
STATUSES = ("proposed", "approved", "in_progress", "in_review",
            "completed", "blocked", "abandoned")
# Tasks are agent-managed: when the agent says a task is done it is done
# (the human inspects task-level code directly), so tasks have no
# in_review stage. in_review remains a feature-only status.
TASK_STATUSES = tuple(s for s in STATUSES if s != "in_review")


def _task_status(value: object) -> str:
    status = _check_status(value)
    return "completed" if status == "in_review" else status
PRIORITIES = ("low", "medium", "high", "urgent")
AUTHORS = ("human", "agent")
REVIEW_DECISIONS = ("pending", "changes_requested", "approved_for_merge")
TASK_KINDS = ("work", "review-fixes")

SPEC_KEYS = (
    "goal", "user_story", "use_case", "behavior", "edge_cases",
    "ui_feedback", "assets_needed", "acceptance", "out_of_scope",
    "open_questions", "testing",
)
SPEC_TITLES = {
    "goal": "Goal",
    "user_story": "User Story",
    "use_case": "High-Level Use Case",
    "behavior": "Player-Facing Behavior",
    "edge_cases": "Edge Cases & Rules",
    "ui_feedback": "UI / Feedback",
    "assets_needed": "Assets & Level Data Needed",
    "acceptance": "Acceptance Criteria",
    "out_of_scope": "Out of Scope",
    "open_questions": "Open Questions",
    "testing": "Testing",
}

# Free-form annotation labels (NQ28): any lowercase string is allowed;
# these are only suggested starters shown in the game UI.
SUGGESTED_LABELS = ("failed", "bug")


class StoreError(ValueError):
    """Raised for invalid ids, enums, or missing parents."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower())
    return s.strip("-")


def _check_slug(kind: str, value: object) -> str:
    if not isinstance(value, str) or not SLUG_RE.match(value):
        raise StoreError(
            f"invalid {kind} id {value!r}: use lowercase letters, digits, '-' or '_'")
    return value


def _check_status(value: object) -> str:
    if value not in STATUSES:
        raise StoreError(f"invalid status {value!r}: expected one of {list(STATUSES)}")
    return value  # type: ignore[return-value]


def _check_priority(value: object) -> str:
    if value not in PRIORITIES:
        raise StoreError(f"invalid priority {value!r}: expected one of {list(PRIORITIES)}")
    return value  # type: ignore[return-value]


def _check_author(value: object) -> str:
    if value not in AUTHORS:
        raise StoreError(f"invalid author {value!r}: expected 'human' or 'agent'")
    return value  # type: ignore[return-value]


def validate_attachment_path(value: object, root: Path = EVIDENCE_ROOT) -> str:
    """Return a repo-relative evidence path, rejecting escapes.

    Attachments live under screenshots/ (the evidence root). Accepts
    repo-relative paths like screenshots/features/<fid>/shot.png or
    features/<fid>/shot.png. Absolute paths and .. escapes raise.
    """
    if not isinstance(value, str) or not value.strip():
        raise StoreError("attachment path must be a non-empty string")
    text = value.strip().replace("\\", "/")
    if text.startswith("/") or ":" in text.split("/")[0]:
        raise StoreError(f"attachment path escapes the evidence root: {value!r}")
    rel = text
    if rel.startswith("screenshots/"):
        rel = rel[len("screenshots/"):]
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts) or not parts:
        raise StoreError(f"attachment path escapes the evidence root: {value!r}")
    resolved = (root / "/".join(parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise StoreError(f"attachment path escapes the evidence root: {value!r}")
    return "screenshots/" + "/".join(parts)


def _norm_str_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StoreError(f"{field} must be a list")
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise StoreError(f"{field} entries must be non-empty strings")
        out.append(item.strip())
    return out


def _norm_attachments(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StoreError("attachments must be a list of paths")
    return [validate_attachment_path(v) for v in value]


def _norm_session_refs(value: object) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StoreError("session_refs must be a list")
    out = []
    for entry in value:
        if not isinstance(entry, dict):
            raise StoreError("each session ref must be a mapping")
        sid = entry.get("id")
        if not isinstance(sid, str) or not sid.strip():
            raise StoreError("session ref needs a non-empty id")
        out.append(_normalize_session_ref(entry))
    return out


def _normalize_session_ref(entry: dict) -> dict:
    created_by = entry.get("created_by") or "human"
    _check_author(created_by)
    return {
        "id": str(entry.get("id")).strip(),
        "path": entry.get("path") or "",
        "level": entry.get("level") or "",
        "created_by": created_by,
        "result": entry.get("result") or "",
        "label": entry.get("label") or "",
    }


def _normalize_comment(entry: object) -> dict:
    if not isinstance(entry, dict):
        raise StoreError("each comment must be a mapping")
    cid = entry.get("id")
    if not isinstance(cid, str) or not cid.strip():
        raise StoreError("each comment needs a non-empty id")
    author = _check_author(entry.get("author"))
    body = entry.get("body") or ""
    if not isinstance(body, str) or not body.strip():
        raise StoreError("comment body must not be empty")
    return {
        "id": cid.strip(),
        "author": author,
        "created": entry.get("created") or "",
        "body": body,
        "attachments": _norm_attachments(entry.get("attachments")),
        "session_refs": _norm_session_refs(entry.get("session_refs")),
    }


def _normalize_task(entry: object, feature_id: str) -> dict:
    if not isinstance(entry, dict):
        raise StoreError("each task must be a mapping")
    tid = _check_slug("task", entry.get("id"))
    title = entry.get("title") or ""
    if not isinstance(title, str) or not title.strip():
        raise StoreError(f"task {tid!r} title must not be empty")
    status = _task_status(entry.get("status") or "proposed")
    priority = _check_priority(entry.get("priority") or "medium")
    kind = entry.get("kind") or "work"
    if kind not in TASK_KINDS:
        raise StoreError(f"invalid task kind {kind!r}: expected one of {list(TASK_KINDS)}")
    try:
        order = int(entry.get("order", 0))
    except (TypeError, ValueError):
        raise StoreError(f"task {tid!r} order must be an integer")
    return {
        "id": tid,
        "feature_id": feature_id,
        "title": title.strip(),
        "description": entry.get("description") or "",
        "acceptance": entry.get("acceptance") or "",
        "status": status,
        "priority": priority,
        "requires": _norm_str_list(entry.get("requires"), "task requires"),
        "order": order,
        "kind": kind,
        "commit": entry.get("commit"),
        "archived": bool(entry.get("archived", False)),
        "created": entry.get("created") or "",
        "updated": entry.get("updated") or "",
        "comments": [_normalize_comment(c) for c in (entry.get("comments") or [])],
    }


def _normalize_review(raw: object) -> dict:
    if raw is None:
        return {"decision": "pending", "by": None, "at": None}
    if not isinstance(raw, dict):
        raise StoreError("review must be a mapping")
    decision = raw.get("decision") or "pending"
    if decision not in REVIEW_DECISIONS:
        raise StoreError(f"invalid review decision {decision!r}")
    return {"decision": decision, "by": raw.get("by"), "at": raw.get("at")}


def _normalize_feature(entry: object) -> dict:
    if not isinstance(entry, dict):
        raise StoreError("each feature must be a mapping")
    fid = _check_slug("feature", entry.get("id"))
    title = entry.get("title") or ""
    if not isinstance(title, str) or not title.strip():
        raise StoreError(f"feature {fid!r} title must not be empty")
    status = _check_status(entry.get("status") or "proposed")
    priority = _check_priority(entry.get("priority") or "medium")
    spec_raw = entry.get("spec") or {}
    if not isinstance(spec_raw, dict):
        raise StoreError(f"feature {fid!r} spec must be a mapping")
    spec = {k: (spec_raw.get(k) or "") for k in SPEC_KEYS}
    # Legacy flat section keys are folded into spec for resilience.
    for k in SPEC_KEYS:
        if k in entry and isinstance(entry.get(k), str):
            spec[k] = entry[k]  # type: ignore[assignment]
    tasks = [_normalize_task(t, fid) for t in (entry.get("tasks") or [])]
    seen: set[str] = set()
    for t in tasks:
        if t["id"] in seen:
            raise StoreError(f"duplicate task id {t['id']!r} in feature {fid!r}")
        seen.add(t["id"])
    sessions = [_normalize_session_ref(s) for s in (entry.get("sessions") or [])]
    merged = entry.get("merged")
    if merged is not None:
        if not isinstance(merged, dict):
            raise StoreError(f"feature {fid!r} merged must be a mapping or null")
        merged = {"commit": merged.get("commit"), "at": merged.get("at")}
    return {
        "id": fid,
        "title": title.strip(),
        "summary": entry.get("summary") or "",
        "status": status,
        "priority": priority,
        "requires": _norm_str_list(entry.get("requires"), "feature requires"),
        "spec": spec,
        "branch": entry.get("branch"),
        "worktree": entry.get("worktree"),
        "test_level": entry.get("test_level"),
        "review": _normalize_review(entry.get("review")),
        "merged": merged,
        "sessions": sessions,
        "archived": bool(entry.get("archived", False)),
        "created": entry.get("created") or "",
        "updated": entry.get("updated") or "",
        "comments": [_normalize_comment(c) for c in (entry.get("comments") or [])],
        "tasks": tasks,
    }


def _split_header(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    cut = 0
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            cut += len(line)
        else:
            break
    return text[:cut], text[cut:]


def _load_yaml(path: Path) -> tuple[dict, str]:
    if not path.is_file():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    header, body = _split_header(text)
    data = yaml.safe_load(body) or {}
    if not isinstance(data, dict):
        raise StoreError(f"{path} must contain a mapping at the top level")
    return data, header


def _save_yaml(path: Path, data: dict, header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True) if data else ""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(header)
            if header and not header.endswith("\n"):
                fh.write("\n")
            fh.write(body)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


DEFAULT_HEADER = (
    "# Project manager store — owned by tools/server.py; never hand-edit.\n"
    "# Board state lives here on main and is written only through the API.\n"
    "# YAML chosen per plan decision 1; SQLite is the fallback behind pm_store.\n"
)


def load_pm(path: Path = PM_PATH) -> tuple[dict, str]:
    """Return (data, header); data is {\"features\": [feature, ...]}."""
    raw, header = _load_yaml(path)
    raw_features = raw.get("features") or []
    if isinstance(raw_features, dict):
        raw_features = list(raw_features.values())
    if not isinstance(raw_features, list):
        raise StoreError("pm 'features' must be a list")
    features = [_normalize_feature(f) for f in raw_features]
    ids = [f["id"] for f in features]
    if len(ids) != len(set(ids)):
        raise StoreError("duplicate feature ids in pm store")
    known = set(ids)
    for f in features:
        for req in f["requires"]:
            if req not in known:
                raise StoreError(
                    f"feature {f['id']!r} requires unknown feature {req!r}")
    return {"features": features}, header


def save_pm(data: dict, header: str, path: Path = PM_PATH) -> None:
    _save_yaml(path, data, header or DEFAULT_HEADER)


def get_feature(data: dict, fid: str) -> dict:
    for f in data.get("features", []):
        if f["id"] == fid:
            return f
    raise StoreError(f"feature {fid!r} does not exist")


def find_feature(data: dict, fid: str) -> dict | None:
    for f in data.get("features", []):
        if f["id"] == fid:
            return f
    return None


def get_task(feature: dict, tid: str) -> dict:
    for t in feature.get("tasks", []):
        if t["id"] == tid:
            return t
    raise StoreError(f"task {tid!r} does not exist in feature {feature['id']!r}")


def feature_progress(feature: dict) -> dict:
    tasks = [t for t in feature.get("tasks", []) if not t.get("archived")]
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == "completed")
    return {"done": done, "total": total,
            "label": f"{done}/{total}",
            "percent": (round(100 * done / total) if total else 0)}


def derived_unblocks(data: dict, fid: str) -> list[str]:
    return sorted(f["id"] for f in data.get("features", [])
                  if fid in (f.get("requires") or []))


def review_rollup(data: dict, fid: str) -> dict:
    feature = get_feature(data, fid)
    gallery: list[str] = []
    sessions: list[dict] = []
    for c in feature.get("comments", []):
        gallery.extend(c.get("attachments") or [])
        sessions.extend(c.get("session_refs") or [])
    for t in feature.get("tasks", []):
        for c in t.get("comments", []):
            gallery.extend(c.get("attachments") or [])
            sessions.extend(c.get("session_refs") or [])
    sessions.extend(feature.get("sessions") or [])
    # De-duplicate gallery preserving order.
    seen: set[str] = set()
    uniq_gallery = []
    for g in gallery:
        if g not in seen:
            seen.add(g)
            uniq_gallery.append(g)
    return {
        "feature": feature["id"],
        "status": feature["status"],
        "review": feature.get("review"),
        "progress": feature_progress(feature),
        "tasks": [{"id": t["id"], "title": t["title"], "status": t["status"],
                   "kind": t.get("kind", "work"), "commit": t.get("commit"),
                   "archived": t.get("archived", False)}
                  for t in feature.get("tasks", [])],
        "gallery": uniq_gallery,
        "sessions": sessions,
        "test_level": feature.get("test_level"),
        "branch": feature.get("branch"),
        "worktree": feature.get("worktree"),
    }


def _touch(record: dict) -> None:
    record["updated"] = _now()


def create_feature(data: dict, fid: str | None, title: str,
                   summary: str = "", priority: str = "medium",
                   status: str = "proposed", requires: object = None,
                   spec: dict | None = None, test_level: object = None,
                   branch: str | None = None, worktree: str | None = None) -> dict:
    if not isinstance(title, str) or not title.strip():
        raise StoreError("feature title must not be empty")
    fid = _check_slug("feature", fid or _slugify(title))
    if find_feature(data, fid) is not None:
        raise StoreError(f"feature {fid!r} already exists")
    reqs = _norm_str_list(requires, "feature requires")
    known = {f["id"] for f in data.get("features", [])} | {fid}
    for r in reqs:
        if r == fid:
            raise StoreError("a feature cannot require itself")
        if r not in known and r not in {f["id"] for f in data.get("features", [])}:
            # Allow forward refs only if target exists; strict per plan.
            raise StoreError(f"feature requires unknown feature {r!r}")
    spec_clean = {k: "" for k in SPEC_KEYS}
    if spec:
        if not isinstance(spec, dict):
            raise StoreError("spec must be a mapping")
        for k in SPEC_KEYS:
            if k in spec:
                spec_clean[k] = spec[k] or ""
    now = _now()
    feature = _normalize_feature({
        "id": fid, "title": title.strip(), "summary": summary or "",
        "status": status, "priority": priority, "requires": reqs,
        "spec": spec_clean, "branch": branch, "worktree": worktree,
        "test_level": test_level, "review": {"decision": "pending", "by": None, "at": None},
        "merged": None, "sessions": [], "archived": False,
        "created": now, "updated": now, "comments": [], "tasks": [],
    })
    data.setdefault("features", []).append(feature)
    return feature


def update_feature(data: dict, fid: str, fields: dict) -> dict:
    feature = get_feature(data, fid)
    allowed = {"title", "summary", "status", "priority", "requires",
               "spec", "test_level", "branch", "worktree", "merged"}
    for key, value in (fields or {}).items():
        if key not in allowed:
            continue
        if key == "title":
            if not isinstance(value, str) or not value.strip():
                raise StoreError("feature title must not be empty")
            feature["title"] = value.strip()
        elif key == "status":
            feature["status"] = _check_status(value)
        elif key == "priority":
            feature["priority"] = _check_priority(value)
        elif key == "requires":
            reqs = _norm_str_list(value, "feature requires")
            known = {f["id"] for f in data.get("features", [])}
            for r in reqs:
                if r == fid:
                    raise StoreError("a feature cannot require itself")
                if r not in known:
                    raise StoreError(f"feature requires unknown feature {r!r}")
            feature["requires"] = reqs
        elif key == "spec":
            if not isinstance(value, dict):
                raise StoreError("spec must be a mapping")
            for k in SPEC_KEYS:
                if k in value:
                    feature["spec"][k] = value[k] or ""
        elif key == "merged":
            feature["merged"] = value
        else:
            feature[key] = value
    _touch(feature)
    return feature


def archive_feature(data: dict, fid: str) -> dict:
    feature = get_feature(data, fid)
    feature["archived"] = True
    _touch(feature)
    return feature


def create_task(data: dict, fid: str, tid: str | None, title: str,
                description: str = "", acceptance: str = "",
                status: str = "proposed", priority: str = "medium",
                requires: object = None, kind: str = "work",
                order: object = None) -> dict:
    feature = get_feature(data, fid)
    if not isinstance(title, str) or not title.strip():
        raise StoreError("task title must not be empty")
    tid = _check_slug("task", tid or _slugify(title))
    if any(t["id"] == tid for t in feature["tasks"]):
        raise StoreError(f"task {tid!r} already exists in feature {fid!r}")
    if order is None:
        order = max([t["order"] for t in feature["tasks"]], default=-1) + 1
    now = _now()
    task = _normalize_task({
        "id": tid, "feature_id": fid, "title": title.strip(),
        "description": description or "", "acceptance": acceptance or "",
        "status": status, "priority": priority,
        "requires": requires or [], "order": order, "kind": kind,
        "commit": None, "archived": False, "created": now, "updated": now,
        "comments": [],
    }, fid)
    feature["tasks"].append(task)
    feature["tasks"].sort(key=lambda t: (t["order"], t["id"]))
    _touch(feature)
    return task


def update_task(data: dict, fid: str, tid: str, fields: dict) -> dict:
    feature = get_feature(data, fid)
    task = get_task(feature, tid)
    allowed = {"title", "description", "acceptance", "status", "priority",
               "requires", "order", "commit", "kind"}
    for key, value in (fields or {}).items():
        if key not in allowed:
            continue
        if key == "title":
            if not isinstance(value, str) or not value.strip():
                raise StoreError("task title must not be empty")
            task["title"] = value.strip()
        elif key == "status":
            task["status"] = _task_status(value)
        elif key == "priority":
            task["priority"] = _check_priority(value)
        elif key == "requires":
            task["requires"] = _norm_str_list(value, "task requires")
        elif key == "order":
            try:
                task["order"] = int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise StoreError("task order must be an integer")
        elif key == "kind":
            if value not in TASK_KINDS:
                raise StoreError(f"invalid task kind {value!r}")
            task["kind"] = value
        else:
            task[key] = value
    _touch(task)
    _touch(feature)
    feature["tasks"].sort(key=lambda t: (t["order"], t["id"]))
    return task


def archive_task(data: dict, fid: str, tid: str) -> dict:
    feature = get_feature(data, fid)
    task = get_task(feature, tid)
    task["archived"] = True
    _touch(task)
    _touch(feature)
    return task


def move_task(data: dict, fid: str, tid: str, status: str,
              order: object = None) -> dict:
    """Set a task's status and (optionally) its order among siblings."""
    feature = get_feature(data, fid)
    task = get_task(feature, tid)
    task["status"] = _task_status(status)
    if order is not None:
        try:
            task["order"] = int(order)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise StoreError("task order must be an integer")
    _touch(task)
    _touch(feature)
    feature["tasks"].sort(key=lambda t: (t["order"], t["id"]))
    return task


def claim_task(data: dict, fid: str, tid: str) -> dict:
    """Claim a task for work; refuses a double-claim (plan step 2)."""
    feature = get_feature(data, fid)
    task = get_task(feature, tid)
    if task["status"] == "in_progress":
        raise StoreError(
            f"task {fid}/{tid} is already in_progress; "
            "two sessions never work the same task")
    task["status"] = "in_progress"
    _touch(task)
    _touch(feature)
    return task


def next_review_fixes_id(feature: dict) -> str:
    n = 1
    existing = {t["id"] for t in feature.get("tasks", [])}
    while f"review-fixes-{n}" in existing:
        n += 1
    return f"review-fixes-{n}"


def _next_comment_id(comments: list[dict]) -> str:
    n = len(comments) + 1
    existing = {c["id"] for c in comments}
    cid = f"c{n}"
    while cid in existing:
        n += 1
        cid = f"c{n}"
    return cid


def _add_comment_to(comments: list[dict], author: str, body: str,
                    attachments: object = None,
                    session_refs: object = None) -> dict:
    _check_author(author)
    if not isinstance(body, str) or not body.strip():
        raise StoreError("comment body must not be empty")
    comment = _normalize_comment({
        "id": _next_comment_id(comments), "author": author,
        "created": _now(), "body": body.strip(),
        "attachments": attachments or [], "session_refs": session_refs or [],
    })
    comments.append(comment)
    return comment


def add_feature_comment(data: dict, fid: str, author: str, body: str,
                        attachments: object = None,
                        session_refs: object = None) -> dict:
    feature = get_feature(data, fid)
    comment = _add_comment_to(feature["comments"], author, body,
                              attachments, session_refs)
    _touch(feature)
    return comment


def add_task_comment(data: dict, fid: str, tid: str, author: str, body: str,
                     attachments: object = None,
                     session_refs: object = None) -> dict:
    feature = get_feature(data, fid)
    task = get_task(feature, tid)
    comment = _add_comment_to(task["comments"], author, body,
                              attachments, session_refs)
    _touch(task)
    _touch(feature)
    return comment


def _find_comment(comments: list[dict], cid: str) -> dict:
    for c in comments:
        if c["id"] == cid:
            return c
    raise StoreError(f"comment {cid!r} does not exist")


def update_comment(comments: list[dict], cid: str, body: str,
                   attachments: object = None,
                   session_refs: object = None) -> dict:
    comment = _find_comment(comments, cid)
    if comment["author"] != "human":
        raise StoreError("agent comments are read-only")
    if not isinstance(body, str) or not body.strip():
        raise StoreError("comment body must not be empty")
    comment["body"] = body.strip()
    if attachments is not None:
        comment["attachments"] = _norm_attachments(attachments)
    if session_refs is not None:
        comment["session_refs"] = _norm_session_refs(session_refs)
    return comment


def delete_comment(comments: list[dict], cid: str) -> None:
    comment = _find_comment(comments, cid)
    if comment["author"] != "human":
        raise StoreError("agent comments are read-only")
    comments.remove(comment)


def set_review(data: dict, fid: str, decision: str, by: str,
               comment_body: str | None = None) -> dict:
    """Record the human's explicit review action (distinct from completed)."""
    feature = get_feature(data, fid)
    if decision not in ("changes_requested", "approved_for_merge"):
        raise StoreError(
            "review decision must be 'changes_requested' or 'approved_for_merge'")
    _check_author(by) if False else None
    if by not in AUTHORS:
        raise StoreError("review 'by' must be 'human' or 'agent'")
    if decision == "changes_requested":
        if not comment_body or not str(comment_body).strip():
            raise StoreError("Request changes requires a comment")
    feature["review"] = {"decision": decision, "by": by, "at": _now()}
    if decision == "changes_requested":
        feature["status"] = "in_progress"
    # approved_for_merge deliberately leaves status at in_review:
    # completed is set only by the agent after a verified merge.
    _touch(feature)
    return feature


def link_session(data: dict, fid: str, session_ref: dict,
                 tid: str | None = None) -> dict:
    feature = get_feature(data, fid)
    ref = _normalize_session_ref(session_ref)
    if tid:
        task = get_task(feature, tid)
        task.setdefault("comments", task.get("comments", []))
        # Sessions attach to the feature index; the task link is a
        # comment by convention. Here we index on the feature and
        # return the ref; callers add a comment for narrative.
        feature["sessions"].append(ref)
        _touch(task)
    else:
        feature["sessions"].append(ref)
    _touch(feature)
    return ref


def record_merge(data: dict, fid: str, commit: str) -> dict:
    feature = get_feature(data, fid)
    if not commit or not str(commit).strip():
        raise StoreError("merge commit must not be empty")
    feature["merged"] = {"commit": str(commit).strip(), "at": _now()}
    feature["status"] = "completed"
    for t in feature["tasks"]:
        if not t.get("archived") and t["status"] in ("in_review", "in_progress"):
            t["status"] = "completed"
            _touch(t)
    _touch(feature)
    return feature


# --- Markdown export (one-way, feature-level) ---

def export_feature_md(feature: dict, data: dict) -> str:
    spec = feature.get("spec") or {}
    lines: list[str] = []
    lines.append("---")
    lines.append(f"title: {feature['title']}")
    lines.append(f"summary: {feature.get('summary') or ''}")
    lines.append(f"status: {feature['status']}")
    lines.append(f"priority: {feature['priority']}")
    reqs = feature.get("requires") or []
    lines.append("requires:")
    for r in reqs:
        lines.append(f"  - ./{r}.md")
    if not reqs:
        lines.append("  []")
    unblocks = derived_unblocks(data, feature["id"])
    lines.append("unblocks:")
    for u in unblocks:
        lines.append(f"  - ./{u}.md")
    if not unblocks:
        lines.append("  []")
    lines.append("---")
    lines.append("")
    lines.append(f"# Feature: {feature['title']}")
    lines.append("")
    lines.append("<!-- Generated by the project-manager tool from pm.yml. "
                 "Do not edit by hand; the store is the source of truth. -->")
    lines.append("")
    for key in SPEC_KEYS:
        lines.append(f"## {SPEC_TITLES[key]}")
        lines.append("")
        lines.append((spec.get(key) or "").strip() or "_(to be written)_")
        lines.append("")
    lines.append("## Tasks")
    lines.append("")
    tasks = feature.get("tasks") or []
    if not tasks:
        lines.append("_(no tasks yet)_")
        lines.append("")
    for t in sorted(tasks, key=lambda x: (x.get("order", 0), x["id"])):
        arch = " (archived)" if t.get("archived") else ""
        lines.append(f"### {feature['id']}/{t['id']} — {t['title']}{arch}")
        lines.append("")
        lines.append(f"- Status: `{t['status']}` · Priority: `{t['priority']}` "
                     f"· Kind: `{t.get('kind', 'work')}`"
                     + (f" · Commit: `{t['commit']}`" if t.get("commit") else ""))
        if t.get("description"):
            lines.append(f"- Description: {t['description']}")
        if t.get("acceptance"):
            lines.append(f"- Acceptance: {t['acceptance']}")
        for c in t.get("comments") or []:
            for a in c.get("attachments") or []:
                lines.append(f"- Evidence: `{a}`")
            for s in c.get("session_refs") or []:
                lines.append(f"- Session: `{s.get('id')}` "
                             f"({s.get('level')}, {s.get('created_by')}, {s.get('result')})")
        lines.append("")
    lines.append("## Comments")
    lines.append("")
    all_comments: list[tuple[str, dict]] = []
    for c in feature.get("comments") or []:
        all_comments.append((feature["id"], c))
    for t in tasks:
        for c in t.get("comments") or []:
            all_comments.append((f"{feature['id']}/{t['id']}", c))
    if not all_comments:
        lines.append("_(no comments yet)_")
        lines.append("")
    for scope, c in all_comments:
        lines.append(f"### {c.get('created', '')} · {c.get('author', '')} · on `{scope}`")
        lines.append("")
        lines.append(c.get("body") or "")
        for a in c.get("attachments") or []:
            lines.append(f"- Evidence: `{a}`")
        for s in c.get("session_refs") or []:
            lines.append(f"- Session: `{s.get('id')}` "
                         f"({s.get('level')}, {s.get('created_by')}, {s.get('result')})")
        lines.append("")
    return "\n".join(lines)


def export_all(data: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for feature in data.get("features", []):
        path = out_dir / f"{feature['id']}.md"
        path.write_text(export_feature_md(feature, data), encoding="utf-8")
        written.append(path)
    return written


# --- Seeding (idempotent) ---

SEED_FEATURES: list[dict] = []  # filled below; kept as data for clarity


def _seed() -> list[dict]:
    def spec(goal, user_story, use_case, behavior, edge_cases, ui_feedback,
             assets_needed, acceptance, out_of_scope, open_questions, testing):
        return {"goal": goal, "user_story": user_story, "use_case": use_case,
                "behavior": behavior, "edge_cases": edge_cases,
                "ui_feedback": ui_feedback, "assets_needed": assets_needed,
                "acceptance": acceptance, "out_of_scope": out_of_scope,
                "open_questions": open_questions, "testing": testing}
    def task(tid, title, acceptance):
        return {"id": tid, "title": title, "acceptance": acceptance}
    return [
        {
            "id": "game-shell", "title": "Game shell and deterministic core",
            "summary": "A playable game page with a deterministic step function and session recording from the first build.",
            "priority": "urgent", "requires": [], "test_level": None,
            "spec": spec(
                "Provide the game page that every later mechanic plugs into. The engine step function is pure and deterministic: given the initial level plus the ordered, timestamped input log, the same run always produces the same states. The timer is a real counting clock reproduced in replay from recorded t_ms timestamps, never from unrecorded wall-clock reads.",
                "**As a** player\n**I want** to open the game, pick a level, and play\n**So that** later mechanics have a deterministic, recordable home.",
                "Player opens the game URL, chooses a level or Test Level from the game menu, and plays with the keyboard. Every play is recorded as a JSONL session from the first playable build.",
                "- Given a level file, when the game loads, then it renders that level.\n- Given the same initial level and the same timestamped input log, when the log is replayed, then the same states result.\n- Every play writes a JSONL session (header, steps, end) labelled by creator.",
                "- Timer at any step is a function of recorded elapsed time (t_ms since session start).\n- Rendering is a view of state, never a driver of it.",
                "- Game menus list levels and Test Levels with a start action.\n- Debug readout shows the last registered input.",
                "- Sprites: reuse level-preview sprites from tools/static/level-sprites.\n- Level JSON: existing levels/*.json format (rows + legend).",
                "- [ ] game.html renders a chosen level.\n- [ ] Same log replays to the same states.\n- [ ] Every play writes a JSONL session.\n- [ ] A Test Level can be launched from the game menu.",
                "- Movement, timer-loss, keys, orbs and warp mechanics (later features).\n- Procedural level generation.",
                "- Session file layout is fixed by the project-manager plan (header/steps/end/annotations).",
                "Needs a mechanics playground: reuse — the game menu must launch Test Levels; no dedicated room for this feature itself. Verification should record play sessions for replay."),
            "tasks": [
                task("scaffold-game-page", "Scaffold game.html extending the level preview", "game.html renders a chosen level (rows + legend) in the browser."),
                task("deterministic-core", "Deterministic state core: pure step function", "Same initial level + timestamped input log always replays to the same states; timer derived from recorded t_ms (real counting clock)."),
                task("session-recording", "Session recording from the first playable build", "Every play writes its JSONL header + steps + end line; no session is ever unrecorded."),
                task("game-menus", "Game menus: level and Test Level selection", "A playground/Test Level can be launched from inside the game menu."),
                task("keyboard-input", "Keyboard input scaffold", "WASD/arrow input is registered and visible in the debug readout."),
            ],
        },
        {
            "id": "player-movement", "title": "Player movement and collision",
            "summary": "Move Jolly one tile per keypress with wall, lock and gate collision.",
            "priority": "urgent", "requires": ["game-shell"], "test_level": "movement-room",
            "spec": spec(
                "Let the player move around a level one tile at a time. Movement is the first mechanic built on the deterministic core, so its sessions become the first replayable evidence.",
                "**As a** player\n**I want** to move Jolly with WASD or arrow keys\n**So that** I can explore the level and reach keys, orbs and the gate.",
                "Player presses a direction key; Jolly moves one tile if the target is walkable floor, otherwise stays. The sprite follows the state position.",
                "- Given floor ahead, when the player presses a direction, then Jolly moves one tile.\n- Given a wall, lock or gate ahead, when the player presses toward it, then Jolly does not move.",
                "- Only floor is walkable in this feature; keys/orbs/gate behaviour arrives in later features.\n- Movement is one tile per keypress, recorded as a timestamped input.",
                "- Player sprite renders at the state position after each step.",
                "- Sprites: jolly.png on floor_default.png.\n- Level JSON: a Test Level empty room.",
                "- [ ] Empty-room Test Level loads with Jolly placed.\n- [ ] One tile per keypress on floor only.\n- [ ] Walls block movement.\n- [ ] Sprite matches state position.\n- [ ] Recorded session replays to the same end state.",
                "- Picking up keys/orbs, opening locks/gates (later features).",
                "- None.",
                "Needs a mechanics playground: new — an empty-room Test Level (movement-room). Verification should record play sessions for replay."),
            "tasks": [
                task("movement-test-level", "Test Level: empty room", "Empty-room Test Level loads and Jolly is placed."),
                task("move-one-tile", "Move one tile per keypress", "Each keypress moves Jolly exactly one tile on floor."),
                task("collision", "Wall, lock and gate collision", "Pressing into a wall, lock or closed gate does not move Jolly."),
                task("sprite-follows-state", "Player sprite follows state", "Rendered sprite position always matches the state position."),
            ],
        },
        {
            "id": "session-logs-replay", "title": "Session logs, replay and forks",
            "summary": "Find, annotate, replay and fork recorded play sessions from the game UI.",
            "priority": "high", "requires": ["player-movement"], "test_level": None,
            "spec": spec(
                "Make recorded sessions reviewable: a reviewer can find a session in seconds, replay it to pinpoint where something went wrong, and fork a new playable session from any replay point. Built immediately after player-movement so every later feature's playtest evidence is a replayable session, not just screenshots.",
                "**As a** reviewer\n**I want** to find, replay and fork a recorded session\n**So that** I can pinpoint the exact failing move instead of guessing from a still image.",
                "Reviewer opens the Sessions menu, filters to the session, opens it (or follows a ?replay=<id>&t=<seconds> deep link — time-based per NQ30), watches the replay with speed controls (1x, 2x, 5x, 10x; NQ29: no idle-gap compression so the countdown timer reads exactly), and forks from the paused point to try a different action.",
                "- Given the Sessions menu, when filtering by level, creator, feature, date, result or annotation labels, then the named session is findable in seconds.\n- Given a replay, when it plays, then inputs play back at their recorded t_ms spacing (viewer speed 1x/2x/5x/10x, pause/step/scrub) and the per-step readout shows step, position, inventory, orbs left, timer and the input.\n- Given a paused replay, when the reviewer forks, then a new playable session starts from that state; its header keeps the original created_by and adds forked_by, forked_from and fork_step.\n- Given a session, when a note or label is added afterwards, then it is appended as an annotation line; replay ignores annotations. Labels are free-form lowercase (NQ28), with failed and bug as suggested starters.\n- Given a replay under a different level/engine version than recorded, then the UI warns instead of diverging silently.",
                "- Deep links are time-based: ?replay=<session-id>&t=<seconds> lands on that moment (step index is derived from t_ms).\n- Annotations are append-only; a correction is a new line.\n- Only the game loop is deterministic; level generation happens outside it (NQ26).",
                "- Sessions menu with filters and a replay bar (play/pause, step, scrubber, speed).\n- Per-step state readout (step, position, inventory, orbs, timer, input).",
                "- No new sprites.\n- Session JSONL files under sessions/ (gitignored).",
                "- [ ] A named session is findable in seconds via filters.\n- [ ] Notes/labels can be added after play without touching recorded steps.\n- [ ] Replay with a t-based deep link lands on the exact moment; record-then-replay reaches the same end state.\n- [ ] Fork from a replay point is playable and keeps the original created_by.\n- [ ] Version mismatch warns.",
                "- Spawning board tasks from a bug-labelled session (linking in a comment is enough for v1).",
                "- Replay speed set is 1x/2x/5x/10x (NQ29); no idle-gap compression.",
                "Needs a mechanics playground: none — verified against recorded sessions of the movement-room Test Level. Verification records its own sessions."),
            "tasks": [
                task("sessions-menu", "Sessions menu in the game UI", "Sessions list/filter by level, creator, feature, date, result and labels finds a named session in seconds."),
                task("annotate-session", "Annotate a session after play", "Notes and labels (e.g. failed, bug) append to the session JSONL without touching recorded steps."),
                task("replay-player", "Replay player with deep links", "Play/pause, step, scrub and speeds 1x/2x/5x/10x; ?replay=<id>&t=<seconds> lands on the exact moment with a per-step state readout."),
                task("fork-from-replay", "Fork from any replay step", "Forked session keeps the original created_by and adds forked_by/forked_from/fork_step, playable from that state."),
                task("version-mismatch-warning", "Version-mismatch warning", "Replaying under a different level/engine than recorded warns instead of diverging silently."),
            ],
        },
        {
            "id": "level-timer", "title": "Level timer and restart",
            "summary": "A real counting countdown that ends the run at zero, with restart.",
            "priority": "high", "requires": ["game-shell"], "test_level": None,
            "spec": spec(
                "Give each level a time limit. The countdown is a real counting clock: it counts down in real time while playing, and every input is recorded with its elapsed time, so the timer value at any step is a function of the session log.",
                "**As a** player\n**I want** a visible countdown and a restart key\n**So that** levels have pressure and a failed run is one keypress to retry.",
                "The HUD timer ticks down from the level limit. At zero the run is lost with a message. Pressing R (or the restart button) restores position, orbs, keys and timer.",
                "- Given a running level, when time passes, then the countdown decreases in real time.\n- Given the timer reaches zero, then the run ends as lost with a message.\n- Given R or the restart button, then position, orbs, keys and timer are restored.",
                "- Timer value at any replay step comes from recorded t_ms, never unrecorded wall-clock reads.\n- Restart starts a new recorded session.",
                "- HUD countdown display; loss message; restart button.",
                "- Level JSON: a per-level time limit.",
                "- [ ] Countdown ticks from the level limit.\n- [ ] Expiry ends the run with a message.\n- [ ] Restart restores position/orbs/keys/timer.\n- [ ] A timeout loss replays as a loss at the same moment.",
                "- Pause behaviour (not specified; out of scope until asked).",
                "- None.",
                "Needs a mechanics playground: none — verified in any level; a short-limit test level may be added by the implementing task if useful. Verification should record play sessions for replay."),
            "tasks": [
                task("countdown", "Countdown from level limit", "HUD timer counts down in real time from the level limit."),
                task("lose-at-zero", "Lose at zero with message", "Timer expiry ends the run as lost and shows a message."),
                task("restart", "Restart with R and button", "R and the restart button restore position, orbs, keys and timer."),
            ],
        },
        {
            "id": "keys-and-locks", "title": "Keys and locks",
            "summary": "Pick up coloured keys into 8 inventory slots; matching locks dissolve and consume the key.",
            "priority": "high", "requires": ["player-movement"], "test_level": "keys-room",
            "spec": spec(
                "Add coloured keys and matching lock blocks, the core gating mechanic beside orbs. Keys occupy the player's 8 inventory slots; pressing against a matching lock consumes one key and dissolves the lock.",
                "**As a** player\n**I want** to pick up keys and open matching locks\n**So that** I can open paths that were blocked.",
                "Player walks onto a key and it enters the first free inventory slot. Pressing against a lock of the same colour consumes one matching key and the lock dissolves. A wrong-colour lock does nothing.",
                "- Given a key tile, when the player walks onto it, then the key enters the first free of 8 slots.\n- Given a full inventory (8 keys), when the player walks onto a 9th key, then the key stays on the floor.\n- Given a matching lock, when the player presses against it holding that colour, then one key is consumed and the lock dissolves.\n- Given a wrong-colour lock, when the player presses against it, then nothing happens.",
                "- Inventory holds at most 8 keys.\n- Lock colour must match key colour exactly.\n- Dissolved locks become walkable floor.",
                "- Inventory slots (8) in the HUD; key and lock sprites per colour.",
                "- Sprites: key_<colour>.png and wall_keyhole_<colour>.png (placeholders exist in chip1 legend).\n- Level JSON: keys-room Test Level.",
                "- [ ] Key pickup fills the first free slot.\n- [ ] 9th key stays when full.\n- [ ] Matching lock consumes the key and dissolves.\n- [ ] Wrong-colour lock does nothing.\n- [ ] Recorded session replays to the same end state.",
                "- Non-key inventory items.",
                "- None.",
                "Needs a mechanics playground: new — a keys-room Test Level with keys, locks and an orb. Verification should record play sessions for replay."),
            "tasks": [
                task("keys-test-level", "Test Level: room with keys, locks and an orb", "Keys-room Test Level places keys, locks and an orb; all tiles are placed and readable."),
                task("key-pickup", "Walk onto key to pick it up", "Walking onto a key puts it in the first free of 8 inventory slots."),
                task("inventory-full", "Inventory full behaviour", "With 8 keys held, a 9th key stays on the floor."),
                task("matching-lock", "Matching lock press", "Pressing a matching lock consumes one key and the lock dissolves."),
                task("wrong-colour-lock", "Wrong-colour lock press", "Pressing a lock without its colour does nothing."),
            ],
        },
        {
            "id": "orbs-and-gate", "title": "Orbs and gate",
            "summary": "Collect all orbs to open the gate that blocks the warp.",
            "priority": "high", "requires": ["player-movement"], "test_level": "orbs-room",
            "spec": spec(
                "Add orbs and the gate. Orbs never enter the inventory; each one decrements the orbs-left counter. The gate blocks like a wall until the counter reaches zero, then it opens.",
                "**As a** player\n**I want** collecting every orb to open the gate\n**So that** I can reach the warp and finish the level.",
                "Player walks onto orbs; the orbs-left counter decrements. The gate is shut and blocks movement while orbs remain. At zero orbs the gate opens and becomes passable.",
                "- Given an orb, when the player walks onto it, then orbs-left decrements (not inventory).\n- Given orbs remaining, when the player presses the gate, then it blocks like a wall.\n- Given zero orbs left, then the gate opens, is passable, and its state/sprite changes.",
                "- Orbs are not inventory items.\n- Gate state is part of deterministic state and replays exactly.",
                "- Orbs-left counter in the HUD; gate open/shut sprites.",
                "- Sprites: orb.png, gate.png.\n- Level JSON: orbs-room Test Level.",
                "- [ ] Orb pickup decrements orbs-left only.\n- [ ] Gate blocks while orbs remain.\n- [ ] Gate opens and is passable at zero.\n- [ ] Recorded session replays to the same end state.",
                "- Warp progression itself (warp-and-levels feature).",
                "- None.",
                "Needs a mechanics playground: new — an orbs-room Test Level with a gated portal and orbs. Verification should record play sessions for replay."),
            "tasks": [
                task("orbs-test-level", "Test Level: gated portal with orbs", "Orbs-room Test Level places a gated portal with orbs; the gate is shut at start."),
                task("orb-pickup", "Walk onto orb", "Walking onto an orb decrements orbs-left and does not use inventory."),
                task("gate-blocks", "Gate shut while orbs remain", "The shut gate blocks movement like a wall."),
                task("gate-opens", "Gate opens at zero orbs", "At zero orbs the gate opens, is passable, and state/sprites change."),
            ],
        },
        {
            "id": "warp-and-levels", "title": "Warp and level progression",
            "summary": "Stepping on the warp behind the open gate loads the next level.",
            "priority": "medium", "requires": ["orbs-and-gate"], "test_level": None,
            "spec": spec(
                "Complete the level loop: the warp tile behind the gate takes the player to the next level, and progression state tracks the current level.",
                "**As a** player\n**I want** finishing a level to load the next one\n**So that** I can progress through the level set.",
                "Player collects all orbs, the gate opens, the player steps on the warp, and the next level loads with the level counter advanced.",
                "- Given an open gate, when the player steps on the warp, then the next level loads.\n- Given progression, then the current-level counter advances.",
                "- Warp is only reachable behind the gate (gate rules from orbs-and-gate).\n- Last-level behaviour follows the open question below until resolved.",
                "- Current-level display advances; next level renders.",
                "- Level JSON: an ordered level list.",
                "- [ ] Warp behind the gate loads the next level.\n- [ ] Level counter advances.",
                "- Level select beyond the game menu basics.",
                "- What happens after the last level: loop, win screen, or back to menu? Resolve during implementation and record the choice here.",
                "Needs a mechanics playground: reuse — the orbs-room Test Level plus a second level to warp into. Verification should record play sessions for replay."),
            "tasks": [
                task("warp-loads-next", "Step on warp behind gate", "Stepping on the warp behind the open gate loads the next level."),
                task("progression-state", "Progression state", "Level counter advances; last-level behaviour follows the recorded open-question decision."),
            ],
        },
        {
            "id": "hud", "title": "HUD: timer, orbs, level and inventory",
            "summary": "Live heads-up display per the full-level UI reference.",
            "priority": "medium", "requires": ["game-shell"], "test_level": None,
            "spec": spec(
                "Show the player the state that matters: countdown timer, orbs left, current level, and the 8-slot inventory, live from game state, per scratchpad/full-level-ui.png.",
                "**As a** player\n**I want** to see the timer, orbs left, level and my keys\n**So that** I always know my progress and what I am carrying.",
                "The HUD renders four readouts from state on every step: timer, orbs-left, current level, and 8 inventory slots showing held keys.",
                "- Given any state change, when it renders, then timer, orbs-left, level and inventory all match state.",
                "- Inventory shows at most 8 slots.\n- HUD is a view of state; it never drives state.",
                "- Four HUD elements per scratchpad/full-level-ui.png.",
                "- Sprites: key colour icons for inventory slots.",
                "- [ ] Timer display is live from state.\n- [ ] Orbs-left display is live from state.\n- [ ] Current-level display is live from state.\n- [ ] Inventory shows held keys in 8 slots.",
                "- Score, lives or other HUD elements not in the reference.",
                "- None.",
                "Needs a mechanics playground: none — verified in any level against state. Verification may record sessions; screenshots are the primary evidence."),
            "tasks": [
                task("hud-timer", "Timer display", "HUD timer shows the live countdown from state."),
                task("hud-orbs", "Orbs-left display", "HUD shows the live orbs-left count from state."),
                task("hud-level", "Current-level display", "HUD shows the current level from state."),
                task("hud-inventory", "Inventory display (8 slots)", "HUD shows held keys in 8 slots, live from state, per the full-level UI reference."),
            ],
        },
    ]


SEED_FEATURES = _seed()


def seed_pm(data: dict) -> dict:
    """Idempotently add the seeded features and starter tasks.

    Existing features/tasks (matched by id) are left untouched, so
    re-running seed never duplicates or overwrites human edits.
    Returns {features_added, tasks_added}.
    """
    added_f = 0
    added_t = 0
    for seed in SEED_FEATURES:
        existing = find_feature(data, seed["id"])
        if existing is None:
            now = _now()
            feature = _normalize_feature({
                "id": seed["id"], "title": seed["title"],
                "summary": seed["summary"], "status": "proposed",
                "priority": seed["priority"], "requires": seed["requires"],
                "spec": seed["spec"], "branch": f"feat/{seed['id']}",
                "worktree": f".worktrees/{seed['id']}",
                "test_level": seed.get("test_level"),
                "review": {"decision": "pending", "by": None, "at": None},
                "merged": None, "sessions": [], "archived": False,
                "created": now, "updated": now, "comments": [], "tasks": [],
            })
            data.setdefault("features", []).append(feature)
            existing = feature
            added_f += 1
        have = {t["id"] for t in existing["tasks"]}
        for idx, st in enumerate(seed["tasks"]):
            if st["id"] in have:
                continue
            now = _now()
            task = _normalize_task({
                "id": st["id"], "feature_id": seed["id"], "title": st["title"],
                "description": "", "acceptance": st["acceptance"],
                "status": "proposed", "priority": seed["priority"],
                "requires": [], "order": idx, "kind": "work", "commit": None,
                "archived": False, "created": now, "updated": now, "comments": [],
            }, seed["id"])
            existing["tasks"].append(task)
            added_t += 1
        existing["tasks"].sort(key=lambda t: (t["order"], t["id"]))
    return {"features_added": added_f, "tasks_added": added_t}
