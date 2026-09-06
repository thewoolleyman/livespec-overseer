#!/usr/bin/env python3
"""drain-backlog tick reader: what changed since the last tick, from the authoritative sources.

    tick.py --repo <path> [--server <fabro-url>] [--since <ISO>]   # one tick
    tick.py --repo <path> --follow                                 # Monitor watcher

Reads: the dispatch journal's outcome events since the last tick (tolerant of the
dispatcher rewriting the file), the ledger's active claims vs wip_cap, live runs on the
factory server, and open PRs whose checks are red. Prints a tick report by id. Writes
nothing to the ledger. Run under the credential wrapper so `bd` reaches the tenant.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

Record = dict[str, Any]

OUTCOME_RE = re.compile(
    r'"stage": ?"outcome"|dispatch-claim-abandoned|provider-exhaustion|'
    r'"status": ?"(refused|failed|blocked|capacity-deferred)"'
)
POLL_SECONDS = 60
DETAIL_WIDTH = 200
ROW_WIDTH = 150
TITLE_WIDTH = 70
PS_TIMEOUT = 90
EPOCH = "1970-01-01T00:00:00Z"
PR_FIELDS = "number,title,mergeStateStatus,autoMergeRequest,statusCheckRollup,headRefName"


def out(text: str) -> None:
    _ = sys.stdout.write(text + "\n")
    sys.stdout.flush()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(args: list[str], cwd: Path, timeout: int = 60) -> str:
    """Run an argv list (no shell) and return stdout, or "" when it fails or times out."""
    try:
        done = subprocess.run(  # noqa: S603
            args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return done.stdout


def load_records(text: str) -> list[Record]:
    parsed: Any = json.loads(text or "[]")
    return [r for r in parsed if isinstance(r, dict)] if isinstance(parsed, list) else []


def outcome_line(d: Record) -> str:
    raw_outcome: Any = d.get("outcome")
    o: Record = raw_outcome if isinstance(raw_outcome, dict) else {}
    wi = str(o.get("work_item_id") or d.get("work_item_id") or "")
    ev = "OUTCOME" if o else str(d.get("event") or "event")
    detail = str(o.get("detail") or d.get("detail") or "").replace("\n", " ")
    fail = " / ".join(
        x.strip()
        for x in str(o.get("detail") or "").splitlines()
        if x.strip().startswith("✗") or "Error:" in x or "Failure:" in x
    )
    at = str(d.get("at") or "")[11:19]
    stage = o.get("stage") or d.get("stage")
    state = o.get("status") or d.get("status")
    run_id = o.get("fabro_run_id") or ""
    return (
        f"{at} {ev} {wi} {stage} {state} pr={o.get('pr_number')} run={run_id} "
        f"| {(fail or detail)[:DETAIL_WIDTH]}"
    )


def parse_line(raw: str) -> Record | None:
    if not OUTCOME_RE.search(raw):
        return None
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def journal_since(journal: Path, since: str) -> list[str]:
    if not journal.exists():
        return []
    lines: list[str] = []
    for raw in journal.read_text(errors="replace").splitlines():
        d = parse_line(raw)
        if d is not None and str(d.get("at") or "") > since:
            lines.append(outcome_line(d))
    return lines


def follow(journal: Path) -> None:
    """Replay-safe watcher: print only NEW matching lines; resync when the file shrinks."""
    prev = len(journal.read_text(errors="replace").splitlines()) if journal.exists() else 0
    while True:
        time.sleep(POLL_SECONDS)
        if not journal.exists():
            continue
        text = journal.read_text(errors="replace").splitlines()
        cur = len(text)
        if cur < prev:
            out(f"journal rewritten ({prev} -> {cur} lines); resyncing")
            prev = cur
            continue
        for raw in text[prev:cur]:
            d = parse_line(raw)
            if d is not None:
                out(outcome_line(d))
        prev = cur


def report_claims(repo: Path) -> None:
    out("\n## ledger claims")
    active = load_records(run(["bd", "list", "--status", "active", "--json"], repo))
    cfg = repo / ".livespec.jsonc"
    cap = re.search(r'"wip_cap"\s*:\s*(\d+)', cfg.read_text()) if cfg.exists() else None
    names = ", ".join(str(i["id"]).split("-")[-1] for i in active)
    out(f"active claims: {len(active)} / wip_cap {cap.group(1) if cap else '?'} :: {names}")
    ready = load_records(run(["bd", "list", "--status", "ready", "--json"], repo))
    out(f"ready: {len(ready)}")


def report_runs(repo: Path, server: str | None) -> None:
    out("\n## live runs on the factory")
    if not server:
        out("(pass --server <url>; bare `fabro ps` queries the wrong server)")
        return
    ps = run(["fabro", "ps", "--server", server], repo, timeout=PS_TIMEOUT)
    if "RUN ID" not in ps:
        out("(fabro ps UNAVAILABLE: timed out or errored; an unseen run is an unmeasured run)")
        return
    rows = [line for line in ps.splitlines() if repo.name in line]
    out("\n".join(r[:ROW_WIDTH] for r in rows) if rows else "(none for this repo)")


def report_prs(repo: Path) -> None:
    out("\n## open PRs with red or pending checks")
    argv = ["gh", "pr", "list", "--state", "open", "--limit", "30", "--json", PR_FIELDS]
    try:
        prs = load_records(run(argv, repo))
    except json.JSONDecodeError:
        out("(gh pr list unavailable)")
        return
    for p in prs:
        raw_checks: Any = p.get("statusCheckRollup") or []
        checks: list[Record] = [c for c in raw_checks if isinstance(c, dict)]
        failed = [str(c.get("name")) for c in checks if c.get("conclusion") == "FAILURE"]
        pending = [
            c for c in checks if c.get("conclusion") is None and c.get("status") != "COMPLETED"
        ]
        if failed or pending or p.get("mergeStateStatus") in ("BLOCKED", "DIRTY"):
            out(
                f"PR {p['number']} {p.get('mergeStateStatus')} "
                f"auto={bool(p.get('autoMergeRequest'))} failed={','.join(failed) or '-'} "
                f"pending={len(pending)} :: {p['headRefName']} :: "
                f"{str(p['title'])[:TITLE_WIDTH]}"
            )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    _ = ap.add_argument("--repo", default=".")
    _ = ap.add_argument("--server", default=None, help="fabro server URL for `fabro ps`")
    _ = ap.add_argument("--since", default=None)
    _ = ap.add_argument("--follow", action="store_true")
    a = ap.parse_args()
    repo = Path(str(a.repo)).resolve()
    state = repo / "tmp" / "drain-backlog"
    state.mkdir(parents=True, exist_ok=True)
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    if a.follow:
        follow(journal)
        return 0

    marker = state / "last-tick"
    since = str(a.since or (marker.read_text().strip() if marker.exists() else EPOCH))
    out(f"# tick {now_iso()} (since {since})")
    out("\n## journal outcomes since last tick")
    lines = journal_since(journal, since)
    out("\n".join(lines) if lines else "(none)")
    report_claims(repo)
    report_runs(repo, a.server)
    report_prs(repo)
    _ = marker.write_text(now_iso() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
