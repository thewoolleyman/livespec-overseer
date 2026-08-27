"""Beside-tests for the Pi active-session reader's identity JOIN.

Every fact the join needs must be present and agree — the process markers that
identify a Pi tool invocation, the session id the environment carries, the header
that binds that id to a repository, and the latest session_info name — and each
one missing, empty or disagreeing yields no evidence at all.

The METADATA-READING half of the reader (how a line is classified, and the bounds
that keep a transcript unread) is a separate concern and lives in
:mod:`test_pi_sessions_metadata`.
"""

from __future__ import annotations

import pi_sessions
from test_pi_sessions_fakes import (
    FOREMAN_TOPIC,
    REPO,
    SESSION_ID,
    header,
    pi_env,
    read,
    session_info,
    valid_records,
    write_session_file,
)

__all__: list[str] = []


def test_an_active_pi_session_in_the_repo_yields_exactly_one_named_identity(*, tmp_path):
    """The positive control: markers, id, cwd and the latest name all agree."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())

    sessions, parse = read(env=pi_env(session_file=path))

    assert [(s.session_id, s.name, s.cwd) for s in sessions] == [(SESSION_ID, FOREMAN_TOPIC, REPO)]
    assert all(pi_sessions.metadata_record_type(line=line) for line in parse.lines)


def test_absent_process_markers_refuse_closed(*, tmp_path):
    """The `!` / `!!` path injects nothing, and a plain shell carries no markers."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())

    no_agent, no_agent_parse = read(env=pi_env(session_file=path, AI_AGENT=None))
    wrong_agent, _ = read(env=pi_env(session_file=path, AI_AGENT="claude"))
    no_marker, _ = read(env=pi_env(session_file=path, PI_CODING_AGENT=None))
    wrong_marker, _ = read(env=pi_env(session_file=path, PI_CODING_AGENT="false"))

    assert no_agent == []
    assert wrong_agent == []
    assert no_marker == []
    assert wrong_marker == []
    assert no_agent_parse.lines == []


def test_no_session_mode_and_an_absent_session_file_refuse_closed(*, tmp_path):
    """`--no-session` leaves the per-invocation variables unset."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())

    no_id, _ = read(env=pi_env(session_file=path, PI_SESSION_ID=None))
    empty_id, _ = read(env=pi_env(session_file=path, session_id=""))
    no_file, _ = read(env=pi_env(session_file=path, PI_SESSION_FILE=None))
    empty_file, _ = read(env=pi_env(session_file=""))

    assert no_id == []
    assert empty_id == []
    assert no_file == []
    assert empty_file == []


def test_an_id_mismatch_refuses_closed(*, tmp_path):
    """The environment's id and the header's id must be the same session."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())

    sessions, _ = read(env=pi_env(session_file=path, session_id="some-other-session"))

    assert sessions == []


def test_an_absent_or_unusable_header_refuses_closed(*, tmp_path):
    """No header, a non-string id, and a header with no cwd all fail closed."""
    headerless = write_session_file(
        tmp_path=tmp_path, records=[session_info()], name="headerless.jsonl"
    )
    typed_id = write_session_file(
        tmp_path=tmp_path,
        records=[{"type": pi_sessions.SESSION_HEADER_TYPE, "id": 7, "cwd": REPO}, session_info()],
        name="typed.jsonl",
    )
    cwdless = write_session_file(
        tmp_path=tmp_path,
        records=[{"type": pi_sessions.SESSION_HEADER_TYPE, "id": SESSION_ID}, session_info()],
        name="cwdless.jsonl",
    )

    for path in (headerless, typed_id, cwdless):
        sessions, _ = read(env=pi_env(session_file=path))
        assert sessions == [], path


def test_only_the_first_header_defines_the_identity(*, tmp_path):
    """A later header cannot redefine the session's id or repository."""
    path = write_session_file(
        tmp_path=tmp_path,
        records=[header(), header(session_id="usurper", cwd="/tmp/elsewhere"), session_info()],
    )

    sessions, _ = read(env=pi_env(session_file=path))

    assert [(s.session_id, s.cwd) for s in sessions] == [(SESSION_ID, REPO)]


def test_an_absent_or_empty_session_name_refuses_closed(*, tmp_path):
    """No session_info at all, no name key, and an explicitly cleared name."""
    nameless = write_session_file(tmp_path=tmp_path, records=[header()], name="nameless.jsonl")
    keyless = write_session_file(
        tmp_path=tmp_path,
        records=[header(), {"type": pi_sessions.SESSION_INFO_TYPE, "kind": "other"}],
        name="keyless.jsonl",
    )
    cleared = write_session_file(
        tmp_path=tmp_path, records=[header(), session_info(name="")], name="cleared.jsonl"
    )

    for path in (nameless, keyless, cleared):
        sessions, _ = read(env=pi_env(session_file=path))
        assert sessions == [], path


def test_the_latest_session_info_name_wins_including_when_it_clears_the_name(*, tmp_path):
    """Last-writer-wins in both directions: a rename is adopted, a clear refuses."""
    renamed = write_session_file(
        tmp_path=tmp_path,
        records=[header(), session_info(name="old-topic"), session_info()],
        name="renamed.jsonl",
    )
    keyless_tail = write_session_file(
        tmp_path=tmp_path,
        records=[
            header(),
            session_info(),
            {"type": pi_sessions.SESSION_INFO_TYPE, "kind": "other"},
        ],
        name="keyless-tail.jsonl",
    )
    cleared_tail = write_session_file(
        tmp_path=tmp_path,
        records=[header(), session_info(), session_info(name="")],
        name="cleared-tail.jsonl",
    )

    renamed_sessions, _ = read(env=pi_env(session_file=renamed))
    keyless_sessions, _ = read(env=pi_env(session_file=keyless_tail))
    cleared_sessions, _ = read(env=pi_env(session_file=cleared_tail))

    assert [s.name for s in renamed_sessions] == [FOREMAN_TOPIC]
    assert [s.name for s in keyless_sessions] == [FOREMAN_TOPIC]
    assert cleared_sessions == []


def test_the_default_environment_is_the_real_process_environment(*, monkeypatch, tmp_path):
    """`env=None` reads os.environ, which is how the shipped facade calls it."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())
    for key, value in pi_env(session_file=path).items():
        monkeypatch.setenv(key, value)

    assert [s.name for s in pi_sessions.read_live_pi_sessions()] == [FOREMAN_TOPIC]


def test_the_default_parse_seam_is_the_repo_json_reader(*, monkeypatch, tmp_path):
    """The recording decoder is a test control, not the shipped decode path."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())
    monkeypatch.delenv(pi_sessions.AI_AGENT_ENV, raising=False)

    sessions = pi_sessions.read_live_pi_sessions(env=pi_env(session_file=path))

    assert [s.cwd for s in sessions] == [REPO]
