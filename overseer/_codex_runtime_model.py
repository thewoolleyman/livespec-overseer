"""Codex state-database runtime-model reader for launch-profile capture.

The launch profile records the model a track will be RE-ASSERTED with on restart. Read
from launch identity alone (``-m``/``--model`` in argv, else ``ANTHROPIC_MODEL`` in the
environ), that model reverts a mid-session Codex model change to the LAUNCH model on the
daemon's ready-restart, because neither argv nor the environ is rewritten by the change.
This module supplies the additional permitted source that closes that gap for a
CODEX-harness track: ``threads.model`` in the live session's own Codex state database.

Five properties of the source are load-bearing, and each is pinned by a test:

- **The ACTIVE database only.** The active database is the numerically greatest regular
  file named ``state_<positive-integer>.sqlite`` under the resolved Codex home. A
  lower-numbered candidate is NEVER consulted when the active one is unusable, because
  an older database can retain a stale row and would answer with a model the session is
  no longer running.
- **The carrier's own Codex home.** ``CODEX_HOME`` is read from the live carrier's
  environ — the process whose model is being captured — and only a NON-EMPTY value wins;
  otherwise the daemon account's standard ``~/.codex`` is used.
- **An EXACT identity, supplied rather than chosen.** The row is selected by a thread
  identifier exactly equal to the session identity the caller already established from
  process evidence (pid → open-rollout FILENAME → index), and its ``cwd`` must resolve to
  the supervised repository. This module never enumerates rollouts, never walks into an
  ancestor or nested carrier, and never picks among candidates: with no single
  established identity the caller passes none and the source is simply unusable.
- **A real launch TOKEN, not a rendered display name.** ``threads.model`` carries the
  same token the model flag takes, which is why admitting it does not turn the
  statusline's display name into a launch token. A null, empty, ``<synthetic>`` or
  whitespace-bearing value is not a usable token and is skipped — a display name such as
  ``GPT-5.6 Terra`` is rejected by that last rule rather than being mapped back.
- **Fail-soft, everywhere.** An unresolved home; an absent, non-regular, unreadable or
  locked database; a schema without the required table or fields; a missing row; a row
  whose ``cwd`` names another repository; or an unusable token all resolve to ``None``,
  so the caller falls back to the launch source exactly as before and supervision is
  never blocked.

**This module NEVER opens a rollout body.** Rollout ``.jsonl`` files are full session
transcripts, and :mod:`codex_sessions` keeps the hard invariant that nothing here reads
one; the session id arrives from the rollout FILENAME, which this module does not even
see. The state database is a different file entirely. Keep it that way.

This is the CODEX reader only; the Claude transcript source lives in
:mod:`_claude_runtime_model` and is untouched by it.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import codex_sessions
from _seams import PidToOptionalBytes

__all__: list[str] = [
    "CODEX_HOME_ENV",
    "active_state_database",
    "carrier_codex_home",
    "read_runtime_model",
    "read_state_database_model",
    "usable_model_token",
]

CODEX_HOME_ENV = "CODEX_HOME"

# A model value that is not a launch token, mirroring the Claude transcript reader's
# rule: a synthetic marker expresses no model the track could be relaunched under.
_SYNTHETIC_MODEL = "<synthetic>"

_STATE_DATABASE_NAME = re.compile(r"^state_([0-9]+)\.sqlite$")

# The thread-identifier column, tried in order against the columns the database actually
# has. Every query is a LITERAL — the column name is never interpolated — and the
# comparison value is always the exact established session id, so a candidate that names
# the wrong column simply matches no row. Schema drift therefore fails SOFT rather than
# lending another thread's model.
_THREAD_ROW_QUERIES: tuple[tuple[str, str], ...] = (
    ("id", "SELECT model, cwd FROM threads WHERE id = ?"),
    ("thread_id", "SELECT model, cwd FROM threads WHERE thread_id = ?"),
    ("session_id", "SELECT model, cwd FROM threads WHERE session_id = ?"),
    ("uuid", "SELECT model, cwd FROM threads WHERE uuid = ?"),
)


def usable_model_token(*, value: object) -> str | None:
    """A launch token, or ``None`` for a null, empty, synthetic or display-name value.

    The whitespace rule is what keeps this source a LAUNCH-TOKEN source: a rendered
    display name carries a space, so it is rejected here instead of being mapped back to
    a token, which is the mapping the specification forbids introducing.
    """
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token or token == _SYNTHETIC_MODEL or any(char.isspace() for char in token):
        return None
    return token


def carrier_codex_home(
    *,
    pid: int,
    environ_of: PidToOptionalBytes,
    fallback: str | os.PathLike[str] | None,
) -> str | os.PathLike[str] | None:
    """The live carrier's NON-EMPTY ``CODEX_HOME``, else the daemon account's home.

    ``fallback`` is the daemon-wide Codex home seam, whose own ``None`` means "resolve
    the standard ``~/.codex``" — the same convention :mod:`codex_sessions` uses.
    """
    for item in (environ_of(pid=pid) or b"").split(b"\0"):
        key, separator, value = item.decode(errors="replace").partition("=")
        if separator and key == CODEX_HOME_ENV and value:
            return value
    return fallback


def active_state_database(*, codex_home: str | os.PathLike[str]) -> Path | None:
    """The numerically greatest regular ``state_<positive-integer>.sqlite`` file, if any.

    A lower-numbered candidate is deliberately NOT returned as a second choice: an older
    database can retain a stale row, so an unusable active database means the whole
    source is unusable.
    """
    try:
        entries = sorted(Path(codex_home).iterdir())
    except OSError:
        return None
    active: tuple[int, Path] | None = None
    for entry in entries:
        matched = _STATE_DATABASE_NAME.match(entry.name)
        if matched is None:
            continue
        number = int(matched.group(1))
        if number <= 0 or not entry.is_file():
            continue
        if active is None or number > active[0]:
            active = (number, entry)
    return None if active is None else active[1]


# The three characters SQLite gives special meaning inside a URI filename: `%` starts an
# escape, `?` starts the query and `#` starts the fragment. Escaped by hand rather than
# with `urllib.parse.quote`, because importing `urllib` anywhere reachable from the
# supervision loop trips the package's network-capable-import guard — and this reader
# does no networking at all. `%` MUST be replaced first or the later escapes are
# double-encoded.
_URI_ESCAPES: tuple[tuple[str, str], ...] = (("%", "%25"), ("?", "%3f"), ("#", "%23"))


def _read_only_uri(*, database: Path) -> str:
    """``database`` as a read-only SQLite URI, escaped so any path is expressible."""
    encoded = str(database)
    for character, escape in _URI_ESCAPES:
        encoded = encoded.replace(character, escape)
    return f"file:{encoded}?mode=ro"


def _same_repository(*, row_cwd: object, cwd: str) -> bool:
    if not isinstance(row_cwd, str):
        return False
    return Path(row_cwd).resolve() == Path(cwd).resolve()


def _thread_row_query(*, cursor: sqlite3.Cursor) -> str | None:
    columns = {str(column[1]) for column in cursor.execute("PRAGMA table_info(threads)")}
    if "model" not in columns or "cwd" not in columns:
        return None
    return next((query for name, query in _THREAD_ROW_QUERIES if name in columns), None)


def _thread_model(*, connection: sqlite3.Connection, session_id: str, cwd: str) -> str | None:
    cursor = connection.cursor()
    query = _thread_row_query(cursor=cursor)
    if query is None:
        return None
    row = cursor.execute(query, (session_id,)).fetchone()
    if row is None or not _same_repository(row_cwd=row[1], cwd=cwd):
        return None
    return usable_model_token(value=row[0])


def read_state_database_model(
    *,
    database: str | os.PathLike[str],
    session_id: str,
    cwd: str,
) -> str | None:
    """``threads.model`` for the EXACT ``session_id`` whose row ``cwd`` is ``cwd``.

    Opened read-only and without a busy wait, so a locked or unreadable database fails
    immediately to ``None`` rather than stalling the supervision round.
    """
    try:
        connection = sqlite3.connect(_read_only_uri(database=Path(database)), uri=True, timeout=0)
    except (OSError, sqlite3.Error):
        return None
    try:
        return _thread_model(connection=connection, session_id=session_id, cwd=cwd)
    except (OSError, sqlite3.Error):
        return None
    finally:
        connection.close()


def read_runtime_model(
    *,
    codex_home: str | os.PathLike[str] | None,
    session_id: str,
    cwd: str,
) -> str | None:
    """Resolve Codex home → ACTIVE state database → exact thread row → model token."""
    home = codex_home if codex_home is not None else codex_sessions.default_codex_home()
    database = active_state_database(codex_home=home)
    if database is None:
        return None
    return read_state_database_model(database=database, session_id=session_id, cwd=cwd)
