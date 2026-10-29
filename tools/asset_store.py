"""Backend-owned storage for the iterative asset design tool.

The backend is the sole writer of ``assets/manifest.yml`` and
``assets/judgements.yml``; users never hand-edit them. All writes are atomic
(temp file + rename). Leading comment blocks in both files are preserved
across saves.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "assets" / "manifest.yml"
JUDGEMENTS_PATH = Path(__file__).resolve().parent.parent / "assets" / "judgements.yml"
SESSIONS_PATH = Path(__file__).resolve().parent.parent / "assets" / "sessions.yml"

LOTTERY_MIN = 1
LOTTERY_MAX = 10
LOTTERY_DEFAULT = 4
MAX_REFERENCES = 10

CHECKLIST_ORDER = [
    "covers_frame",
    "square_corners",
    "no_cracks",
    "no_weathering",
    "seamless_3x3",
]

CHECKLIST_CONSTRAINTS = {
    "covers_frame": "texture must fill the entire frame edge to edge with no margin/border",
    "square_corners": "sharp square 90-degree corners, no rounding/bevel",
    "no_cracks": "no cracks/joints/grout/flagstones",
    "no_weathering": "no moss/weathering/stains",
    "seamless_3x3": "opposite edges must match so 3x3 tiling shows no seams",
}


def normalize_run_count(value: object) -> int:
    """Validate the lottery size N (1-10). None means the default."""
    if value is None:
        return LOTTERY_DEFAULT
    if isinstance(value, bool):
        raise StoreError("num must be an integer between 1 and 10")
    if isinstance(value, float):
        if not value.is_integer():
            raise StoreError("num must be an integer between 1 and 10")
        value = int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return LOTTERY_DEFAULT
        try:
            value = int(text)
        except ValueError:
            raise StoreError("num must be an integer between 1 and 10")
    if not isinstance(value, int):
        raise StoreError("num must be an integer between 1 and 10")
    if not LOTTERY_MIN <= value <= LOTTERY_MAX:
        raise StoreError("num must be between 1 and 10")
    return value


def validate_references(references: object) -> list:
    """Validate the reference list shape and the 10-image cap."""
    if references is None:
        return []
    if not isinstance(references, list):
        raise StoreError("references must be a list of output filenames")
    if len(references) > MAX_REFERENCES:
        raise StoreError(
            f"at most {MAX_REFERENCES} reference images are allowed "
            f"(got {len(references)})"
        )
    cleaned: list = []
    for ref in references:
        if not isinstance(ref, str) or not ref.strip():
            raise StoreError("each reference must be a non-empty filename")
        cleaned.append(ref.strip())
    return cleaned


def lottery_keys(base: str, num: int) -> list[str]:
    """Return output keys for one run. N=1 keeps the legacy bare key."""
    count = normalize_run_count(num)
    if not base or not base.strip():
        raise StoreError("base key must not be empty")
    base = base.strip()
    if count == 1:
        return [base]
    return [f"{base}-{i + 1}" for i in range(count)]


def split_cost_per_output(total: object, num: int) -> str | None:
    """Split a run total across N outputs as a 2-decimal string."""
    count = normalize_run_count(num)
    if total is None:
        return None
    try:
        amount = float(total)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f"{amount / count:.2f}"


def build_prompt_draft(parent_prompt: object, human_review: object = "",
                       checklist: object = None) -> str:
    """Draft a child prompt from parent prompt + parent judgement.

    Pure helper shared by the New Version UI (mirrored in JS) so the user
    edits rather than cobbles together constraints. Returns the parent
    prompt unchanged when there is no judgement to carry forward.
    """
    base = (parent_prompt or "") if isinstance(parent_prompt, str) else ""
    base = base.strip()
    review = (human_review or "") if isinstance(human_review, str) else ""
    review = review.strip()
    checks = checklist if isinstance(checklist, dict) else {}
    failed = [k for k in CHECKLIST_ORDER if checks.get(k) is False]
    constraints = [CHECKLIST_CONSTRAINTS[k] for k in failed
                   if k in CHECKLIST_CONSTRAINTS]
    if not constraints and not review:
        return base
    if constraints and review:
        block = ("Constraints from parent judgement: "
                 + "; ".join(constraints)
                 + '. Parent noted: "' + review + '"')
    elif constraints:
        block = "Constraints from parent judgement: " + "; ".join(constraints)
    else:
        block = "Constraints from parent judgement: " + review
    return (base + "\n\n" + block).strip() if base else block


class StoreError(ValueError):
    """Raised for invalid names, duplicates, or missing parents."""


def _split_header(text: str) -> tuple[str, str]:
    """Split leading comment/blank lines (header) from the YAML body."""
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
    """Return (data, header). Missing files read as empty data."""
    if not path.is_file():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    header, body = _split_header(text)
    data = yaml.safe_load(body) or {}
    if not isinstance(data, dict):
        raise StoreError(f"{path} must contain a mapping at the top level")
    return data, header


def _save_yaml(path: Path, data: dict, header: str) -> None:
    """Atomically write data with the preserved header prepended."""
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


def _migrate_versions(raw: object) -> list[dict]:
    """Migrate the legacy single-mapping ``versions:`` to a version list.

    Legacy ``queue: completed|failed`` maps to ``status``; any other queue
    (ready/ignore) means the version has not run yet, so status is None.
    """
    if isinstance(raw, list):
        versions = []
        for entry in raw:
            if not isinstance(entry, dict):
                raise StoreError("each version must be a mapping")
            versions.append(_normalize_version(entry))
        return versions
    if isinstance(raw, dict):
        entry = dict(raw)
        queue = entry.pop("queue", None)
        version = _normalize_version(entry)
        version["status"] = {"completed": "completed", "failed": "failed"}.get(queue)
        return [version]
    raise StoreError("versions must be a mapping or a list of mappings")


def _normalize_output(entry: object) -> dict:
    if not isinstance(entry, dict):
        raise StoreError("each output must be a mapping")
    if not entry.get("key") or not entry.get("path"):
        raise StoreError("each output must have a key and a path")
    return {
        "key": entry.get("key"),
        "path": entry.get("path"),
        "estimated_usd": entry.get("estimated_usd"),
        "original_path": entry.get("original_path"),
        "requested_width": entry.get("requested_width"),
        "requested_height": entry.get("requested_height"),
        "raw_width": entry.get("raw_width"),
        "raw_height": entry.get("raw_height"),
    }


def _normalize_version(entry: dict) -> dict:
    if not isinstance(entry.get("slug"), str) or not NAME_RE.match(entry["slug"]):
        raise StoreError(f"invalid version slug: {entry.get('slug')!r}")
    return {
        "slug": entry.get("slug"),
        "desc": entry.get("desc") or "",
        "prompt": entry.get("prompt") or "",
        "parent": entry.get("parent"),
        "status": entry.get("status"),
        "width": entry.get("width"),
        "height": entry.get("height"),
        "references": validate_references(entry.get("references")),
        "outputs": [_normalize_output(o) for o in (entry.get("outputs") or [])],
    }


def _normalize_asset(name: str, raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise StoreError(f"asset {name!r} must be a mapping")
    return {
        "width": raw.get("width"),
        "height": raw.get("height"),
        "versions": _migrate_versions(raw.get("versions") or []),
    }


def load_manifest(path: Path = MANIFEST_PATH) -> tuple[dict, str]:
    """Return (assets, header) with versions normalized and migrated."""
    data, header = _load_yaml(path)
    raw_assets = data.get("assets") or {}
    if not isinstance(raw_assets, dict):
        raise StoreError("manifest 'assets' must be a mapping")
    assets = {}
    for name, raw in raw_assets.items():
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise StoreError(f"invalid asset name: {name!r}")
        assets[name] = _normalize_asset(name, raw)
    return assets, header


def save_manifest(assets: dict, header: str, path: Path = MANIFEST_PATH) -> None:
    _save_yaml(path, {"assets": assets}, header)


def load_judgements(path: Path = JUDGEMENTS_PATH) -> tuple[dict, str]:
    """Return (judgements, header). Judgements map output key -> record."""
    data, header = _load_yaml(path)
    return data, header


def save_judgements(judgements: dict, header: str, path: Path = JUDGEMENTS_PATH) -> None:
    _save_yaml(path, judgements, header)


def _check_name(kind: str, value: str) -> None:
    if not isinstance(value, str) or not NAME_RE.match(value):
        raise StoreError(
            f"invalid {kind} name {value!r}: use letters, digits, '-' or '_'")


def create_asset(assets: dict, name: str, width: int, height: int) -> dict:
    _check_name("asset", name)
    if name in assets:
        raise StoreError(f"asset {name!r} already exists")
    if not isinstance(width, int) or not isinstance(height, int):
        raise StoreError("width and height must be integers")
    if width <= 0 or height <= 0:
        raise StoreError("width and height must be positive integers")
    assets[name] = {"width": width, "height": height, "versions": []}
    return assets[name]


def update_asset(assets: dict, name: str, width: int, height: int) -> dict:
    if name not in assets:
        raise StoreError(f"asset {name!r} does not exist")
    if not isinstance(width, int) or not isinstance(height, int):
        raise StoreError("width and height must be integers")
    if width <= 0 or height <= 0:
        raise StoreError("width and height must be positive integers")
    assets[name]["width"] = width
    assets[name]["height"] = height
    return assets[name]


def get_version(asset: dict, slug: str) -> dict:
    for version in asset["versions"]:
        if version["slug"] == slug:
            return version
    raise StoreError(f"version {slug!r} does not exist")


def add_version(assets: dict, asset_name: str, slug: str, desc: str,
                prompt: str, parent: str | None = None,
                width: int | None = None,
                height: int | None = None,
                references: object = None) -> dict:
    _check_name("version", slug)
    if asset_name not in assets:
        raise StoreError(f"asset {asset_name!r} does not exist")
    asset = assets[asset_name]
    if any(v["slug"] == slug for v in asset["versions"]):
        raise StoreError(f"version {slug!r} already exists in {asset_name!r}")
    if parent is not None:
        get_version(asset, parent)  # raises when the parent is missing
    if not (prompt or "").strip():
        raise StoreError("prompt must not be empty")
    for label, value in (("width", width), ("height", height)):
        if value is not None and (not isinstance(value, int) or value <= 0):
            raise StoreError(f"{label} override must be a positive integer")
    version = {
        "slug": slug,
        "desc": desc or "",
        "prompt": prompt,
        "parent": parent,
        "status": None,
        "width": width,
        "height": height,
        "references": validate_references(references),
        "outputs": [],
    }
    asset["versions"].append(version)
    return version


def update_version(assets: dict, asset_name: str, slug: str, desc: str,
                   prompt: str, width: int | None = None,
                   height: int | None = None,
                   references: object = None) -> dict:
    """Update an existing version's editable fields in place.

    Slug and parent are immutable: the slug keys outputs and judgements,
    so renaming would orphan records. Width/height of None clears that
    override back to the asset default. References of None leaves the
    stored selection unchanged; pass a list (possibly empty) to replace it.
    """
    if asset_name not in assets:
        raise StoreError(f"asset {asset_name!r} does not exist")
    version = get_version(assets[asset_name], slug)
    if not (prompt or "").strip():
        raise StoreError("prompt must not be empty")
    for label, value in (("width", width), ("height", height)):
        if value is not None and (not isinstance(value, int) or value <= 0):
            raise StoreError(f"{label} override must be a positive integer")
    version["desc"] = desc or ""
    version["prompt"] = prompt
    version["width"] = width
    version["height"] = height
    if references is not None:
        version["references"] = validate_references(references)
    return version


def record_output(assets: dict, asset_name: str, slug: str, key: str,
                  path: str, estimated_usd: str | float | None,
                  original_path: str | None = None,
                  requested_width: int | None = None,
                  requested_height: int | None = None,
                  raw_width: int | None = None,
                  raw_height: int | None = None) -> dict:
    if asset_name not in assets:
        raise StoreError(f"asset {asset_name!r} does not exist")
    version = get_version(assets[asset_name], slug)
    output = {
        "key": key,
        "path": path,
        "estimated_usd": estimated_usd,
        "original_path": original_path,
        "requested_width": requested_width,
        "requested_height": requested_height,
        "raw_width": raw_width,
        "raw_height": raw_height,
    }
    version["outputs"].append(output)
    version["status"] = "completed"
    return output


def mark_failed(assets: dict, asset_name: str, slug: str) -> None:
    if asset_name not in assets:
        raise StoreError(f"asset {asset_name!r} does not exist")
    get_version(assets[asset_name], slug)["status"] = "failed"


def save_judgement(judgements: dict, key: str, human_review: str,
                   checklist: dict | None = None,
                   preferred: bool | None = None) -> dict:
    if not (key or "").strip():
        raise StoreError("judgement key must not be empty")
    record = judgements.get(key) or {}
    record["human_review"] = human_review or ""
    if checklist is not None:
        if not isinstance(checklist, dict):
            raise StoreError("checklist must be a mapping")
        record["checklist"] = {str(k): bool(v) for k, v in checklist.items()}
    if preferred is not None:
        record["preferred"] = bool(preferred)
    judgements[key] = record
    return record


def validate_run_not_noop(version: dict, parent: dict | None,
                          references: list | None) -> None:
    """Block a first run that cannot differ from its parent.

    A child whose prompt is byte-identical to its parent's, run with no
    reference image and no prior outputs, is a fresh draw from the same
    prompt — not an iteration. Re-runs of an already-run version and any
    run with a reference or a changed prompt are legitimate.
    """
    if parent is None or version.get("outputs"):
        return
    if references:
        return
    if (version.get("prompt") or "") != (parent.get("prompt") or ""):
        return
    raise StoreError(
        "prompt is identical to parent "
        f"{parent.get('slug')!r} and no reference image is selected: "
        "this run would just re-roll the same prompt. Change the prompt "
        "(put the fix in the prompt, not only in the description) or "
        "select a reference image to edit from.")


# --- Multi-turn sessions (emulated provider continuity) ---
#
# SPIKE NOTE (2026-10-28): the OpenAI-compatible images API used by
# ``scripts/gen-image`` (``client.images.generate`` / ``client.images.edit``,
# plus the hand-rolled ``edit_images_indexed`` POST to ``/images/edits``)
# exposes no session/conversation/continuation parameter, and
# ``scripts/gen-image`` accepts no ``--session-id`` flag. So there is no
# provider session to plumb: continuity is emulated by auto-carrying ordered
# ``-i`` references from prior turns of the same session. Turn records keep
# a ``provider_session`` field (always None on this branch) so a future
# provider session id can slot in without changing the UI or publish path.

SESSION_ID_RE = NAME_RE
UPLOAD_MAX_BYTES = 8 * 1024 * 1024
UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SESSION_CONTEXT_MAX = 10


def _normalize_turn(entry: object) -> dict:
    if not isinstance(entry, dict):
        raise StoreError("each turn must be a mapping")
    try:
        seq = int(entry.get("seq", 0))
    except (TypeError, ValueError):
        raise StoreError("each turn must have an integer seq")
    if seq <= 0:
        raise StoreError("each turn must have a positive integer seq")
    return {
        "seq": seq,
        "prompt": entry.get("prompt") or "",
        "full_prompt_sent": entry.get("full_prompt_sent") or "",
        "references": validate_references(entry.get("references")),
        "num": entry.get("num"),
        "provider_session": entry.get("provider_session"),
        "status": entry.get("status"),
        "cost_total": entry.get("cost_total"),
        "outputs": [_normalize_output(o) for o in (entry.get("outputs") or [])],
    }


def _normalize_session(sid: str, raw: object) -> dict:
    if not isinstance(raw, dict):
        raise StoreError(f"session {sid!r} must be a mapping")
    return {
        "id": sid,
        "asset_name": raw.get("asset_name") or "",
        "title": raw.get("title") or "",
        "created": raw.get("created") or "",
        "turns": [_normalize_turn(t) for t in (raw.get("turns") or [])],
    }


def load_sessions(path: Path = SESSIONS_PATH) -> tuple[dict, str]:
    """Return (sessions, header) keyed by session id."""
    data, header = _load_yaml(path)
    raw = data.get("sessions") or {}
    if not isinstance(raw, dict):
        raise StoreError("sessions file 'sessions' must be a mapping")
    sessions = {}
    for sid, entry in raw.items():
        if not isinstance(sid, str) or not SESSION_ID_RE.match(sid):
            raise StoreError(f"invalid session id: {sid!r}")
        sessions[sid] = _normalize_session(sid, entry)
    return sessions, header


def save_sessions(sessions: dict, header: str, path: Path = SESSIONS_PATH) -> None:
    _save_yaml(path, {"sessions": sessions}, header)


def create_session(sessions: dict, sid: str, asset_name: str,
                   title: str = "", created: str = "") -> dict:
    """Create an empty session. Raises StoreError on bad/duplicate id."""
    _check_name("session", sid)
    if sid in sessions:
        raise StoreError(f"session {sid!r} already exists")
    if not (asset_name or "").strip():
        raise StoreError("session needs an asset name")
    session = {
        "id": sid,
        "asset_name": asset_name.strip(),
        "title": title or "",
        "created": created or "",
        "turns": [],
    }
    sessions[sid] = session
    return session


def get_session(sessions: dict, sid: str) -> dict:
    try:
        return sessions[sid]
    except KeyError:
        raise StoreError(f"session {sid!r} does not exist")


def add_turn(sessions: dict, sid: str, prompt: str,
             references: object, num: int) -> dict:
    """Append a pending turn to a session; caller fills outputs on completion."""
    session = get_session(sessions, sid)
    if not (prompt or "").strip():
        raise StoreError("turn prompt must not be empty")
    cleaned_refs = validate_references(references)
    turn = {
        "seq": len(session["turns"]) + 1,
        "prompt": prompt,
        "full_prompt_sent": "",
        "references": cleaned_refs,
        "num": num,
        "provider_session": None,
        "status": None,
        "cost_total": None,
        "outputs": [],
    }
    session["turns"].append(turn)
    return turn


def record_turn_outputs(sessions: dict, sid: str, seq: int,
                        outputs_info: list, total_usd: object,
                        full_prompt_sent: str = "") -> dict:
    """Attach completed outputs to a pending turn; marks it completed."""
    session = get_session(sessions, sid)
    turn = next((t for t in session["turns"] if t["seq"] == seq), None)
    if turn is None:
        raise StoreError(f"turn {seq!r} does not exist in session {sid!r}")
    for info in outputs_info:
        turn["outputs"].append({
            "key": info["key"],
            "path": info["path"],
            "estimated_usd": info.get("estimated_usd"),
            "original_path": info.get("original_path"),
            "requested_width": info.get("requested_width"),
            "requested_height": info.get("requested_height"),
            "raw_width": info.get("raw_width"),
            "raw_height": info.get("raw_height"),
        })
    turn["status"] = "completed"
    turn["cost_total"] = total_usd
    if full_prompt_sent:
        turn["full_prompt_sent"] = full_prompt_sent
    return turn


def mark_turn_failed(sessions: dict, sid: str, seq: int) -> None:
    session = get_session(sessions, sid)
    turn = next((t for t in session["turns"] if t["seq"] == seq), None)
    if turn is None:
        raise StoreError(f"turn {seq!r} does not exist in session {sid!r}")
    turn["status"] = "failed"


def session_output_keys(session: dict) -> list:
    """All output keys in a session, oldest turn first."""
    keys = []
    for turn in session.get("turns") or []:
        for output in turn.get("outputs") or []:
            keys.append(output["key"])
    return keys


def find_session_output(sessions: dict, sid: str, output_key: str) -> dict:
    """Return the output record for a key in a session; raises StoreError."""
    session = get_session(sessions, sid)
    for turn in session.get("turns") or []:
        for output in turn.get("outputs") or []:
            if output.get("key") == output_key:
                return output
    raise StoreError(f"output {output_key!r} not found in session {sid!r}")


def session_context_refs(session: dict, judgements: dict | None = None,
                         limit: int = SESSION_CONTEXT_MAX) -> list:
    """Auto-carry context for the next turn: preferred first, newest first.

    Collects output filenames (``<key>.png``) from all completed turns,
    newest turn first; outputs marked preferred in ``judgements`` sort ahead
    of the rest within that newest-first order. Dedupes and caps at
    ``limit`` (default 10, matching the reference cap).
    """
    judgements = judgements or {}
    ordered: list = []
    for turn in reversed(session.get("turns") or []):
        for output in reversed(turn.get("outputs") or []):
            ordered.append(output["key"])
    preferred = [k for k in ordered if (judgements.get(k) or {}).get("preferred")]
    rest = [k for k in ordered if k not in preferred]
    keys = (preferred + rest)[:limit]
    return [k + ".png" for k in keys]


def publish_slug(sid: str, seq: int) -> str:
    """Derive a manifest-safe version slug for a published turn output."""
    slug = f"{sid}-t{seq}".strip()
    if not SESSION_ID_RE.match(slug):
        slug = "s-" + re.sub(r"[^A-Za-z0-9_-]", "-", slug).strip("-") or "s-published"
    return slug


def validate_upload(filename: object, size: int) -> str:
    """Validate an upload's name and byte size; return the cleaned basename."""
    if not isinstance(filename, str) or not filename.strip():
        raise StoreError("upload needs a filename")
    base = Path(filename.strip()).name
    if not base or base in (".", ".."):
        raise StoreError(f"invalid upload filename: {filename!r}")
    if "." not in base or Path(base).suffix.lower() not in UPLOAD_EXTENSIONS:
        raise StoreError(
            f"upload {base!r} must be one of: {', '.join(sorted(UPLOAD_EXTENSIONS))}")
    if not isinstance(size, int) or size <= 0:
        raise StoreError("upload is empty")
    if size > UPLOAD_MAX_BYTES:
        raise StoreError(
            f"upload is {size} bytes; the limit is {UPLOAD_MAX_BYTES} bytes")
    return base
