"""The Codex state database as a permitted runtime-model source for the launch profile.

Five integration-tier scenario tests drive the REAL adoption capture path
(`sup.adopt_sessions()`) and the REAL wrap-up refresh
(`refresh_launch_profile_at_wrapup`) against a genuine on-disk SQLite state database,
and back the five `## Scenario:` headings SPECIFICATION/scenarios.md adds for this
behavior. The remaining tests pin the reader itself and the identity binding directly.
All live in one file because the red-green-replay Red moment is per-file: exactly one
test file may be staged per Red commit.

Tier: `tests.integration` is one of the documented default `scenario_tiers` prefixes,
so `check-heading-coverage` direction 4 accepts these node ids without this repo having
to declare `scenario_tiers` in `pyproject.toml`.

The two module accessors below (`codex_runtime_model` / `profile_sources`) import their
subject INSIDE the test body rather than at module top, so this file's Red moment is a
genuine assertion failure ("the reader does not exist yet") rather than a collection
error that would only prove the module unimportable.
"""

from __future__ import annotations

import builtins
import contextlib
import importlib
import io
import json
import sqlite3
from pathlib import Path

import _supervisor_launch_profile as launch_profile
import _supervisor_launch_profile_capture as capture
import _supervisor_launch_profile_refresh as refresh
import codex_sessions
import registry
from test_supervisor_builders import adopt_sup, codex_idle_capture, make_plan
from test_supervisor_fakes import FakeTmux

_PACKAGE = Path(__file__).resolve().parents[2] / "overseer"

CARRIER_PID = 9000
OTHER_CARRIER_PID = 9100
PANE_PID = 7001
TMUX_SESSION = "cx-pane"
SESSION_ID = "019f7b2f-3771-7ad3-9fc3-26fda0435ca9"
UNINDEXED_SESSION_ID = "019f7b2f-3771-7ad3-9fc3-26fda0435caa"
OTHER_SESSION_ID = "019f0000-0000-7000-8000-000000000001"

_SCHEMA = "CREATE TABLE threads (id TEXT PRIMARY KEY, model TEXT, cwd TEXT)"
_INSERT = "INSERT INTO threads (id, model, cwd) VALUES (?, ?, ?)"
_SCHEMA_WITHOUT_CWD = "CREATE TABLE threads (id TEXT PRIMARY KEY, model TEXT)"
_INSERT_WITHOUT_CWD = "INSERT INTO threads (id, model) VALUES (?, ?)"
_SCHEMA_ANOTHER_TABLE = "CREATE TABLE conversations (id TEXT, model TEXT, cwd TEXT)"
_SCHEMA_UNKNOWN_IDENTIFIER = "CREATE TABLE threads (rowkey TEXT, model TEXT, cwd TEXT)"


def codex_runtime_model():
    """The Codex state-database reader module, imported once it exists on disk."""
    assert (
        _PACKAGE / "_codex_runtime_model.py"
    ).is_file(), "overseer/_codex_runtime_model.py has not been implemented yet"
    return importlib.import_module("_codex_runtime_model")


def profile_sources():
    """The launch-profile sources module, once it can bind a Codex model source."""
    module = importlib.import_module("_supervisor_launch_profile_sources")
    assert hasattr(
        module, "codex_model_source"
    ), "_supervisor_launch_profile_sources.codex_model_source has not been implemented yet"
    return module


# --- fixtures: a real state database and a live Codex carrier ------------------------


def write_state_database(*, path, rows=(), schema=_SCHEMA, insert=_INSERT):
    """A real SQLite state database, so the reader is exercised rather than simulated."""
    connection = sqlite3.connect(path)
    with connection:
        _ = connection.execute(schema)
        if rows:
            _ = connection.executemany(insert, rows)
    connection.close()


def set_model(*, path, session_id, model):
    connection = sqlite3.connect(path)
    with connection:
        _ = connection.execute(
            "UPDATE threads SET model = ? WHERE id = ?",
            (model, session_id),
        )
    connection.close()


def codex_home_indexing(*, tmp_path, topic, session_ids, name="codex-home"):
    home = tmp_path / name
    home.mkdir(exist_ok=True)
    (home / "session_index.jsonl").write_text(
        "".join(
            json.dumps({"id": session_id, "thread_name": topic}) + "\n"
            for session_id in session_ids
        ),
        encoding="utf-8",
    )
    return home


def rollout_path(*, codex_home, session_id, on_disk=False):
    day = Path(codex_home) / "sessions" / "2026" / "09" / "11"
    path = day / f"rollout-2026-09-11T00-00-00-{session_id}.jsonl"
    if on_disk:
        day.mkdir(parents=True, exist_ok=True)
        path.write_text('{"never": "read"}\n', encoding="utf-8")
    return path


def nul(*, argv):
    return b"\0".join(part.encode() for part in argv) + b"\0"


def environ_bytes(*, values):
    return b"\0".join(f"{key}={value}".encode() for key, value in values.items()) + b"\0"


def codex_supervisor(
    *,
    tmp_path,
    repo,
    codex_home,
    model,
    rollouts=None,
    other_rollouts=(),
):
    """A supervisor whose ONLY live session is one Codex carrier in ``repo``.

    Every Codex host coupling is injected, so nothing here reads the runner's `/proc` or
    its real `~/.codex`; ``other_rollouts`` models a SECOND live carrier, which the
    tracked carrier's rollout walk must never be attributed. The carrier sets no
    ``CODEX_HOME``, so the daemon-wide home seam supplies the database location — the
    carrier-set case is pinned directly by the `carrier_codex_home` tests below.
    """
    held = rollouts if rollouts is not None else [SESSION_ID]
    fake = FakeTmux()
    fake.serve(session=TMUX_SESSION, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    fake.pane_pids = {PANE_PID: TMUX_SESSION}
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    fd_targets = {
        CARRIER_PID: [
            str(rollout_path(codex_home=codex_home, session_id=session_id)) for session_id in held
        ],
        OTHER_CARRIER_PID: [
            str(rollout_path(codex_home=codex_home, session_id=session_id))
            for session_id in other_rollouts
        ],
    }
    carriers = [CARRIER_PID, *([OTHER_CARRIER_PID] if other_rollouts else [])]
    return adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={CARRIER_PID: PANE_PID, OTHER_CARRIER_PID: PANE_PID},
        starttimes={},
        watch_repos=[str(repo)],
        codex_home=str(codex_home),
        codex_pids_of_comm=lambda *, comm: carriers if comm == codex_sessions.CODEX_COMM else [],
        codex_fd_targets_of=lambda *, pid: fd_targets.get(pid, []),
        codex_cwd_of=lambda *, pid: str(repo) if pid in fd_targets else None,
        cmdline_of=lambda *, pid: nul(argv=["codex", "-m", model]) if pid in fd_targets else None,
        environ_of=lambda *, pid: b"" if pid in fd_targets else None,
    )


def persisted_profile(*, tmp_path):
    rows = [
        json.loads(line)
        for line in (tmp_path / "map.jsonl").read_text().splitlines()
        if line.strip()
    ]
    return rows[0]["model_profile"]


def stored_track(*, tmp_path):
    return registry.read_valid_mapping(store_path=tmp_path / "map.jsonl")[0]


def refresh_at_wrapup(*, sup, tmp_path):
    """Drive the REAL wrap-up profile refresh, swallowing the daemon's own diagnostics."""
    with contextlib.redirect_stderr(io.StringIO()):
        refresh.refresh_launch_profile_at_wrapup(
            sup=sup,
            track=stored_track(tmp_path=tmp_path),
            target=TMUX_SESSION,
            capture=codex_idle_capture(ctx=40),
        )
    return persisted_profile(tmp_path=tmp_path)["model"]


def set_row_cwd(*, path, session_id, cwd):
    connection = sqlite3.connect(path)
    with connection:
        _ = connection.execute("UPDATE threads SET cwd = ? WHERE id = ?", (cwd, session_id))
    connection.close()


# --- Integration-tier scenario tests (heading-coverage backed) -----------------------


def test_scenario_codex_profile_captures_a_mid_session_model_change_from_the_database(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="cx")
    home = codex_home_indexing(tmp_path=tmp_path, topic=topic, session_ids=[SESSION_ID])
    database = home / "state_1.sqlite"
    write_state_database(path=database, rows=[(SESSION_ID, "gpt-5.6-luna", str(repo))])
    sup = codex_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        codex_home=home,
        model="gpt-5.6-terra",
    )

    adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    assert persisted_profile(tmp_path=tmp_path)["harness"] == "codex"
    assert persisted_profile(tmp_path=tmp_path)["model"] == "gpt-5.6-luna"

    set_model(path=database, session_id=SESSION_ID, model="gpt-5.6-sol")

    assert refresh_at_wrapup(sup=sup, tmp_path=tmp_path) == "gpt-5.6-sol"
    plan = launch_profile.codex_fresh_launch_plan(track=stored_track(tmp_path=tmp_path))
    assert not isinstance(plan, launch_profile.LaunchProfileProblem)
    assert "-m gpt-5.6-sol" in plan.command


def test_scenario_a_same_base_codex_database_model_preserves_the_launch_variant(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="cx")
    home = codex_home_indexing(tmp_path=tmp_path, topic=topic, session_ids=[SESSION_ID])
    write_state_database(
        path=home / "state_1.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-sol", str(repo))],
    )
    sup = codex_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        codex_home=home,
        model="gpt-5.6-sol[1m]",
    )

    adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    assert persisted_profile(tmp_path=tmp_path)["model"] == "gpt-5.6-sol[1m]"

    # CONTROL: the very same fixture DOES consult the database, so the retention above
    # is a decision about a same-base token rather than a source that never answered.
    set_model(path=home / "state_1.sqlite", session_id=SESSION_ID, model="gpt-5.7-nova")

    assert refresh_at_wrapup(sup=sup, tmp_path=tmp_path) == "gpt-5.7-nova"


def test_scenario_an_unavailable_or_mismatched_codex_state_row_fails_soft(*, tmp_path):
    # Track one: the ACTIVE database is unreadable while a LOWER-numbered database
    # retains the exact row. The stale lower-numbered token must never be consulted.
    stale = tmp_path / "stale"
    stale.mkdir()
    repo_a, topic_a = make_plan(tmp_path=stale, repo_name="repo-a", topic="cx-a")
    home_a = codex_home_indexing(
        tmp_path=stale, topic=topic_a, session_ids=[SESSION_ID], name="codex-home-a"
    )
    write_state_database(
        path=home_a / "state_1.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-stale", str(repo_a))],
    )
    (home_a / "state_2.sqlite").write_bytes(b"not a sqlite database at all")
    sup_a = codex_supervisor(
        tmp_path=stale,
        repo=repo_a,
        codex_home=home_a,
        model="gpt-5.6-terra",
    )

    # Track two: the ACTIVE database's exact-id row names ANOTHER repository as its cwd.
    wrong = tmp_path / "wrong"
    wrong.mkdir()
    repo_b, topic_b = make_plan(tmp_path=wrong, repo_name="repo-b", topic="cx-b")
    home_b = codex_home_indexing(
        tmp_path=wrong, topic=topic_b, session_ids=[SESSION_ID], name="codex-home-b"
    )
    write_state_database(
        path=home_b / "state_1.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-elsewhere", str(wrong / "another-repo"))],
    )
    sup_b = codex_supervisor(
        tmp_path=wrong,
        repo=repo_b,
        codex_home=home_b,
        model="gpt-5.6-terra",
    )

    adopted_a = sup_a.adopt_sessions()
    adopted_b = sup_b.adopt_sessions()

    assert [track.topic for track in adopted_a] == [topic_a]
    assert [track.topic for track in adopted_b] == [topic_b]
    assert persisted_profile(tmp_path=stale)["model"] == "gpt-5.6-terra"
    assert persisted_profile(tmp_path=wrong)["model"] == "gpt-5.6-terra"

    # CONTROL for BOTH tracks: repair only the defect under test and the same fixtures
    # capture the database token, so each fallback above is the named defect failing
    # soft rather than a source that was never reachable.
    (home_a / "state_2.sqlite").unlink()
    write_state_database(
        path=home_a / "state_2.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-active", str(repo_a))],
    )
    set_row_cwd(path=home_b / "state_1.sqlite", session_id=SESSION_ID, cwd=str(repo_b))

    assert refresh_at_wrapup(sup=sup_a, tmp_path=stale) == "gpt-5.6-active"
    assert refresh_at_wrapup(sup=sup_b, tmp_path=wrong) == "gpt-5.6-elsewhere"


def test_scenario_codex_runtime_model_capture_never_reads_a_rollout_body(*, tmp_path, monkeypatch):
    repo, topic = make_plan(tmp_path=tmp_path, topic="cx")
    home = codex_home_indexing(tmp_path=tmp_path, topic=topic, session_ids=[SESSION_ID])
    _ = rollout_path(codex_home=home, session_id=SESSION_ID, on_disk=True)
    write_state_database(
        path=home / "state_1.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-luna", str(repo))],
    )
    sup = codex_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        codex_home=home,
        model="gpt-5.6-terra",
    )
    real_open = builtins.open

    def refuse_rollout_bodies(file, *args, **kwargs):
        if Path(str(file)).name.startswith("rollout-"):
            raise AssertionError(f"a Codex rollout body was opened: {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", refuse_rollout_bodies)
    monkeypatch.setattr(io, "open", refuse_rollout_bodies)

    adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    assert persisted_profile(tmp_path=tmp_path)["model"] == "gpt-5.6-luna"


def test_scenario_an_ambiguous_rollout_set_cannot_lend_another_codex_model(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="cx")
    home = codex_home_indexing(tmp_path=tmp_path, topic=topic, session_ids=[SESSION_ID])
    write_state_database(
        path=home / "state_1.sqlite",
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(repo)),
            (OTHER_SESSION_ID, "gpt-5.6-borrowed", str(repo)),
        ],
    )
    sup = codex_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        codex_home=home,
        model="gpt-5.6-terra",
        rollouts=[UNINDEXED_SESSION_ID, SESSION_ID],
        other_rollouts=[OTHER_SESSION_ID],
    )

    adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    assert persisted_profile(tmp_path=tmp_path)["model"] == "gpt-5.6-luna"

    # With NO indexed candidate the carrier names no session at all, so no launch-profile
    # source is produced and nothing invents an identity from the ambiguous set.
    unnamed = tmp_path / "unnamed"
    unnamed.mkdir()
    repo_c, topic_c = make_plan(tmp_path=unnamed, repo_name="repo-c", topic="cx-c")
    home_c = codex_home_indexing(
        tmp_path=unnamed, topic=topic_c, session_ids=[], name="codex-home-c"
    )
    sup_c = codex_supervisor(
        tmp_path=unnamed,
        repo=repo_c,
        codex_home=home_c,
        model="gpt-5.6-terra",
        rollouts=[UNINDEXED_SESSION_ID, OTHER_SESSION_ID],
    )

    assert sup_c.adopt_sessions() == []
    sources = profile_sources()
    identity_free = sources.LaunchProfileSource(pid=CARRIER_PID, harness="codex", pane_pid=None)
    assert (
        sources.codex_model_source(
            source=identity_free,
            environ_of=lambda *, pid: b"",
            codex_home=str(home_c),
        )
        is None
    )
    assert capture.complete_launch_profile(
        profile={"harness": "codex", "model": "gpt-5.6-terra", "wrapper": None},
        harness="codex",
        pid=CARRIER_PID,
        runtime_model_of=lambda *, pid: None,
        codex_identity=None,
    ) == {"harness": "codex", "model": "gpt-5.6-terra", "wrapper": None}


# --- usable_model_token -------------------------------------------------------------


def test_usable_model_token_accepts_a_launch_token_and_refuses_everything_else():
    crm = codex_runtime_model()

    assert crm.usable_model_token(value="  gpt-5.6-sol[1m]  ") == "gpt-5.6-sol[1m]"
    assert crm.usable_model_token(value=None) is None
    assert crm.usable_model_token(value="") is None
    assert crm.usable_model_token(value="   ") is None
    assert crm.usable_model_token(value="<synthetic>") is None
    # A RENDERED DISPLAY NAME is refused here rather than mapped back to a token, which
    # is the mapping the specification forbids introducing.
    assert crm.usable_model_token(value="GPT-5.6 Terra") is None


# --- carrier_codex_home -------------------------------------------------------------


def test_carrier_codex_home_prefers_the_carriers_own_non_empty_value():
    crm = codex_runtime_model()

    assert (
        crm.carrier_codex_home(
            pid=CARRIER_PID,
            environ_of=lambda *, pid: environ_bytes(
                values={"PATH": "/bin", "CODEX_HOME": "/carrier/.codex"}
            ),
            fallback="/daemon/.codex",
        )
        == "/carrier/.codex"
    )


def test_carrier_codex_home_falls_back_for_absent_empty_or_unrelated_environs():
    crm = codex_runtime_model()

    def home(*, environ):
        return crm.carrier_codex_home(
            pid=CARRIER_PID,
            environ_of=lambda *, pid: environ,
            fallback="/daemon/.codex",
        )

    assert home(environ=None) == "/daemon/.codex"
    assert home(environ=b"CODEX_HOME=\0") == "/daemon/.codex"
    assert home(environ=b"PATH=/bin\0") == "/daemon/.codex"
    assert home(environ=b"NO_EQUALS_SIGN\0") == "/daemon/.codex"


# --- active_state_database ----------------------------------------------------------


def test_active_state_database_picks_the_numerically_greatest_regular_file(*, tmp_path):
    crm = codex_runtime_model()
    home = tmp_path / "home"
    home.mkdir()
    for name in ("state_1.sqlite", "state_2.sqlite", "state_10.sqlite", "state_0.sqlite"):
        (home / name).write_bytes(b"")
    (home / "state_11.sqlite").mkdir()  # not a regular file
    (home / "notes.sqlite").write_bytes(b"")
    (home / "state_x.sqlite").write_bytes(b"")

    assert crm.active_state_database(codex_home=home) == home / "state_10.sqlite"


def test_active_state_database_is_none_without_candidates_or_a_readable_home(*, tmp_path):
    crm = codex_runtime_model()
    empty = tmp_path / "empty"
    empty.mkdir()

    assert crm.active_state_database(codex_home=empty) is None
    assert crm.active_state_database(codex_home=tmp_path / "absent") is None


# --- read_state_database_model ------------------------------------------------------


def test_read_state_database_model_returns_the_exact_rows_token(*, tmp_path):
    crm = codex_runtime_model()
    database = tmp_path / "state_1.sqlite"
    write_state_database(
        path=database,
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(tmp_path)),
            (OTHER_SESSION_ID, "gpt-5.6-borrowed", str(tmp_path)),
        ],
    )

    assert (
        crm.read_state_database_model(database=database, session_id=SESSION_ID, cwd=str(tmp_path))
        == "gpt-5.6-luna"
    )


def test_read_state_database_model_fails_soft_for_every_database_and_row_defect(*, tmp_path):
    crm = codex_runtime_model()

    def model(*, database, session_id=SESSION_ID, cwd=str(tmp_path)):
        return crm.read_state_database_model(database=database, session_id=session_id, cwd=cwd)

    absent = tmp_path / "absent.sqlite"
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"definitely not a sqlite file")
    no_table = tmp_path / "no-table.sqlite"
    write_state_database(path=no_table, schema=_SCHEMA_ANOTHER_TABLE)
    no_cwd_column = tmp_path / "no-cwd.sqlite"
    write_state_database(
        path=no_cwd_column,
        schema=_SCHEMA_WITHOUT_CWD,
        insert=_INSERT_WITHOUT_CWD,
        rows=[(SESSION_ID, "gpt-5.6-luna")],
    )
    unknown_identifier = tmp_path / "unknown-id.sqlite"
    write_state_database(path=unknown_identifier, schema=_SCHEMA_UNKNOWN_IDENTIFIER)
    populated = tmp_path / "populated.sqlite"
    write_state_database(
        path=populated,
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(tmp_path)),
            (OTHER_SESSION_ID, "gpt-5.6-luna", None),
            ("null-model", None, str(tmp_path)),
            ("display-name", "GPT-5.6 Terra", str(tmp_path)),
        ],
    )

    assert model(database=absent) is None
    assert model(database=corrupt) is None
    assert model(database=no_table) is None
    assert model(database=no_cwd_column) is None
    assert model(database=unknown_identifier) is None
    assert model(database=populated, session_id="no-such-thread") is None
    assert model(database=populated, session_id=OTHER_SESSION_ID) is None
    assert model(database=populated, cwd=str(tmp_path / "elsewhere")) is None
    assert model(database=populated, session_id="null-model") is None
    assert model(database=populated, session_id="display-name") is None


def test_read_state_database_model_fails_soft_on_a_locked_database(*, tmp_path):
    crm = codex_runtime_model()
    database = tmp_path / "state_1.sqlite"
    write_state_database(path=database, rows=[(SESSION_ID, "gpt-5.6-luna", str(tmp_path))])
    holder = sqlite3.connect(database)
    holder.isolation_level = None
    _ = holder.execute("BEGIN EXCLUSIVE")
    try:
        assert (
            crm.read_state_database_model(
                database=database, session_id=SESSION_ID, cwd=str(tmp_path)
            )
            is None
        )
    finally:
        _ = holder.execute("ROLLBACK")
        holder.close()


# --- read_runtime_model -------------------------------------------------------------


def test_read_runtime_model_resolves_home_then_active_database_then_row(*, tmp_path):
    crm = codex_runtime_model()
    home = tmp_path / "home"
    home.mkdir()
    write_state_database(
        path=home / "state_1.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-stale", str(tmp_path))],
    )
    write_state_database(
        path=home / "state_2.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-luna", str(tmp_path))],
    )

    assert (
        crm.read_runtime_model(codex_home=home, session_id=SESSION_ID, cwd=str(tmp_path))
        == "gpt-5.6-luna"
    )
    assert (
        crm.read_runtime_model(
            codex_home=tmp_path / "absent", session_id=SESSION_ID, cwd=str(tmp_path)
        )
        is None
    )


def test_read_runtime_model_falls_back_to_the_daemon_accounts_codex_home(*, tmp_path, monkeypatch):
    crm = codex_runtime_model()
    home = tmp_path / "account-home"
    (home / ".codex").mkdir(parents=True)
    write_state_database(
        path=home / ".codex" / "state_1.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-account", str(tmp_path))],
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert (
        crm.read_runtime_model(codex_home=None, session_id=SESSION_ID, cwd=str(tmp_path))
        == "gpt-5.6-account"
    )


# --- codex_model_source: the identity binding ---------------------------------------


def test_codex_model_source_binds_an_established_identity_and_the_carriers_home(*, tmp_path):
    sources = profile_sources()
    source = sources.LaunchProfileSource(
        pid=CARRIER_PID,
        harness="codex",
        pane_pid=PANE_PID,
        session_id=SESSION_ID,
        cwd=str(tmp_path),
    )

    bound = sources.codex_model_source(
        source=source,
        environ_of=lambda *, pid: environ_bytes(values={"CODEX_HOME": "/carrier/.codex"}),
        codex_home="/daemon/.codex",
        read=lambda *, codex_home, session_id, cwd: f"{codex_home}|{session_id}|{cwd}",
    )

    assert bound is not None
    assert bound.session_id == SESSION_ID
    assert bound.cwd == str(tmp_path)
    assert bound.codex_home == "/carrier/.codex"
    assert (
        capture.complete_launch_profile(
            profile={"harness": "codex", "model": "gpt-5.6-terra", "wrapper": None},
            harness="codex",
            pid=CARRIER_PID,
            runtime_model_of=lambda *, pid: None,
            codex_identity=bound,
        )["model"]
        == f"/carrier/.codex|{SESSION_ID}|{tmp_path}"
    )


def test_codex_model_source_is_none_without_a_complete_established_identity(*, tmp_path):
    sources = profile_sources()

    def bind(*, session_id, cwd):
        return sources.codex_model_source(
            source=sources.LaunchProfileSource(
                pid=CARRIER_PID,
                harness="codex",
                pane_pid=None,
                session_id=session_id,
                cwd=cwd,
            ),
            environ_of=lambda *, pid: b"",
            codex_home=str(tmp_path),
        )

    assert bind(session_id=None, cwd=str(tmp_path)) is None
    assert bind(session_id=SESSION_ID, cwd=None) is None
    assert bind(session_id=SESSION_ID, cwd=str(tmp_path)) is not None


# --- complete_launch_profile: the two sources stay apart --------------------------------


def test_completing_a_profile_leaves_a_third_harness_model_untouched():
    """Neither permitted source applies to a harness that declares neither."""
    profile = capture.complete_launch_profile(
        profile={"harness": "pi", "model": "macmini/qwen3", "wrapper": None},
        harness="pi",
        pid=CARRIER_PID,
        runtime_model_of=lambda *, pid: "claude-fable-5-1",
        codex_identity=None,
    )

    assert profile["model"] == "macmini/qwen3"


def test_the_codex_source_does_not_change_claude_capture(*, tmp_path):
    """A Claude track ignores the Codex state database entirely, identity bound or not."""
    sources = profile_sources()
    bound = sources.codex_model_source(
        source=sources.LaunchProfileSource(
            pid=CARRIER_PID,
            harness="claude",
            pane_pid=None,
            session_id=SESSION_ID,
            cwd=str(tmp_path),
        ),
        environ_of=lambda *, pid: b"",
        codex_home=str(tmp_path),
        read=lambda *, codex_home, session_id, cwd: "gpt-5.6-leaked",
    )

    profile = capture.complete_launch_profile(
        profile={"harness": "claude", "model": "claude-opus-4-8[1m]", "wrapper": None},
        harness="claude",
        pid=CARRIER_PID,
        runtime_model_of=lambda *, pid: "claude-opus-4-8",
        codex_identity=bound,
    )

    assert profile["model"] == "claude-opus-4-8[1m]"
