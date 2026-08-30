"""Edges for final-ruling source parsing and movement checks."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import _supervisor_config
import foreman_runtime_identity
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


def test_ledger_comment_moved_answers_both_ways_on_a_fixture():
    """Both values, proven WITHOUT the store — the store's absence is the defect.

    A test that read the live channel would encode the very bug being repaired as
    its expectation, so this drives the pure predicate over a comment set held in
    hand. The floor is the relay's recorded ``latest_plan_comment_at``, else the
    relay's own instant.
    """
    source = source_module()
    relay = source.FinalRelay(
        at=10.0,
        item_id=TEST_EPIC,
        session_identity=None,
        branch=None,
        branch_head=None,
        latest_plan_comment_at=None,
    )
    after = ({"created_at": "1970-01-01T00:00:20Z"},)
    before = ({"created_at": "1970-01-01T00:00:05Z"},)

    assert source.ledger_comment_moved(relay=relay, comments=after) is True
    assert source.ledger_comment_moved(relay=relay, comments=before) is False
    assert source.ledger_comment_moved(relay=relay, comments=()) is False
    assert source.ledger_comment_moved(relay=relay, comments=({"text": "no stamp"},)) is False

    floored = source.FinalRelay(
        at=0.0,
        item_id=TEST_EPIC,
        session_identity=None,
        branch=None,
        branch_head=None,
        latest_plan_comment_at=30.0,
    )

    assert source.ledger_comment_moved(relay=floored, comments=after) is False


def test_ledger_comment_movement_keeps_an_unreadable_ledger_its_own_condition(
    *, tmp_path, monkeypatch
):
    source = source_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    relay = source.FinalRelay(
        at=10.0,
        item_id=TEST_EPIC,
        session_identity=None,
        branch=None,
        branch_head=None,
        latest_plan_comment_at=None,
    )

    monkeypatch.setattr(source, "LEDGER_COMMENTS", lambda *, repo, work_item_id: None)
    unavailable = source.ledger_comment_movement(repo=repo, relay=relay)
    monkeypatch.setattr(source, "LEDGER_COMMENTS", lambda *, repo, work_item_id: ())
    silent = source.ledger_comment_movement(repo=repo, relay=relay)
    monkeypatch.setattr(
        source,
        "LEDGER_COMMENTS",
        lambda *, repo, work_item_id: ({"created_at": "1970-01-01T00:00:20Z"},),
    )
    answered = source.ledger_comment_movement(repo=repo, relay=relay)

    assert (unavailable.moved, unavailable.source) == (False, "unavailable")
    assert (silent.moved, silent.source) == (False, "ledger")
    assert (answered.moved, answered.source) == (True, "ledger")


def test_the_two_dead_cache_exemption_branches_are_gone(*, tmp_path):
    """Neither retired artifact can produce a label any more."""
    source = source_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    overseer_tmp = repo / "tmp" / "overseer"
    (overseer_tmp / "ledger-items").mkdir(parents=True, exist_ok=True)
    (overseer_tmp / "ledger-items" / f"{TEST_EPIC}.json").write_text(
        json.dumps({"id": TEST_EPIC, "metadata": {"blocked_reason": "infra-external"}}),
        encoding="utf-8",
    )
    (overseer_tmp / "caam-quota.json").write_text(
        json.dumps({"account_window_exhausted": True}), encoding="utf-8"
    )

    assert source.exemption_label(repo=repo, item_id=TEST_EPIC, floor_at=0.0) is None
    assert not hasattr(source, "read_ledger_item")
    assert not hasattr(source, "caam_quota_exhausted")


def test_final_ruling_attention_read_only_and_guard_edges(*, tmp_path, monkeypatch):
    main_path = Path("overseer/_supervisor_final_ruling_attention.py")
    assert main_path.is_file()
    _ = importlib.import_module("_supervisor_final_ruling_attention")
    from test_supervisor_final_ruling_attention import final_relay, serve_ledger

    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    serve_ledger(monkeypatch=monkeypatch, comments=())

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
