"""Beside-tests for how the Pi active-session reader READS a session file.

The reader's transcript-safety promise rests on two mechanisms, and this module
owns both: the raw-prefix classifier that decides which lines are decoded at all,
and the bounds — line length, drained over-long lines, scanned-record count —
that keep a large transcript record from ever being held.

Each control asserts on the lines that reached the injected decoder, not only on
the returned identity: a test that checked the return value alone would pass just
as happily if the reader had decoded, logged and discarded the conversation first.

The identity JOIN these mechanisms feed lives in :mod:`test_pi_sessions`.
"""

from __future__ import annotations

import json

import pi_sessions
from test_pi_sessions_fakes import (
    FOREMAN_TOPIC,
    REPO,
    SECRET,
    SESSION_ID,
    header,
    pi_env,
    read,
    session_info,
    transcript_records,
    valid_records,
    write_session_file,
)

__all__: list[str] = []


def test_transcript_records_are_never_decoded_retained_or_returned(*, tmp_path):
    """The sentinel reaches neither the decoder nor the returned identity."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())

    sessions, parse = read(env=pi_env(session_file=path))

    assert len(parse.lines) == 2
    assert [pi_sessions.metadata_record_type(line=line) for line in parse.lines] == [
        pi_sessions.SESSION_HEADER_TYPE,
        pi_sessions.SESSION_INFO_TYPE,
    ]
    assert not any(SECRET in line for line in parse.lines)
    assert not any(SECRET in repr(session) for session in sessions)


def test_a_transcript_record_quoting_the_metadata_token_is_refused_after_decoding(*, tmp_path):
    """The residual named on `metadata_record_type` is closed by the decoded type.

    JSON escaping means a token quoted inside a STRING value cannot match the
    classifier at all — the quotes are backslash-escaped there. A NESTED OBJECT
    can, which is the real residual: this record's own `type` is `message` and
    sits after a nested block that declares the metadata token. It is classified
    as a header, decoded, and then dropped on the decoded top-level `type`.
    """
    impostor = {"content": {"type": pi_sessions.SESSION_HEADER_TYPE}, "type": "message"}
    path = write_session_file(tmp_path=tmp_path, records=[impostor, *valid_records()])

    sessions, parse = read(env=pi_env(session_file=path))

    assert pi_sessions.metadata_record_type(line=json.dumps(impostor)) == (
        pi_sessions.SESSION_HEADER_TYPE
    )
    assert len(parse.lines) == 3
    assert [(s.session_id, s.name, s.cwd) for s in sessions] == [(SESSION_ID, FOREMAN_TOPIC, REPO)]


def test_the_classifier_refuses_every_non_metadata_shape_without_decoding():
    """`metadata_record_type` is a pure raw-prefix read, so it can be tested alone."""
    for record in transcript_records():
        assert pi_sessions.metadata_record_type(line=json.dumps(record)) == ""
    assert pi_sessions.metadata_record_type(line="") == ""
    assert pi_sessions.metadata_record_type(line="not json at all") == ""
    assert pi_sessions.metadata_record_type(line=json.dumps(header())) == (
        pi_sessions.SESSION_HEADER_TYPE
    )
    assert pi_sessions.metadata_record_type(line=json.dumps(session_info())) == (
        pi_sessions.SESSION_INFO_TYPE
    )


def test_a_type_token_beyond_the_prefix_bound_is_never_classified():
    """The prefix bound is real: a token pushed past it is not seen at all."""
    padding = "x" * pi_sessions.MAX_CLASSIFIED_PREFIX_CHARS
    line = json.dumps({"content": padding, "type": pi_sessions.SESSION_HEADER_TYPE})

    assert pi_sessions.metadata_record_type(line=line) == ""


def test_a_missing_or_non_regular_session_file_refuses_closed(*, tmp_path):
    """A path that is not a readable regular file is no evidence at all."""
    missing, _ = read(env=pi_env(session_file=tmp_path / "gone.jsonl"))
    directory, _ = read(env=pi_env(session_file=tmp_path))

    assert missing == []
    assert directory == []


def test_an_undecodable_session_file_refuses_closed(*, tmp_path):
    """A non-UTF-8 file raises UnicodeDecodeError, which is not an OSError."""
    path = tmp_path / "binary.jsonl"
    path.write_bytes(b"\xff\xfe\x00\x01\n")

    sessions, _ = read(env=pi_env(session_file=path))

    assert sessions == []


def test_malformed_metadata_refuses_closed(*, tmp_path):
    """A truncated metadata line decodes to nothing, so the header never resolves."""
    path = tmp_path / "malformed.jsonl"
    path.write_text(
        '{"type": "session", "id": "'
        + SESSION_ID
        + '", "cwd"\n'
        + json.dumps(session_info())
        + "\n",
        encoding="utf-8",
    )

    sessions, parse = read(env=pi_env(session_file=path))

    assert sessions == []
    assert len(parse.lines) == 2


def test_a_well_formed_non_object_metadata_line_refuses_closed(*, tmp_path):
    """A JSON scalar carrying the token parses cleanly and is still not a record."""
    path = tmp_path / "scalar.jsonl"
    path.write_text('"type": "session"\n' + json.dumps(session_info()) + "\n", encoding="utf-8")

    sessions, _ = read(env=pi_env(session_file=path))

    assert sessions == []


def test_an_oversized_metadata_line_is_drained_and_refuses_closed(*, tmp_path):
    """Over the bound the line is drained in chunks, never decoded, never believed."""
    bound = 64
    oversized = json.dumps(header(cwd=REPO + "/" + "x" * bound * 3))
    path = write_session_file(tmp_path=tmp_path, records=[])
    path.write_text(oversized + "\n" + json.dumps(session_info()) + "\n", encoding="utf-8")

    sessions, parse = read(env=pi_env(session_file=path), max_line_chars=bound)

    assert len(oversized) > bound
    assert sessions == []
    assert parse.lines == [json.dumps(session_info()) + "\n"]


def test_an_oversized_final_line_without_a_newline_is_drained_to_end_of_file(*, tmp_path):
    """The drain also terminates at EOF, not only at a newline."""
    bound = 32
    path = tmp_path / "unterminated.jsonl"
    path.write_text(json.dumps(header()) + "\n" + "y" * bound * 4, encoding="utf-8")

    sessions, parse = read(env=pi_env(session_file=path), max_line_chars=bound)

    assert sessions == []
    assert parse.lines == []


def test_the_scanned_record_bound_stops_the_read(*, tmp_path):
    """Beyond `max_records` nothing is read, so a late name never arrives."""
    path = write_session_file(tmp_path=tmp_path, records=valid_records())

    truncated, parse = read(env=pi_env(session_file=path), max_records=1)
    whole, _ = read(env=pi_env(session_file=path))

    assert truncated == []
    assert parse.lines == [json.dumps(header()) + "\n"]
    assert whole != []
