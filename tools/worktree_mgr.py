"""Discover git worktrees and tools/server.py processes; stop servers.

Used by the /worktrees page in tools/server.py. Scope is deliberately
narrow (per user choice): view + open + stop servers only. This module
never removes worktrees, branches, or files.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path


def _labels_path(root: Path) -> Path:
    return Path(root) / ".worktrees" / "labels.json"


def load_labels(root: Path) -> dict:
    try:
        data = json.loads(_labels_path(root).read_text())
        return {"worktrees": dict(data.get("worktrees") or {}),
                "servers": dict(data.get("servers") or {})}
    except (OSError, ValueError):
        return {"worktrees": {}, "servers": {}}


def set_label(root: Path, kind: str, key: str, label: str) -> dict:
    if kind not in ("worktrees", "servers") or not key:
        raise ValueError("kind must be 'worktrees' or 'servers', with a key")
    labels = load_labels(root)
    label = (label or "").strip()[:80]
    if label:
        labels[kind][key] = label
    else:
        labels[kind].pop(key, None)
    path = _labels_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(labels, indent=1))
    tmp.replace(path)
    return labels


def _feature_titles(root: Path) -> dict[str, str]:
    titles = {}
    feat_dir = Path(root) / "plans" / "simple-game-engine" / "features"
    try:
        files = list(feat_dir.glob("*.md"))
    except OSError:
        return titles
    for f in files:
        try:
            head = f.read_text(errors="replace")[:2000]
        except OSError:
            continue
        m = re.search(r"^title:\s*(.+)$", head, re.M)
        if m:
            titles[f.stem] = m.group(1).strip()
    return titles


def _boot_time() -> float | None:
    try:
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("btime "):
                return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _started_iso(ticks: int | None, boot: float | None) -> str | None:
    if ticks is None or boot is None:
        return None
    try:
        hz = os.sysconf("SC_CLK_TCK")
        return datetime.datetime.fromtimestamp(
            boot + ticks / hz, datetime.timezone.utc).astimezone().isoformat(timespec="seconds")
    except (OSError, ValueError, OverflowError):
        return None


def list_worktrees(root: Path) -> list[dict]:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return []
    except (OSError, subprocess.TimeoutExpired):
        return []
    worktrees: list[dict] = []
    cur: dict = {}
    def flush():
        if cur.get("path"):
            worktrees.append(dict(cur))
    for line in out.stdout.splitlines():
        if not line.strip():
            flush(); cur = {}; continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur = {"path": val, "branch": None, "head": None,
                   "detached": False, "bare": False, "locked": False,
                   "prunable": False}
        elif key == "HEAD":
            cur["head"] = val[:9]
        elif key == "branch":
            cur["branch"] = val.removeprefix("refs/heads/")
        elif key in ("detached", "bare", "locked", "prunable"):
            cur[key] = True
    flush()
    titles = _feature_titles(root)
    for wt in worktrees:
        p = Path(wt["path"])
        wt["exists"] = p.is_dir()
        wt["is_main"] = p.resolve() == Path(root).resolve() if wt["exists"] else False
        wt["name"] = p.name or wt["path"]
        # A worktree dir or branch named after a PM feature inherits its title.
        wt["feature"] = None
        for cand in (wt["name"], wt.get("branch") or ""):
            if cand in titles:
                wt["feature"] = {"id": cand, "title": titles[cand]}
                break
        wt["dirty"] = None
        wt["changed_files"] = []
        wt["last_commit"] = None
        if wt["exists"]:
            try:
                s = subprocess.run(["git", "-C", wt["path"], "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=10)
                if s.returncode == 0:
                    lines = [l for l in s.stdout.splitlines() if l.strip()]
                    wt["dirty"] = len(lines)
                    wt["changed_files"] = [l[3:] for l in lines[:6]]
            except (OSError, subprocess.TimeoutExpired):
                pass
            try:
                log = subprocess.run(
                    ["git", "-C", wt["path"], "log", "-1", "--format=%s%x1f%cI"],
                    capture_output=True, text=True, timeout=10)
                if log.returncode == 0 and "\x1f" in log.stdout:
                    subj, date = log.stdout.strip().split("\x1f", 1)
                    wt["last_commit"] = {"subject": subj, "date": date}
            except (OSError, subprocess.TimeoutExpired):
                pass
    return worktrees


def _parse_port(args: list[str]) -> int:
    if "--port" in args:
        i = args.index("--port")
        if i + 1 < len(args):
            try:
                return int(args[i + 1])
            except ValueError:
                pass
    return 8321


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def list_servers() -> list[dict]:
    servers = []
    proc = Path("/proc")
    if not proc.is_dir():
        return servers
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        args = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
        if not any(a.endswith("tools/server.py") or a == "tools/server.py" for a in args):
            continue
        try:
            cwd_raw = os.readlink(entry / "cwd")
        except OSError:
            cwd_raw = ""
        cwd_deleted = cwd_raw.endswith(" (deleted)")
        cwd = cwd_raw.removesuffix(" (deleted)")
        port = _parse_port(args)
        try:
            started = int((entry / "stat").read_text().split()[21])
        except (OSError, IndexError, ValueError):
            started = None
        servers.append({
            "pid": pid, "port": port, "args": args,
            "cmdline": " ".join(args), "cwd": cwd,
            "cwd_deleted": cwd_deleted, "cwd_exists": Path(cwd).is_dir() if cwd else False,
            "listening": _listening(port),
            "url": f"http://127.0.0.1:{port}/",
            "_started_ticks": started,
        })
    servers.sort(key=lambda s: (s["port"], s["pid"]))
    return servers


def collect(root: Path, self_pid: int, self_port: int) -> dict:
    labels = load_labels(root)
    worktrees = list_worktrees(root)
    servers = list_servers()
    boot = _boot_time()
    wt_by_path = {w["path"]: w for w in worktrees}
    for w in worktrees:
        w["label"] = labels["worktrees"].get(w["path"], "")
    for s in servers:
        s["started_at"] = _started_iso(s.pop("_started_ticks", None), boot)
        # Code on disk in its cwd changed after it started => it serves old code.
        s["code_stale"] = False
        if s["started_at"] and s["cwd"] and not s["cwd_deleted"]:
            try:
                mtime = (Path(s["cwd"]) / "tools" / "server.py").stat().st_mtime
                started_ts = datetime.datetime.fromisoformat(s["started_at"]).timestamp()
                s["code_stale"] = mtime > started_ts
            except OSError:
                pass
        s["is_self"] = s["pid"] == self_pid
        s["worktree"] = None
        if s["cwd"]:
            try:
                cwd_r = str(Path(s["cwd"]).resolve())
            except OSError:
                cwd_r = s["cwd"]
            # longest matching worktree prefix
            matches = [w for w in worktrees if cwd_r == str(Path(w["path"]).resolve())
                       or cwd_r.startswith(str(Path(w["path"]).resolve()) + os.sep)]
            if matches:
                s["worktree"] = max(matches, key=lambda w: len(w["path"]))["path"]
        s["stale"] = bool(s["cwd_deleted"] or (s["cwd"] and not s["cwd_exists"])
                         or (s["cwd"] and not s["worktree"]))
        wt = wt_by_path.get(s["worktree"] or "")
        s["worktree_name"] = wt["name"] if wt else (Path(s["cwd"]).name if s["cwd"] else None)
        s["label"] = labels["servers"].get(f"{s['cwd']}|{s['port']}", "")
        # Human name: your label, else the feature title, else the worktree/branch name.
        s["purpose"] = (wt["feature"]["title"] if wt and wt.get("feature") else None)
    by_wt: dict[str, list] = {}
    for s in servers:
        if s["worktree"]:
            by_wt.setdefault(s["worktree"], []).append(
                {k: s[k] for k in ("pid", "port", "url", "listening", "is_self", "stale")})
    for w in worktrees:
        w["servers"] = by_wt.get(w["path"], [])
    # Folders under .worktrees/ that git no longer knows: leftover, not a worktree.
    known = {Path(w["path"]).name for w in worktrees}
    leftovers = []
    wt_dir = Path(root) / ".worktrees"
    if wt_dir.is_dir():
        for child in sorted(wt_dir.iterdir()):
            if child.is_dir() and child.name not in known:
                leftovers.append({"name": child.name, "path": str(child),
                                    "feature": ({"id": child.name, "title": _feature_titles(root)[child.name]}
                                                if child.name in _feature_titles(root) else None)})
    return {"worktrees": worktrees, "servers": servers, "leftovers": leftovers,
            "self": {"pid": self_pid, "port": self_port,
                     "url": f"http://127.0.0.1:{self_port}/"}}


def _is_server_pid(pid: int) -> list[str] | None:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    args = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
    if any(a.endswith("tools/server.py") or a == "tools/server.py" for a in args):
        return args
    return None


def stop_server(pid: int, self_pid: int) -> dict:
    """SIGTERM a tools/server.py process, escalating to SIGKILL. Refuses self
    and any PID whose cmdline is not tools/server.py (re-checked at kill time)."""
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("pid must be a positive integer")
    if pid == self_pid:
        raise ValueError("refusing to stop this server from itself; stop it from another worktree's page or the terminal")
    if _is_server_pid(pid) is None:
        raise ValueError(f"pid {pid} is not a running tools/server.py process")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"pid": pid, "stopped": True, "signal": "already-exited"}
    for _ in range(20):
        if _is_server_pid(pid) is None:
            return {"pid": pid, "stopped": True, "signal": "SIGTERM"}
        time.sleep(0.1)
    if _is_server_pid(pid) is not None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(0.1)
    return {"pid": pid, "stopped": _is_server_pid(pid) is None, "signal": "SIGKILL"}
