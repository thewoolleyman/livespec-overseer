"""Edges for final-ruling source parsing and movement checks."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import _supervisor_config
import foreman_runtime_identity
import ledger_comments
import registry
from test_supervisor_builders import (
    TEST_EPIC,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux
from test_supervisor_final_ruling_attention import picker_capture

__all__: list[str] = []


def source_module():
    module_path = Path("overseer/_supervisor_final_ruling_sources.py")
    assert module_path.is_file()
    return importlib.import_module("_supervisor_final_ruling_sources")


def relay_at(*, source, at: float = 600.0, latest_plan_comment_at: float | None = None):
    return source.FinalRelay(
        at=at,
        item_id=TEST_EPIC,
        session_identity=None,
        branch=None,
        branch_head=None,
        latest_plan_comment_at=latest_plan_comment_at,
    )


def reader(*, comments):
    def read(*, repo: Path, work_item_id: str):
        _ = repo
        assert work_item_id == TEST_EPIC
        return comments

    return read


def test_final_ruling_source_parsers_cover_fail_soft_edges(*, tmp_path):
    source = source_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "\n" "not-json\n" f"{json.dumps({'work_item_id': TEST_EPIC})}\n" f"{json.dumps([])}\n",
        encoding="utf-8",
    )

    assert source.read_journal(repo=repo) == ({"work_item_id": TEST_EPIC},)
    assert source.relay_from_record(record={"final": False}, fallback_item_id=TEST_EPIC) is None
    assert source.relay_from_record(record={"final": True}, fallback_item_id=None) is None
    assert source.timestamp(value=True) is None
    assert source.timestamp(value=12) == 12.0
    assert source.timestamp(value="") is None
    assert source.timestamp(value="not-a-date") is None
    assert source.timestamp(value="1970-01-01T00:00:01") == 1.0


def test_final_ruling_source_branch_edges(*, tmp_path, monkeypatch):
    source = source_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    relay = source.FinalRelay(
        at=1.0,
        item_id=TEST_EPIC,
        session_identity=None,
        branch=None,
        branch_head=None,
        latest_plan_comment_at=None,
    )

    assert source.branch_moved(repo=repo, relay=relay) is False

    branch_relay = source.FinalRelay(
        at=1.0,
        item_id=TEST_EPIC,
        session_identity=None,
        branch="HEAD",
        branch_head="before",
        latest_plan_comment_at=None,
    )

    def raise_oserror(*args, **kwargs):
        _ = args
        _ = kwargs
        raise OSError

    monkeypatch.setattr(source.subprocess, "run", raise_oserror)
    assert source.branch_moved(repo=repo, relay=branch_relay) is False

    def unchanged(*args, **kwargs):
        _ = args
        _ = kwargs
        return subprocess.CompletedProcess(args=(), returncode=0, stdout="before\n")

    monkeypatch.setattr(source.subprocess, "run", unchanged)
    assert source.branch_moved(repo=repo, relay=branch_relay) is False

    def moved(*args, **kwargs):
        _ = args
        _ = kwargs
        return subprocess.CompletedProcess(args=(), returncode=0, stdout="after\n")

    monkeypatch.setattr(source.subprocess, "run", moved)
    assert source.branch_moved(repo=repo, relay=branch_relay) is True


def test_final_ruling_source_dispatch_fail_soft_edges(*, tmp_path, monkeypatch):
    source = source_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    missing = repo / "tmp" / "overseer" / "detached-dispatch" / f"{TEST_EPIC}-x"
    missing.mkdir(parents=True)
    (missing / "output.log").symlink_to(repo / "missing-output.log")
    assert source.factory_host_failure(repo=repo, item_id=TEST_EPIC) is False

    nonmatching = repo / "tmp" / "overseer" / "detached-dispatch" / f"{TEST_EPIC}-nonmatch"
    nonmatching.mkdir(parents=True)
    (nonmatching / "output.log").write_text("stage fabro-run: ordinary failure", encoding="utf-8")
    assert source.factory_host_failure(repo=repo, item_id=TEST_EPIC) is False

    original_glob = source.Path.glob

    def raise_glob(*args, **kwargs):
        _ = args
        _ = kwargs
        raise OSError

    monkeypatch.setattr(source.Path, "glob", raise_glob)
    assert source.factory_host_failure(repo=repo, item_id=TEST_EPIC) is False

    readable = repo / "tmp" / "overseer" / "detached-dispatch" / f"{TEST_EPIC}-read-error"
    readable.mkdir(parents=True, exist_ok=True)
    (readable / "output.log").write_text("stage fabro-run: ENOSPC", encoding="utf-8")

    def raise_read_text(*args, **kwargs):
        _ = args
        _ = kwargs
        raise OSError

    monkeypatch.setattr(source.Path, "glob", original_glob)
    monkeypatch.setattr(source.Path, "read_text", raise_read_text)
    assert source.factory_host_failure(repo=repo, item_id=TEST_EPIC) is False


def test_ledger_comment_moved_reads_the_live_ledger_through_the_comment_seam(*, tmp_path):
    """The seat's answer comes from the ledger, and answers BOTH ways on a fixture.

    The predecessor read ``tmp/overseer/ledger-items/<item-id>.json``, which
    nothing in this repository writes, so it could only ever answer False.
    """
    source = source_module()
    assert hasattr(source, "LedgerAnswer"), "the seam answers a LedgerAnswer, not a bare bool"
    repo, _topic = make_plan(tmp_path=tmp_path)
    relay = relay_at(source=source)

    answered = source.ledger_comment_moved(
        repo=repo,
        relay=relay,
        comments=reader(comments=({"text": "on it", "created_at": "1970-01-01T00:11:00Z"},)),
    )
    silent = source.ledger_comment_moved(
        repo=repo,
        relay=relay,
        comments=reader(comments=({"text": "older", "created_at": "1970-01-01T00:09:00Z"},)),
    )
    no_comments = source.ledger_comment_moved(repo=repo, relay=relay, comments=reader(comments=()))
    after_plan_floor = source.ledger_comment_moved(
        repo=repo,
        relay=relay_at(source=source, latest_plan_comment_at=720.0),
        comments=reader(comments=({"at": "1970-01-01T00:13:00Z"},)),
    )
    below_plan_floor = source.ledger_comment_moved(
        repo=repo,
        relay=relay_at(source=source, latest_plan_comment_at=720.0),
        comments=reader(comments=({"at": "1970-01-01T00:11:00Z"},)),
    )

    assert answered.moved is True
    assert answered.source == ledger_comments.SOURCE_LEDGER
    assert silent.moved is False
    assert silent.source == ledger_comments.SOURCE_LEDGER
    assert no_comments.moved is False
    assert after_plan_floor.moved is True
    assert below_plan_floor.moved is False

    # The producerless file the predecessor read is NOT a source any more:
    # writing it must not make a silent seat look like it answered.
    item = repo / "tmp" / "overseer" / "ledger-items" / f"{TEST_EPIC}.json"
    item.parent.mkdir(parents=True, exist_ok=True)
    item.write_text(
        json.dumps({"id": TEST_EPIC, "comments": [{"created_at": "1970-01-01T00:59:00Z"}]}),
        encoding="utf-8",
    )
    assert (
        source.ledger_comment_moved(repo=repo, relay=relay, comments=reader(comments=())).moved
        is False
    )


def test_an_unreadable_ledger_is_not_a_silent_seat(*, tmp_path):
    """Both leave the ruling unheeded; the answers must stay distinguishable."""
    source = source_module()
    assert hasattr(source, "LedgerAnswer"), "the seam answers a LedgerAnswer, not a bare bool"
    repo, _topic = make_plan(tmp_path=tmp_path)
    relay = relay_at(source=source)

    unreadable = source.ledger_comment_moved(repo=repo, relay=relay, comments=reader(comments=None))
    silent = source.ledger_comment_moved(repo=repo, relay=relay, comments=reader(comments=()))

    assert unreadable.moved is False
    assert unreadable.source == ledger_comments.SOURCE_UNAVAILABLE
    assert silent.moved is False
    assert silent.source == ledger_comments.SOURCE_LEDGER
    assert unreadable != silent


def test_the_two_producerless_exemptions_are_gone_and_the_reachable_pair_remains(*, tmp_path):
    """infra-external and caam-quota-exhausted are retired, not merely dormant."""
    source = source_module()
    repo, _topic = make_plan(tmp_path=tmp_path)

    assert not hasattr(source, "caam_quota_exhausted")
    assert not hasattr(source, "read_ledger_item")
    assert not hasattr(source, "LedgerItem")

    quota = repo / "tmp" / "overseer" / "caam-quota.json"
    quota.parent.mkdir(parents=True, exist_ok=True)
    quota.write_text(json.dumps({"account_window_exhausted": True}), encoding="utf-8")
    item = repo / "tmp" / "overseer" / "ledger-items" / f"{TEST_EPIC}.json"
    item.parent.mkdir(parents=True, exist_ok=True)
    item.write_text(
        json.dumps({"id": TEST_EPIC, "metadata": {"blocked_reason": "infra-external"}}),
        encoding="utf-8",
    )
    assert source.exemption_label(repo=repo, item_id=TEST_EPIC, floor_at=0.0) is None

    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        json.dumps(
            {
                "at": "1970-01-01T00:11:00Z",
                "stage": "outcome",
                "outcome": {
                    "detail": "HTTP 429 exhausted",
                    "status": "refused",
                    "work_item_id": TEST_EPIC,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert (
        source.exemption_label(repo=repo, item_id=TEST_EPIC, floor_at=0.0)
        == "credential-exhaustion"
    )

    journal.write_text("", encoding="utf-8")
    run_dir = repo / "tmp" / "overseer" / "detached-dispatch" / f"{TEST_EPIC}-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "output.log").write_text(
        "stage fabro-run: ENOSPC No space left on device", encoding="utf-8"
    )
    assert (
        source.exemption_label(repo=repo, item_id=TEST_EPIC, floor_at=0.0) == "factory-host-failure"
    )


def test_final_ruling_attention_read_only_and_guard_edges(*, tmp_path, monkeypatch):
    main_path = Path("overseer/_supervisor_final_ruling_attention.py")
    assert main_path.is_file()
    _ = importlib.import_module("_supervisor_final_ruling_attention")
    from test_supervisor_final_ruling_attention import final_relay

    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    monkeypatch.setattr(ledger_comments, "read_comments", reader(comments=()))
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")

    read_only = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    raised = read_only.evaluate(
        track=mapped_track(repo=repo, topic=topic, session=session), act=False
    )

    fake.panes[session] = idle_capture(ctx=80, topic=topic)
    non_blocked = read_only.evaluate(
        track=mapped_track(repo=repo, topic=topic, session=session), act=False
    )
    fake.panes[session] = picker_capture()
    too_soon = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 620.0).evaluate(
        track=mapped_track(repo=repo, topic=topic, session=session), act=False
    )

    assert raised.status == "final-ruling-unheeded"
    assert not fake.has(method="display")
    assert non_blocked.status != "final-ruling-unheeded"
    assert too_soon.status != "final-ruling-unheeded"

    empty_repo, empty_topic = make_plan(tmp_path=tmp_path, repo_name="empty-final")
    empty_session = registry.tmux_id(repo=str(empty_repo), topic=empty_topic)
    empty_fake = FakeTmux()
    empty_fake.serve(session=empty_session, repo=empty_repo, capture=picker_capture())
    empty_journal = empty_repo / "tmp" / "fabro-dispatch-journal.jsonl"
    empty_journal.parent.mkdir(parents=True, exist_ok=True)
    empty_journal.write_text(json.dumps({"final": False}), encoding="utf-8")
    empty_row = make_supervisor(tmp_path=tmp_path, fake=empty_fake, now=lambda: 1000.0).evaluate(
        track=mapped_track(repo=empty_repo, topic=empty_topic, session=empty_session), act=False
    )
    assert empty_row.status != "final-ruling-unheeded"


def test_foreman_picker_full_autonomy_act_false_has_no_alert(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"full_autonomy": True}}), encoding="utf-8"
    )
    topic = foreman_runtime_identity.canonical_session_name(repo=repo)
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = registry.ForemanSeat(repo=str(repo), topic=topic, tmux=topic, epic=TEST_EPIC)

    row = sup.evaluate(track=track, act=False)

    assert row.status == "foreman-picker-under-full-autonomy"
    assert not fake.has(method="display")
