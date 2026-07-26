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


def fake_host(*, comms=None, cwds=None, fds=None):
    """Injected host readers: pid→comm, pid→cwd, pid→open fd targets."""
    comms, cwds, fds = comms or {}, cwds or {}, fds or {}
    return {
        "pids_of_comm": lambda comm: sorted(p for p, c in comms.items() if c == comm),
        "cwd_of": cwds.get,
        "fd_targets_of": lambda pid: fds.get(pid, []),
    }
