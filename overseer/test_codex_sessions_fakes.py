"""Shared fakes for the `codex_sessions` beside-tests.

Extracted so `test_codex_sessions.py` (the pid->rollout->thread-name join, the index
reader, reboot recovery, the rollout-id parse) and `test_codex_sessions_mapping.py`
(the `map_codex_sessions` / `codex_by_tmux_session` adoption twin and the /proc
primitives) share ONE fake host and ONE fake `~/.codex` instead of one importing the
other's privates. Neither half breaches a ceiling alone; their combined module did,
which is what forced the split.

The `fake_` prefix is load-bearing, not decoration: several tests bind a LOCAL named
`host`, so exporting these as a bare `host` would be shadowed at the call site and
raise `UnboundLocalError`. The suite caught that during the split.

No tests live here. The `test_` prefix is deliberate: coverage omits
`overseer/test_*.py`, so a differently-named helper in this package would be measured
as product code and demand 100% coverage of a test double.
"""

import codex_sessions

__all__: list[str] = ["ID_A", "ID_B", "fake_host", "fake_index", "fake_rollout"]

# --------------------------------------------------------------------------- #
# Helpers: a fake host (pids, comms, cwds, open fds) + a fake ~/.codex.
# --------------------------------------------------------------------------- #


def fake_index(*, tmp_path, records):
    """Write a `session_index.jsonl` with `records` (id, thread_name) pairs, in order."""
    home = tmp_path / "codex"
    home.mkdir(exist_ok=True)
    lines = [
        f'{{"id": "{i}", "thread_name": "{n}", "updated_at": "2026-07-16T08:00:00Z"}}'
        for i, n in records
    ]
    (home / "session_index.jsonl").write_text("\n".join(lines) + "\n")
    return home


def fake_rollout(*, session_id):
    """A rollout path of the real shape — the id is embedded in the FILENAME."""
    return f"/home/u/.codex/sessions/2026/07/16/rollout-2026-07-16T10-49-49-{session_id}.jsonl"


ID_A = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
ID_B = "019f548d-6071-7893-9c2e-472cce81da02"


def fake_host(
    *, comms=None, cwds=None, fds=None, children=None, environs=None, foreground_pgrps=None
):
    """Injected host readers: pid→comm, cwd, fds, children, environ, and foreground group.

    `children` defaults to a childless host, which is both what every pre-0.150 shape
    looked like and what keeps the walk over a session's helper processes hermetic:
    without it that walk would fall back to the REAL `/proc` children reader for the
    fake pids these tests invent.

    `environs` defaults to unreadable environments for the SAME reason, and it was
    missing rather than deliberately omitted. Every reader that scopes a carrier to a
    Codex home consults `environ_of`, so without it the scope test fell back to the
    REAL `/proc/<pid>/environ` for pids these tests invent — and on a host where such a
    pid HAPPENS to exist, that carrier resolved to the host's own Codex home, compared
    unequal to the declared fake one, and was dropped from the mapping. Measured in a
    factory sandbox where `/proc/10` is a live `sleep` and `/proc/20` does not exist:
    four of these tests failed, each losing exactly pid 10 while pid 20 — whose
    unreadable environ already fell back to the declared home — survived.

    An unreadable environ is the right default rather than a convenient one: the scope
    test falls back to the home the caller DECLARED, which is what every fake here
    intends its pids to be carriers of.
    """
    comms, cwds, fds, children = comms or {}, cwds or {}, fds or {}, children or {}
    environs = environs or {}
    if foreground_pgrps is None:
        descendants = {child for nested in children.values() for child in nested}
        foreground_pgrps = {
            pid: pid for pid, comm in comms.items() if comm == "codex" and pid not in descendants
        }
    return {
        "readers": codex_sessions.CodexHostReaders(
            pids_of_comm=lambda *, comm: sorted(p for p, c in comms.items() if c == comm),
            cwd_of=lambda *, pid: cwds.get(pid),
            fd_targets_of=lambda *, pid: fds.get(pid, []),
            children_of=lambda *, pid: list(children.get(pid, [])),
            environ_of=lambda *, pid: environs.get(pid),
            foreground_pgrp_of=lambda *, pid: foreground_pgrps.get(pid),
        )
    }
