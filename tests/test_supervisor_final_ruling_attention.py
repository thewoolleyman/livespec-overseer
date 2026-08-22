"""Beside-tests for final-ruling and full-autonomy picker attention."""

import json

import _supervisor_config
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


def write_ledger_item(*, repo, item_id: str, blocked_reason: str | None = None) -> None:
    item = {"id": item_id, "comments": [{"created_at": "1970-01-01T00:10:00Z"}]}
    if blocked_reason is not None:
        item["metadata"] = {"blocked_reason": blocked_reason}
    path = repo / "tmp" / "overseer" / "ledger-items" / f"{item_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item), encoding="utf-8")


def test_final_ruling_unheeded_raises_report_only_attention(*, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
    track = mapped_track(repo=repo, topic=topic, session=session)
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    write_ledger_item(repo=repo, item_id=TEST_EPIC)

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
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    cases = (
        ("infra-external", {"blocked_reason": "infra-external"}),
        ("credential-exhaustion", {"dispatch_reason": "HTTP 429 exhausted"}),
        ("caam-quota-exhausted", {"caam": True}),
        ("factory-host-failure", {"output": "stage fabro-run: ENOSPC No space left on device"}),
    )
    for label, setup in cases:
        repo, topic = make_plan(tmp_path=tmp_path, repo_name=f"repo-{label}", topic="topic")
        session = registry.tmux_id(repo=str(repo), topic=topic)
        fake = FakeTmux()
        fake.serve(session=session, repo=repo, capture=picker_capture())
        sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)
        final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
        write_ledger_item(
            repo=repo,
            item_id=TEST_EPIC,
            blocked_reason=setup.get("blocked_reason"),
        )
        if reason := setup.get("dispatch_reason"):
            final_relay(
                repo=repo,
                session_identity=f"claude:{session}:{topic}",
                item_id=TEST_EPIC,
            )
            with (repo / "tmp" / "fabro-dispatch-journal.jsonl").open("a", encoding="utf-8") as h:
                _ = h.write(
                    json.dumps(
                        {
                            "at": "1970-01-01T00:11:00Z",
                            "stage": "run-config-overlay",
                            "outcome": "refused",
                            "reason": reason,
                            "work_item_id": TEST_EPIC,
                            "dispatch_id": "d1",
                        }
                    )
                    + "\n"
                )
        if setup.get("caam"):
            (repo / "tmp" / "overseer" / "caam-quota.json").parent.mkdir(
                parents=True, exist_ok=True
            )
            (repo / "tmp" / "overseer" / "caam-quota.json").write_text(
                json.dumps({"account_window_exhausted": True}), encoding="utf-8"
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


def test_final_ruling_unheeded_clears_on_movement_and_unreadable_journal_fails_soft(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "FINAL_RULING_UNHEEDED_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    final_relay(repo=repo, session_identity=f"claude:{session}:{topic}")
    write_ledger_item(repo=repo, item_id=TEST_EPIC)
    item_path = repo / "tmp" / "overseer" / "ledger-items" / f"{TEST_EPIC}.json"
    item = json.loads(item_path.read_text(encoding="utf-8"))
    item["comments"].append({"created_at": "1970-01-01T00:12:00Z"})
    item_path.write_text(json.dumps(item), encoding="utf-8")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)

    moved = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    (repo / "tmp" / "fabro-dispatch-journal.jsonl").chmod(0o000)
    unreadable = sup.evaluate(
        track=mapped_track(repo=repo, topic=topic, session=session), act=False
    )

    assert moved.status != "final-ruling-unheeded"
    assert unreadable.status != "final-ruling-unheeded"


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
