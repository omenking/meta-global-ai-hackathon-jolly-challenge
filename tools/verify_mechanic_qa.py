"""Q&A gate for mechanic sanity-check features (plans/qa-framework/PLAN.md).

Given a feature id, verify the evidence a reviewer will rely on:
linked agent play sessions exist (success ending ``won``, a labelled
naive-failure session, edge coverage), each replayed session reaches
the recorded end state deterministically through GameCore, annotated
``expect`` assertions hold, and the teaching room is not winnable
with an empty input log. Exit 0 only when every hard check passes.

Run: python3 tools/verify_mechanic_qa.py <feature-id>
     [--code-root <checkout-with-the-feature-code>]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import game_levels  # noqa: E402
import game_sessions  # noqa: E402
import pm_store  # noqa: E402

NODE_SCRIPT = r"""
const fs = require('fs');
const core = require(process.argv[1]);
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const level = JSON.parse(fs.readFileSync(payload.level_path, 'utf8'));
function levelHash(lv) {
  const text = JSON.stringify(lv); let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return ('0000000' + h.toString(16)).slice(-8);
}
const out = { level_hash: levelHash(level), engine_version: core.VERSION,
  empty_status: null, sessions: {} };
const empty = core.replay(level, payload.level_id, []);
out.empty_status = core.readout(empty[empty.length - 1]).status;
for (const s of payload.sessions) {
  const log = s.records.filter(r => r.type === 'step')
    .map(r => ({ t_ms: r.t_ms, input: r.input }));
  const a = core.replay(level, payload.level_id, log);
  const b = core.replay(level, payload.level_id, log);
  out.sessions[s.id] = {
    digest: core.stateDigest(a[a.length - 1]),
    digest2: core.stateDigest(b[b.length - 1]),
    readouts: a.map(st => core.readout(st)),
  };
}
console.log(JSON.stringify(out));
"""


def _labels(records) -> list:
    return game_sessions.labels_of(records)


def verify(feature_id: str, code_root: Path, pm_path: Path,
           sessions_roots: list[Path]) -> dict:
    checks = []  # {name, ok, detail, warning}

    def check(name, ok, detail="", warning=False):
        checks.append({"name": name, "ok": bool(ok),
                       "detail": detail, "warning": warning})

    data, _ = pm_store.load_pm(pm_path)
    feature = pm_store.find_feature(data, feature_id)
    if feature is None:
        check("feature_exists", False, f"no feature {feature_id!r} in {pm_path}")
        return {"feature": feature_id, "checks": checks, "sessions": {}}
    check("feature_exists", True, feature.get("title", ""))
    test_level = feature.get("test_level")
    check("test_level_set", bool(test_level), str(test_level))

    level = None
    if test_level:
        try:
            level = game_levels.load_level(code_root / "levels", test_level)
            check("level_loads", True, f"{code_root}/levels/{test_level}.json")
        except Exception as exc:  # LevelError / OSError
            check("level_loads", False, str(exc))

    refs = feature.get("sessions") or []
    check("sessions_linked", len(refs) > 0,
          f"{len(refs)} session(s) linked on the feature")

    # Screenshot evidence anywhere on the feature's comments.
    shots = [a for c in feature.get("comments", [])
             for a in (c.get("attachments") or [])]
    for t in feature.get("tasks", []):
        shots += [a for c in t.get("comments", [])
                  for a in (c.get("attachments") or [])]
    check("screenshot_evidence", len(shots) > 0, f"{len(shots)} attachment(s)")

    # Rule -> evidence table in a sanity-check / qa-verification comment.
    table = False
    for t in feature.get("tasks", []):
        if t["id"] in ("sanity-check", "qa-verification") or \
                t.get("kind") == "qa":
            for c in t.get("comments", []):
                body = (c.get("body") or "").lower()
                if "rule" in body and "evidence" in body and \
                        ("->" in body or "→" in body):
                    table = True
    check("rule_evidence_table", table,
          "sanity/qa task comment must carry a rule -> evidence table")

    sessions = {}
    payload_sessions = []
    for ref in refs:
        sid = ref.get("id", "")
        records, found = None, None
        for sroot in sessions_roots:
            try:
                records = game_sessions.read_session_any(sroot, sid)
                found = sroot
                break
            except Exception:
                continue
        if records is None:
            check(f"session:{sid}:readable", False,
                  f"not found under {[str(r) for r in sessions_roots]}")
            continue
        check(f"session:{sid}:readable", True, str(found))
        sessions[sid] = records
        payload_sessions.append({"id": sid, "records": records})
        header = records[0]
        end = next((r for r in reversed(records) if r.get("type") == "end"), {})
        check(f"session:{sid}:created_by_agent",
              header.get("created_by") == "agent",
              f"created_by={header.get('created_by')!r}")
        check(f"session:{sid}:feature_link",
              header.get("feature") == feature_id,
              f"feature={header.get('feature')!r}")
        check(f"session:{sid}:level_link",
              header.get("level") == test_level,
              f"level={header.get('level')!r} test_level={test_level!r}")
        check(f"session:{sid}:engine_version",
              bool(header.get("engine_version")),
              f"engine_version={header.get('engine_version')!r}")
        check(f"session:{sid}:level_hash",
              bool((header.get("level_source") or {}).get("hash")),
              "level_source.hash present" if
              (header.get("level_source") or {}).get("hash") else "missing")
        check(f"session:{sid}:branch_commit_link",
              bool(header.get("branch")) and bool(header.get("commit")),
              f"branch={header.get('branch')!r} commit={header.get('commit')!r}",
              warning=True)
        check(f"session:{sid}:has_end", bool(end), f"result={end.get('result')!r}")

    # Classification: success / naive-failure / edge coverage.
    def is_agent(records):
        return records and records[0].get("created_by") == "agent"

    def end_result(records):
        end = next((r for r in reversed(records) if r.get("type") == "end"), {})
        return end.get("result")

    agent_sessions = {k: v for k, v in sessions.items() if is_agent(v)}
    won = [k for k, v in agent_sessions.items() if end_result(v) == "won"]
    check("agent_success_session_won", len(won) > 0,
          f"won agent sessions: {won or 'none'}")
    naive = [k for k, v in agent_sessions.items()
             if "naive" in _labels(v) and end_result(v) != "won"]
    check("agent_naive_failure_session", len(naive) > 0,
          f"naive-labelled non-won agent sessions: {naive or 'none'}")
    edge = [k for k, v in agent_sessions.items()
            if "edge" in _labels(v) or
            any("edge" in (a.get("labels") or [])
                for a in v if a.get("type") == "annotation")]
    check("agent_edge_coverage", len(edge) > 0,
          f"edge-labelled agent sessions: {edge or 'none'}")

    # Replay through GameCore (Node), when we have a level + sessions.
    replay_info = {}
    if level is not None and test_level:
        payload = {"level_path": str(code_root / "levels" / f"{test_level}.json"),
                   "level_id": test_level, "sessions": payload_sessions}
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as fh:
            json.dump(payload, fh)
            payload_path = fh.name
        try:
            out = subprocess.run(
                ["node", "-e", NODE_SCRIPT,
                 str(code_root / "tools" / "static" / "game-core.js"),
                 payload_path],
                capture_output=True, text=True, check=True)
            replay_info = json.loads(out.stdout.strip().splitlines()[-1])
        except Exception as exc:
            check("node_replay_runs", False, str(exc)[:400])
        finally:
            Path(payload_path).unlink(missing_ok=True)
    if replay_info:
        check("node_replay_runs", True,
              f"engine={replay_info.get('engine_version')}")
        check("empty_log_does_not_win",
              replay_info.get("empty_status") != "won",
              f"empty-log status={replay_info.get('empty_status')!r}")
        for sid, records in sessions.items():
            info = replay_info.get("sessions", {}).get(sid)
            if not info:
                continue
            steps = [r for r in records if r.get("type") == "step"]
            end = next((r for r in reversed(records)
                        if r.get("type") == "end"), {})
            final = info["readouts"][-1] if info["readouts"] else {}
            check(f"session:{sid}:deterministic_replay",
                  info["digest"] == info["digest2"],
                  f"digest={info['digest']} re-replay={info['digest2']}")
            check(f"session:{sid}:step_count_matches",
                  end.get("steps") in (None, len(steps)),
                  f"end.steps={end.get('steps')} recorded={len(steps)}")
            result = end.get("result")
            status_ok = (result == "won" and final.get("status") == "won") or \
                (result == "lost" and final.get("status") == "lost") or \
                (result in ("quit", None) and
                 final.get("status") in ("playing", "lost", "won"))
            check(f"session:{sid}:end_state_matches",
                  status_ok,
                  f"recorded result={result!r} replay status={final.get('status')!r}")
            if end.get("orbs_left") is not None:
                check(f"session:{sid}:orbs_left_matches",
                      end.get("orbs_left") == final.get("orbs_left"),
                      f"recorded={end.get('orbs_left')} replay={final.get('orbs_left')}")
            header = records[0]
            recorded_hash = (header.get("level_source") or {}).get("hash")
            check(f"session:{sid}:level_hash_matches",
                  not recorded_hash or
                  recorded_hash == replay_info.get("level_hash"),
                  f"recorded={recorded_hash} current={replay_info.get('level_hash')}",
                  warning=not recorded_hash)
            for ann in records:
                if ann.get("type") != "annotation" or not ann.get("expect"):
                    continue
                step = ann.get("step") or 0
                idx = max(0, min(step, len(info["readouts"]) - 1))
                actual = info["readouts"][idx]
                for key, want in ann["expect"].items():
                    got = actual.get(key)
                    if key == "position" and isinstance(want, dict):
                        got = actual.get("position")
                    check(f"session:{sid}:expect@{step}:{key}",
                          got == want, f"want={want!r} got={got!r}")
    return {"feature": feature_id, "checks": checks,
            "sessions": {k: game_sessions.summarize(v) for k, v in sessions.items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("feature_id")
    ap.add_argument("--code-root", type=Path, default=ROOT,
                    help="checkout holding the feature code/levels "
                         "(default: this repo; use the feature worktree "
                         "for unmerged mechanics)")
    ap.add_argument("--pm", type=Path, default=pm_store.PM_PATH)
    ap.add_argument("--sessions-root", type=Path, action="append",
                    help="extra sessions root (repeatable)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    args.code_root = args.code_root.resolve()
    roots = [ROOT / "sessions", args.code_root / "sessions"]
    for extra in args.sessions_root or []:
        roots.append(extra)
    report = verify(args.feature_id, args.code_root, args.pm, roots)
    hard = [c for c in report["checks"] if not c["warning"]]
    failed = [c for c in hard if not c["ok"]]
    warnings = [c for c in report["checks"] if c["warning"] and not c["ok"]]
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Q&A verification: {args.feature_id}")
        for c in report["checks"]:
            mark = "WARN" if (c["warning"] and not c["ok"]) else \
                ("PASS" if c["ok"] else "FAIL")
            print(f"  [{mark}] {c['name']}: {c['detail']}")
        print(f"Result: {'PASS' if not failed else 'FAIL'} "
              f"({len(hard) - len(failed)}/{len(hard)} hard checks passed, "
              f"{len(warnings)} warning(s))")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
