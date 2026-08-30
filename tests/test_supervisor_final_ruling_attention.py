"""Beside-tests for final-ruling and full-autonomy picker attention."""

import json

import _supervisor_config
import _supervisor_final_ruling_sources
import _supervisor_snapshot
import foreman_runtime_identity
import registry
import supervisor
from test_supervisor_builders import (
    TEST_EPIC,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def picker_capture(*, ctx: int = 80) -> str:
    return (
        "Which action should I take?\n"
        "❯ 1. Continue with the recorded next action\n"
        "  2. Escalate to the maintainer\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def final_relay(
    *,
    repo,
    session_identity: str,
    at: str = "1970-01-01T00:10:00Z",
    item_id: str = TEST_EPIC,
) -> None:
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        json.dumps(
            {
                "at": at,
                "stage": "foreman-act",
                "action_id": "blocked_session_answer",
                "session_identity": session_identity,
                "ruling_fingerprint": "rule-1",
                "final": True,
                "work_item_id": item_id,
                "branch": "HEAD",
                "branch_head": "before",
                "latest_plan_comment_at": at,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def serve_ledger(*, monkeypatch, comments) -> None:
    """Redirect the LIVE plan-epic comment read at the module that defines it.

    ``comments`` is the tuple the ledger answered with, or ``None`` for "the
    ledger could not be read at all" — the distinction the condition must keep.
    """
    monkeypatch.setattr(
        _supervisor_final_ruling_sources,
        "LEDGER_COMMENTS",
        lambda *, repo, work_item_id: comments,
    )


def test_final_ruling_unheeded_raises_report_only_attention(*, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    track = mapped_track(repo=repo, topic=topic, session=session)
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    serve_ledger(monkeypatch=monkeypatch, comments=({"created_at": "1970-01-01T00:10:00Z"},))

    row = sup.evaluate(track=track, act=True)
    payload = _supervisor_snapshot.row_payload(sup=sup, row=row)
    needs = render_of(sup=sup, views=[row]).split("NEEDS YOU")[1]

    assert row.status == "final-ruling-unheeded"
    assert "final ruling unheeded" in (row.note or "")
    assert payload["status"] == "final-ruling-unheeded"
    assert supervisor.needs_attention(row=row) is True
    assert "report-only, no restart authorized" in capsys.readouterr().err
    assert "final ruling unheeded" in needs
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_final_ruling_unheeded_suppresses_each_closed_exemption(*, tmp_path, monkeypatch):
    """The closed exemption set is now exactly the two branches that can fire.

    ``infra-external`` and ``caam-quota-exhausted`` are gone; the control that
    they no longer exist is
    ``test_the_retired_artifacts_no_longer_buy_any_exemption``.
    """
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    cases = (
        ("credential-exhaustion", {"dispatch_reason": "HTTP 429 exhausted"}),
        ("factory-host-failure", {"output": "stage fabro-run: ENOSPC No space left on device"}),
    )
    for label, setup in cases:
        repo, topic = make_plan(tmp_path=tmp_path, repo_name=f"repo-{label}", topic="topic")
        session = registry.tmux_id(repo=str(repo), topic=topic)
        fake = FakeTmux()
        fake.serve(session=session, repo=repo, capture=picker_capture())
        sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
        final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
        if reason := setup.get("dispatch_reason"):
            with (repo / "tmp" / "fabro-dispatch-journal.jsonl").open("a", encoding="utf-8") as h:
                _ = h.write(
                    json.dumps(
                        {
                            "at": "1970-01-01T00:09:00Z",
                            "stage": "outcome",
                            "outcome": {
                                "detail": reason,
                                "stage": "run-config-overlay",
                                "status": "refused",
                                "work_item_id": TEST_EPIC,
                            },
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                _ = h.write(
                    json.dumps(
                        {
                            "at": "1970-01-01T00:11:00Z",
                            "stage": "outcome",
                            "outcome": {
                                "detail": reason,
                                "stage": "run-config-overlay",
                                "status": "refused",
                                "work_item_id": TEST_EPIC,
                            },
                        }
                    )
                    + "\n"
                )
        if output := setup.get("output"):
            run_dir = repo / "tmp" / "overseer" / "detached-dispatch" / f"{TEST_EPIC}-run"
            run_dir.mkdir(parents=True)
            (run_dir / "output.log").write_text(output, encoding="utf-8")

        row = sup.evaluate(
            track=mapped_track(repo=repo, topic=topic, session=session),
            act=False,
        )

        assert row.status != "final-ruling-unheeded", label
        assert label in (row.note or "")


def test_final_ruling_unheeded_ignores_stale_credential_refusal_before_relay(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    serve_ledger(monkeypatch=monkeypatch, comments=())
    with (repo / "tmp" / "fabro-dispatch-journal.jsonl").open("a", encoding="utf-8") as h:
        _ = h.write(
            json.dumps(
                {
                    "at": "1970-01-01T00:09:00Z",
                    "stage": "outcome",
                    "outcome": {
                        "detail": "HTTP 429 exhausted",
                        "stage": "run-config-overlay",
                        "status": "refused",
                        "work_item_id": TEST_EPIC,
                    },
                },
                sort_keys=True,
            )
            + "\n"
        )

    row = sup.evaluate(
        track=mapped_track(repo=repo, topic=topic, session=session),
        act=False,
    )

    assert row.status == "final-ruling-unheeded"


def test_answering_on_the_ledger_counts_as_heeding_the_final_ruling(*, tmp_path, monkeypatch):
    """THE CONTROL for the defect: a ledger answer, and a branch that stood still.

    The seat responded the documented way — a comment on its plan epic after the
    relay — and made no commit, so ``branch_moved`` cannot rescue it. Before the
    repair this scenario reported ``final-ruling-unheeded``, because the only
    ledger reader was a cache nothing has ever written and it answered False for
    every seat, every ruling and every epic. It must not report now.
    """
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    serve_ledger(
        monkeypatch=monkeypatch,
        comments=({"created_at": "1970-01-01T00:12:00Z", "text": "acknowledged"},),
    )
    answered = sup.evaluate(track=track, act=False)
    serve_ledger(monkeypatch=monkeypatch, comments=())
    silent = sup.evaluate(track=track, act=False)

    assert answered.status != "final-ruling-unheeded"
    assert silent.status == "final-ruling-unheeded"


def test_a_moved_branch_heeds_the_ruling_without_reading_the_ledger(*, tmp_path, monkeypatch):
    """The cheap evidence short-circuits the expensive one.

    A commit on the branch settles the question, so the live ledger read — a
    subprocess with a ten-second timeout — must not run at all on that tick.
    """
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    reads: list[str] = []

    def record_read(*, repo, work_item_id):
        _ = repo
        reads.append(work_item_id)
        return ()

    monkeypatch.setattr(_supervisor_final_ruling_sources, "LEDGER_COMMENTS", record_read)
    monkeypatch.setattr(
        _supervisor_final_ruling_sources, "branch_moved", lambda *, repo, relay: True
    )
    row = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert row.status != "final-ruling-unheeded"
    assert reads == []


def test_an_unreadable_ledger_does_not_render_like_a_seat_that_never_answered(
    *, tmp_path, monkeypatch, capsys
):
    """A missing input must not pass for a silent seat — the sibling's requirement.

    Both still raise the report-only condition, because the daemon cannot prove
    the ruling was heeded either way, but the note and the alert say WHICH of the
    two was observed.
    """
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    serve_ledger(monkeypatch=monkeypatch, comments=())
    silent = sup.evaluate(track=track, act=False)
    serve_ledger(monkeypatch=monkeypatch, comments=None)
    unreadable = sup.evaluate(track=track, act=True)
    alert = capsys.readouterr().err

    assert silent.status == unreadable.status == "final-ruling-unheeded"
    assert "ledger unreadable" not in (silent.note or "")
    assert "ledger unreadable" in (unreadable.note or "")
    assert "ledger unreadable" in alert


def test_an_unreadable_dispatch_journal_still_fails_soft(*, tmp_path, monkeypatch):
    """No relay can be read, so no ruling can be unheeded.

    The journal is replaced by a DIRECTORY rather than chmod-ed unreadable: the
    suite runs as root in CI sandboxes, where a mode-000 file is still readable
    and the assertion would pass without ever reaching the failure path.
    """
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.unlink()
    journal.mkdir()

    unreadable = sup.evaluate(
        track=mapped_track(repo=repo, topic=topic, session=session), act=False
    )

    assert unreadable.status != "final-ruling-unheeded"


def test_the_retired_artifacts_no_longer_buy_any_exemption(*, tmp_path, monkeypatch):
    """Both dead-cache exemptions are gone, proven by their own former inputs.

    Writing the exact artifacts the removed branches read must now change nothing:
    ``infra-external`` and ``caam-quota-exhausted`` are no longer emittable labels.
    """
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    overseer_tmp = repo / "tmp" / "overseer"
    (overseer_tmp / "ledger-items").mkdir(parents=True, exist_ok=True)
    (overseer_tmp / "ledger-items" / f"{TEST_EPIC}.json").write_text(
        json.dumps({"id": TEST_EPIC, "metadata": {"blocked_reason": "infra-external"}}),
        encoding="utf-8",
    )
    (overseer_tmp / "caam-quota.json").write_text(
        json.dumps({"account_window_exhausted": True}), encoding="utf-8"
    )
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    serve_ledger(monkeypatch=monkeypatch, comments=())

    row = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert row.status == "final-ruling-unheeded"
    assert "infra-external" not in (row.note or "")
    assert "caam-quota-exhausted" not in (row.note or "")


def test_foreman_picker_under_full_autonomy_raises_and_clears(*, tmp_path, capsys):
    repo, _topic = make_plan(tmp_path=tmp_path)
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"full_autonomy": True}}), encoding="utf-8"
    )
    topic = foreman_runtime_identity.canonical_session_name(repo=repo)
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = registry.ForemanSeat(repo=str(repo), topic=topic, tmux=topic, epic=TEST_EPIC)

    raised = sup.evaluate(track=track, act=True)
    fake.panes[topic] = idle_capture(ctx=80, topic=topic)
    cleared = sup.evaluate(track=track, act=False)

    assert raised.status == "foreman-picker-under-full-autonomy"
    assert "full_autonomy=true" in (raised.note or "")
    assert supervisor.needs_attention(row=raised) is True
    assert "report-only, no picker answer authorized" in capsys.readouterr().err
    assert cleared.status != "foreman-picker-under-full-autonomy"


def test_foreman_picker_full_autonomy_false_suppresses_condition(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    topic = foreman_runtime_identity.canonical_session_name(repo=repo)
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = registry.ForemanSeat(repo=str(repo), topic=topic, tmux=topic, epic=TEST_EPIC)

    row = sup.evaluate(track=track, act=False)

    assert row.status != "foreman-picker-under-full-autonomy"
