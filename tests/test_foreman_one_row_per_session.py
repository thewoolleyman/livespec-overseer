"""One live foreman seat publishes ONE row, under ONE identity scheme.

Measured 2026-08-23 (`overseer-nwtw`) on the daemon's own published snapshot: a single
live foreman session was carried TWICE, as `claude:<session>:foreman` reading
`foreman-blocking-prompt` and `tmux:<session>:foreman` reading `foreman-heartbeat-dead`.
The two rows route an operator OPPOSITE ways -- answer the prompt in that pane, or treat
the loop as dead and restore it -- so the surface that exists to supply judgement cost
exactly the judgement it is there to supply.

The mechanism is in `_supervisor_foreman.foreman_rows`, not in the identity function. For
one repo it emits a synthetic blocking-prompt row, which inherits the evaluated seat's
runtime and so publishes under `claude:`, AND a synthetic heartbeat row built from a
FILE, which knows no runtime at all and so falls through to `session_identity`'s `tmux:`
arm. Same repo, same topic, same tmux session name, two identities, two rows.

The negative controls are as load-bearing as the positive case, because the naive check
-- "this topic appears more than once" -- is a FALSE POSITIVE on the very snapshot that
carried the defect: three repositories legitimately run a `work-item-state-machine` topic
and several repositories legitimately run their own `foreman` seat. Neither may be
collapsed, so a blanket de-duplication on (repo, topic) is not the fix. The discriminator
is the SESSION NAME: one live session, one row.
"""

from __future__ import annotations

import json
from pathlib import Path

import _supervisor_snapshot
import registry
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def picker_capture(*, ctx: int = 80) -> str:
    return (
        "Choose how the foreman should proceed.\n"
        "❯ 1. Resume the loop\n"
        "  2. Leave it stopped\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def write_heartbeat(*, repo: Path, tick_interval_seconds: int = 600) -> Path:
    path = repo / "tmp" / "overseer" / "foreman" / "heartbeat.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "written_at": "1970-01-01T00:00:00Z",
                "pid": 4242,
                "tick_generation": 7,
                "tick_interval_seconds": tick_interval_seconds,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def make_tick_supervisor(*, tmp_path: Path, fake: FakeTmux, repos: list[Path], now: float):
    return make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        own_pane="%7",
        watch_repos=[str(repo) for repo in repos],
        now=lambda: now,
        status_writer=lambda *, path, body: None,
    )


def published_rows(*, sup, rows) -> list[dict[str, object]]:
    """The rows AS PUBLISHED, read back out of the daemon's own snapshot document.

    The defect was measured on that document rather than on the in-memory row list, and
    `session_identity` is derived there, so the assertions read the same surface an
    operator does.
    """
    document = _supervisor_snapshot.document_payload(sup=sup, rows=rows)
    return [dict(row) for row in document["rows"]]


def identity_prefix(*, row: dict[str, object]) -> str:
    return str(row["session_identity"]).split(":", 1)[0]


def sessions_under_several_identity_prefixes(
    *, rows: list[dict[str, object]]
) -> dict[str, set[str]]:
    """Session names published under more than ONE identity prefix.

    This is the discriminator the rider records, and NOT "a topic appears twice": on the
    measured snapshot the topic test flags three legitimately distinct
    `work-item-state-machine` rows and two legitimately distinct foreman seats, while this
    one isolates exactly the seat that was published twice.
    """
    prefixes: dict[str, set[str]] = {}
    for row in rows:
        session = row["tmux"]
        if not isinstance(session, str):
            continue
        prefixes.setdefault(session, set()).add(identity_prefix(row=row))
    return {session: found for session, found in prefixes.items() if len(found) > 1}


def test_one_seat_with_both_discovery_paths_live_publishes_one_foreman_row(*, tmp_path) -> None:
    repo, _topic = make_plan(tmp_path=tmp_path)
    seat = "repo-foreman"
    fake = FakeTmux()
    fake.serve(session=seat, repo=repo, capture=picker_capture())
    write_heartbeat(repo=repo)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=fake, repos=[repo], now=9000.0)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=seat, session=seat),
        store_path=sup.store_path,
        added_at="t",
    )

    rows = published_rows(sup=sup, rows=sup.tick(act=True))
    foreman_rows = [row for row in rows if row["topic"] == "foreman"]

    assert sessions_under_several_identity_prefixes(rows=rows) == {}
    assert len(foreman_rows) == 1
    assert foreman_rows[0]["tmux"] == seat
    assert foreman_rows[0]["status"] == "foreman-blocking-prompt"
    assert identity_prefix(row=foreman_rows[0]) == "claude"
    assert foreman_rows[0]["human_wait"] is True
    # The seat's OWN evaluated row survives untouched: the foreman runtime reads its
    # canonical topic back out of this snapshot to detect its own blocking prompt.
    assert [row["status"] for row in rows if row["topic"] == seat] == ["blocked:human"]


def test_the_surviving_row_carries_the_heartbeat_lapse_it_absorbed(*, tmp_path) -> None:
    repo, _topic = make_plan(tmp_path=tmp_path)
    seat = "repo-foreman"
    fake = FakeTmux()
    fake.serve(session=seat, repo=repo, capture=picker_capture())
    write_heartbeat(repo=repo)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=fake, repos=[repo], now=9000.0)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=seat, session=seat),
        store_path=sup.store_path,
        added_at="t",
    )

    rows = sup.tick(act=True)
    row = next(item for item in rows if item.topic == "foreman")
    note = row.note or ""

    assert "suppresses scheduled ticks" in note
    assert "foreman-heartbeat-dead" in note
    assert "pid 4242" in note


def test_two_distinct_sessions_sharing_repo_and_topic_still_publish_two_rows(*, tmp_path) -> None:
    """The discriminating control: the fix may not be a blanket collapse on (repo, topic).

    The mapped seat runs under a LEGACY session name while the heartbeat file names the
    canonical one, so the two rows are genuinely two sessions in one repo under one topic.
    Both must survive.
    """
    repo, _topic = make_plan(tmp_path=tmp_path)
    legacy_seat = "legacy-foreman-seat"
    fake = FakeTmux()
    fake.serve(session=legacy_seat, repo=repo, capture=picker_capture())
    write_heartbeat(repo=repo)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=fake, repos=[repo], now=9000.0)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic="repo-foreman", session=legacy_seat),
        store_path=sup.store_path,
        added_at="t",
    )

    rows = published_rows(sup=sup, rows=sup.tick(act=True))
    foreman_rows = [row for row in rows if row["topic"] == "foreman"]

    assert sessions_under_several_identity_prefixes(rows=rows) == {}
    assert [(row["tmux"], row["status"]) for row in foreman_rows] == [
        (legacy_seat, "foreman-blocking-prompt"),
        ("repo-foreman", "foreman-heartbeat-dead"),
    ]


def test_separate_repositories_each_keep_their_own_foreman_row(*, tmp_path) -> None:
    repos = [make_plan(tmp_path=tmp_path, repo_name=name)[0] for name in ("alpha", "beta")]
    for repo in repos:
        write_heartbeat(repo=repo)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=FakeTmux(), repos=repos, now=9000.0)

    rows = published_rows(sup=sup, rows=sup.tick(act=True))
    foreman_rows = [row for row in rows if row["topic"] == "foreman"]

    assert sessions_under_several_identity_prefixes(rows=rows) == {}
    assert [row["tmux"] for row in foreman_rows] == ["alpha-foreman", "beta-foreman"]


def test_three_repositories_sharing_one_plan_topic_are_not_collapsed(*, tmp_path) -> None:
    """The rider's other negative control, taken from the same measured snapshot."""
    topic = "work-item-state-machine"
    repos = [
        make_plan(tmp_path=tmp_path, repo_name=name, topic=topic)[0]
        for name in ("alpha", "beta", "gamma")
    ]
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=FakeTmux(), repos=repos, now=9000.0)

    rows = published_rows(sup=sup, rows=sup.tick(act=True))

    assert sessions_under_several_identity_prefixes(rows=rows) == {}
    assert [row["status"] for row in rows if row["topic"] == topic] == ["unassigned"] * 3


def test_a_lapsed_heartbeat_carries_the_runtime_observed_for_that_same_session(*, tmp_path) -> None:
    """No prompt is open here, so nothing is reconciled -- and the seat is still ONE seat.

    The heartbeat row is built from a file and knows no runtime, so left alone it publishes
    the live session under `tmux:` while the evaluated row publishes it under `claude:`.
    That is the same one-session-two-identities defect without the contradiction to make it
    obvious.
    """
    repo, _topic = make_plan(tmp_path=tmp_path)
    seat = "repo-foreman"
    fake = FakeTmux()
    fake.serve(session=seat, repo=repo, capture=idle_capture(ctx=88, topic=seat))
    write_heartbeat(repo=repo)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=fake, repos=[repo], now=9000.0)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=seat, session=seat),
        store_path=sup.store_path,
        added_at="t",
    )

    rows = published_rows(sup=sup, rows=sup.tick(act=True))
    foreman_rows = [row for row in rows if row["topic"] == "foreman"]

    assert sessions_under_several_identity_prefixes(rows=rows) == {}
    assert [identity_prefix(row=row) for row in foreman_rows] == ["claude"]


def test_an_unadopted_stale_heartbeat_keeps_the_identity_it_can_justify(*, tmp_path) -> None:
    """The other direction: no evaluated row names this session, so nothing is inherited.

    Inheriting a runtime the daemon did not observe would be a guess; the row keeps the
    `tmux:` scheme, which is exactly what it can justify from a heartbeat file alone.
    """
    repo, _topic = make_plan(tmp_path=tmp_path)
    write_heartbeat(repo=repo)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=FakeTmux(), repos=[repo], now=9000.0)

    rows = published_rows(sup=sup, rows=sup.tick(act=True))
    foreman_rows = [row for row in rows if row["topic"] == "foreman"]

    assert sessions_under_several_identity_prefixes(rows=rows) == {}
    assert [identity_prefix(row=row) for row in foreman_rows] == ["tmux"]
