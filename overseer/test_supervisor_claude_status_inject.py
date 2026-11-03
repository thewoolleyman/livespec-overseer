"""Registry-backed Claude status injection for the `supervisor` beside-tests.

Evaluation re-reads the one registry file discovery joined, so a test that wants a
session to self-report a status must put that status in a registry file and a join
in `claude_identity_by_session`. No tests live here; the `test_` prefix is load-bearing
for the same reason as in `test_supervisor_fakes`.
"""

import json
from pathlib import Path

__all__: list[str] = ["INJECTED_NAME", "inject_claude_status"]

_PID_BASE = 900_000
_PROC_START = "inject"
INJECTED_NAME = "injected"


def inject_claude_status(*, sup, statuses: dict[str, str], merge: bool = False) -> None:
    """Make each ``session`` self-report its status via a real registry file plus join."""
    directory = (
        Path(sup.sessions_dir)
        if sup.sessions_dir is not None
        else Path(sup.stamp_path).parent / "injected-claude-sessions"
    )
    statuses = {**sup.claude_status_by_session, **statuses} if merge else statuses
    directory.mkdir(parents=True, exist_ok=True)
    sup.sessions_dir = directory
    injected = getattr(sup, "_injected_claude_pids", {})
    for session, pid in injected.items():
        (directory / f"{pid}.json").unlink(missing_ok=True)
        sup.claude_identity_by_session.pop((session, INJECTED_NAME), None)
    injected = {session: _PID_BASE + index for index, session in enumerate(statuses)}
    sup._injected_claude_pids = injected
    previous = getattr(sup, "_injected_starttime_of", sup.starttime_of)
    sup._injected_starttime_of = previous
    live = set(injected.values())

    def starttime_of(*, pid):
        return _PROC_START if pid in live else previous(pid=pid)

    sup.starttime_of = starttime_of
    for session, status in statuses.items():
        pid = injected[session]
        payload = {
            "pid": pid,
            "name": INJECTED_NAME,
            "cwd": "/r",
            "procStart": _PROC_START,
            "status": status,
        }
        (directory / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")
        sup.claude_identity_by_session[(session, INJECTED_NAME)] = (
            f"claude:{pid}:{_PROC_START}:{INJECTED_NAME}"
        )
    sup.claude_status_by_session = dict(statuses)
