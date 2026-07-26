"""Beside-tests for `codex_sessions` — the Codex twin of `claude_sessions`.

Every /proc + filesystem coupling is injected, so these run with no codex process and
no real `~/.codex`.

Covers the pid->rollout->thread-name join, the index reader, the reboot-recovery
reverse lookup, and the rollout-id parse. The `map_codex_sessions` /
`codex_by_tmux_session` adoption twin and the /proc primitives live in
`test_codex_sessions_mapping.py`; the two were one module until it crossed the
250-LLOC hard ceiling, and the split follows the section banners the file already
carried.
"""

from __future__ import annotations

import codex_sessions
from test_codex_sessions_fakes import (
    ID_A,
    ID_B,
    fake_host,
    fake_index,
    fake_rollout,
)

__all__: list[str] = []

# --------------------------------------------------------------------------- #
# The join: pid -> open rollout fd -> session id -> thread_name (= the topic).
# --------------------------------------------------------------------------- #


def test_live_codex_session_joins_pid_to_its_thread_name_and_cwd(tmp_path):
    """The whole point: a running codex process HOLDS ITS ROLLOUT FILE OPEN, and the
    rollout filename embeds the session id, which the index maps to the thread_name —
    the plan topic. Verified live 2026-07-16 against a real 2-day-old codex TUI."""
    home = fake_index(tmp_path, [(ID_A, "rop-sweep-consumer-cleanup")])
    host = fake_host(
        comms={4242: "codex"},
        cwds={4242: "/data/projects/livespec"},
        fds={4242: ["/dev/null", fake_rollout(ID_A), "/some/other/file"]},
    )
    out = codex_sessions.read_live_codex_sessions(codex_home=home, **host)
    assert len(out) == 1
    assert out[0].pid == 4242
    assert out[0].name == "rop-sweep-consumer-cleanup"  # == the plan topic
    assert out[0].cwd == "/data/projects/livespec"
    assert out[0].session_id == ID_A


def test_non_codex_processes_are_ignored(tmp_path):
    """Only `comm == codex`. The `bun` wrapper is the codex binary's PARENT (verified
    live: pid 1681795 `bun` -> pid 1682090 `codex`) and must not be mistaken for it."""
    home = fake_index(tmp_path, [(ID_A, "some-topic")])
    host = fake_host(
        comms={1: "bun", 2: "node", 3: "zsh"},
        cwds={1: "/data/projects/livespec", 2: "/x", 3: "/y"},
        fds={1: [fake_rollout(ID_A)]},  # even if it somehow held one
    )
    assert codex_sessions.read_live_codex_sessions(codex_home=home, **host) == []


def test_codex_process_holding_no_rollout_is_skipped(tmp_path):
    """No open rollout ⇒ no session id ⇒ no join. This is also what excludes the `bun`
    wrapper structurally: verified live, it holds ZERO rollout fds while its codex child
    holds exactly one."""
    home = fake_index(tmp_path, [(ID_A, "some-topic")])
    host = fake_host(
        comms={7: "codex"}, cwds={7: "/data/projects/livespec"}, fds={7: ["/dev/null"]}
    )
    assert codex_sessions.read_live_codex_sessions(codex_home=home, **host) == []


def test_unnamed_session_is_skipped(tmp_path):
    """THE real constraint (not a heuristic problem): only NAMED sessions are indexed —
    just 67 of 259 rollouts, live 2026-07-16. An unnamed session carries no topic
    ANYWHERE, so it cannot be joined to a plan and is correctly dropped. Codex adoption
    depends on a naming convention exactly as Claude's does via `claude -n <topic>`."""
    home = fake_index(tmp_path, [(ID_A, "named-topic")])
    host = fake_host(
        comms={9: "codex"},
        cwds={9: "/data/projects/livespec"},
        fds={9: [fake_rollout(ID_B)]},  # live, but its id is NOT in the index
    )
    assert codex_sessions.read_live_codex_sessions(codex_home=home, **host) == []


def test_companion_task_threads_are_returned_not_filtered_here(tmp_path):
    """`Codex Companion Task: …` threads (38 of 69 index records, live) are the codex
    plugin's own sub-agent runs, NOT plan topics. They are deliberately NOT filtered in
    this module: they simply fail the "is this an ACTIVE plan topic?" check at adoption,
    so the noise filters itself and this module stays a pure, dumb join."""
    home = fake_index(tmp_path, [(ID_A, "Codex Companion Task: do a thing")])
    host = fake_host(
        comms={5: "codex"}, cwds={5: "/data/projects/livespec"}, fds={5: [fake_rollout(ID_A)]}
    )
    out = codex_sessions.read_live_codex_sessions(codex_home=home, **host)
    assert [s.name for s in out] == ["Codex Companion Task: do a thing"]


def test_a_process_with_no_readable_cwd_is_skipped(tmp_path):
    """Fail-soft: a pid that vanished between enumeration and the cwd read is dropped,
    never raised."""
    home = fake_index(tmp_path, [(ID_A, "topic")])
    host = fake_host(comms={5: "codex"}, cwds={}, fds={5: [fake_rollout(ID_A)]})
    assert codex_sessions.read_live_codex_sessions(codex_home=home, **host) == []


def test_multiple_live_sessions_all_join(tmp_path):
    home = fake_index(tmp_path, [(ID_A, "topic-a"), (ID_B, "topic-b")])
    host = fake_host(
        comms={11: "codex", 12: "codex"},
        cwds={11: "/data/projects/livespec", 12: "/data/projects/other"},
        fds={11: [fake_rollout(ID_A)], 12: [fake_rollout(ID_B)]},
    )
    out = codex_sessions.read_live_codex_sessions(codex_home=home, **host)
    assert {(s.pid, s.name, s.cwd) for s in out} == {
        (11, "topic-a", "/data/projects/livespec"),
        (12, "topic-b", "/data/projects/other"),
    }


# --------------------------------------------------------------------------- #
# The index reader.
# --------------------------------------------------------------------------- #


def test_index_last_record_wins_for_a_repeated_id(tmp_path):
    """`session_index.jsonl` is an APPEND log — a renamed thread appends a new record for
    the same id, so the LAST one is current."""
    home = fake_index(tmp_path, [(ID_A, "old-name"), (ID_A, "new-name")])
    assert codex_sessions.read_thread_names(codex_home=home)[ID_A] == "new-name"


def test_index_skips_malformed_lines_and_never_raises(tmp_path):
    home = tmp_path / "codex"
    home.mkdir()
    (home / "session_index.jsonl").write_text(
        "not json at all\n"
        f'{{"id": "{ID_A}", "thread_name": "good"}}\n'
        "\n"
        '{"id": 17, "thread_name": "id-not-a-string"}\n'
        '{"thread_name": "no-id"}\n'
        '{"id": "x", "thread_name": ""}\n'
    )
    assert codex_sessions.read_thread_names(codex_home=home) == {ID_A: "good"}


def test_missing_index_is_empty_not_an_error(tmp_path):
    assert codex_sessions.read_thread_names(codex_home=tmp_path / "nonexistent") == {}


def test_non_utf8_index_is_empty_not_an_error(tmp_path):
    """An UNDECODABLE index is empty, not a raise — the case the docstring's
    "fail-soft throughout" promise claimed before it was true.

    The malformed-line test above proves per-LINE tolerance, which cannot reach this:
    a non-UTF-8 byte fails the whole-file decode BEFORE any line is split, and
    ``UnicodeDecodeError`` subclasses ``ValueError``, not ``OSError``, so the read's
    original ``except OSError`` did not catch it. Adoption and reboot-recovery both
    route through this one parser, so the leak reached the daemon from two directions.
    """
    home = tmp_path / "codex"
    home.mkdir()
    (home / "session_index.jsonl").write_bytes(
        b'\xff\xfe{"id": "' + ID_A.encode() + b'", "thread_name": "good"}\n'
    )
    assert codex_sessions.read_thread_names(codex_home=home) == {}


# --------------------------------------------------------------------------- #
# latest_session_for_thread_name + rollout_exists — the reboot-recovery reverse
# lookup (defect #5). The index SURVIVES a session's death, so a dead codex track's
# session id is recoverable from its plan topic; the rollout's on-disk presence gates
# whether `codex resume` can reattach (option c) or recovery must skip+surface (b).
# --------------------------------------------------------------------------- #


def _index_ts(tmp_path, records):
    """Write a `session_index.jsonl` from (id, thread_name, updated_at) TRIPLES, in order."""
    home = tmp_path / "codex"
    home.mkdir(exist_ok=True)
    lines = [f'{{"id": "{i}", "thread_name": "{n}", "updated_at": "{ts}"}}' for i, n, ts in records]
    (home / "session_index.jsonl").write_text("\n".join(lines) + "\n")
    return home


def _write_rollout(home, session_id, *, ymd="2026/06/22", ts="2026-06-22T18-35-28"):
    """Create a real-shape rollout file for `session_id` under `<home>/sessions/YYYY/MM/DD/`."""
    day = home / "sessions" / ymd
    day.mkdir(parents=True, exist_ok=True)
    path = day / f"rollout-{ts}-{session_id}.jsonl"
    path.write_text("{}\n")  # body is never read; presence is all that matters
    return path


def test_latest_session_for_thread_name_picks_the_newest_by_updated_at(tmp_path):
    """Two indexed sessions share a topic (the plan was driven by codex more than once);
    recovery resumes the MOST-RECENT by `updated_at` — distinct per id in real data."""
    home = _index_ts(
        tmp_path,
        [
            (ID_A, "cloud-local-memory-cleanup", "2026-07-13T10:00:00Z"),
            (ID_B, "cloud-local-memory-cleanup", "2026-07-13T20:17:42Z"),
        ],
    )
    assert (
        codex_sessions.latest_session_for_thread_name(
            thread_name="cloud-local-memory-cleanup", codex_home=home
        )
        == ID_B
    )


def test_latest_session_for_thread_name_is_none_for_an_unknown_topic(tmp_path):
    """A topic named nowhere in the index is a CLAUDE track — the caller must NOT resume it
    as codex. None is the signal to fall through to the Claude recovery path."""
    home = _index_ts(tmp_path, [(ID_A, "some-codex-topic", "2026-07-13T10:00:00Z")])
    assert (
        codex_sessions.latest_session_for_thread_name(thread_name="a-claude-topic", codex_home=home)
        is None
    )


def test_latest_session_for_thread_name_honours_a_rename(tmp_path):
    """The index is an APPEND log: an id renamed AWAY from the topic (its LAST record names
    something else) no longer matches, and an id renamed TO the topic does — last record wins,
    shared with `read_thread_names` via `_read_index_final`."""
    home = _index_ts(
        tmp_path,
        [
            (ID_A, "the-topic", "2026-07-13T09:00:00Z"),  # A started as the topic...
            (ID_A, "renamed-away", "2026-07-13T09:30:00Z"),  # ...then was renamed away
            (ID_B, "was-other", "2026-07-13T10:00:00Z"),  # B started as something else...
            (ID_B, "the-topic", "2026-07-13T10:30:00Z"),  # ...then was renamed TO the topic
        ],
    )
    assert (
        codex_sessions.latest_session_for_thread_name(thread_name="the-topic", codex_home=home)
        == ID_B
    )


def test_latest_session_for_thread_name_missing_index_is_none(tmp_path):
    assert (
        codex_sessions.latest_session_for_thread_name(thread_name="t", codex_home=tmp_path / "nope")
        is None
    )


def test_rollout_exists_finds_a_nested_rollout(tmp_path):
    home = tmp_path / "codex"
    home.mkdir()
    _write_rollout(home, ID_A)
    assert codex_sessions.rollout_exists(session_id=ID_A, codex_home=home) is True


def test_rollout_exists_is_false_when_the_rollout_is_gone(tmp_path):
    """Option (b): the index still names the session, but its rollout was pruned — codex
    resume cannot reattach, so recovery must skip+surface rather than resume."""
    home = tmp_path / "codex"
    home.mkdir()
    _write_rollout(home, ID_A)  # a DIFFERENT session's rollout is present
    assert codex_sessions.rollout_exists(session_id=ID_B, codex_home=home) is False


def test_rollout_exists_is_false_when_the_sessions_dir_is_absent(tmp_path):
    home = tmp_path / "codex"
    home.mkdir()  # no sessions/ subtree at all
    assert codex_sessions.rollout_exists(session_id=ID_A, codex_home=home) is False


# --------------------------------------------------------------------------- #
# The rollout-id parse (filename ONLY — never the body; see the secrets caution).
# --------------------------------------------------------------------------- #


def test_rollout_id_is_read_from_the_filename(tmp_path):
    assert codex_sessions.rollout_id(path=fake_rollout(ID_A)) == ID_A


def test_non_rollout_paths_yield_no_id():
    for path in (
        "/dev/null",
        "/home/u/.codex/logs_2.sqlite",
        "/home/u/.codex/sessions/2026/07/16/notes.txt",
        "/home/u/.codex/sessions/rollout-no-uuid-here.jsonl",
        "",
    ):
        assert codex_sessions.rollout_id(path=path) is None


def test_open_rollout_id_picks_the_rollout_out_of_unrelated_fds():
    fds = ["/dev/urandom", "/home/u/.codex/logs_2.sqlite-wal", fake_rollout(ID_B), "socket:[1]"]
    assert codex_sessions.open_rollout_id(pid=1, fd_targets_of=lambda _p: fds) == ID_B


def test_open_rollout_id_is_none_when_no_rollout_is_held():
    assert codex_sessions.open_rollout_id(pid=1, fd_targets_of=lambda _p: ["/dev/null"]) is None
