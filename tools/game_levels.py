"""Level listing for the game menu: regular levels and Test Levels.

Levels are the existing levels/*.json files (rows + legend). A level
is a Test Level when its JSON sets "test": true or its id starts
with "test-". The game menu launches both kinds from inside the game.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class LevelError(ValueError):
    """Raised for invalid level ids or malformed level files."""


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LevelError(f"cannot read level {path.name}: {exc}")
    if not isinstance(data, dict) or not data.get("rows") \
            or not isinstance(data.get("legend"), dict):
        raise LevelError(f"level {path.name} needs rows + legend")
    return data


def list_levels(root: Path) -> list[dict]:
    out = []
    for path in sorted(Path(root).glob("*.json")):
        lid = path.stem
        if not SLUG_RE.match(lid):
            continue
        data = _load(path)
        out.append({
            "id": lid,
            "name": data.get("name") or lid,
            "test": bool(data.get("test")) or lid.startswith("test-"),
        })
    return out


def load_level(root: Path, level_id: str) -> dict:
    if not isinstance(level_id, str) or not SLUG_RE.match(level_id):
        raise LevelError(f"invalid level id {level_id!r}")
    path = Path(root) / f"{level_id}.json"
    if not path.is_file():
        raise LevelError(f"level {level_id!r} does not exist")
    return _load(path)
