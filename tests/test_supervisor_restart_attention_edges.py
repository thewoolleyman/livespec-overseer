"""Edge coverage for post-respawn restart attention."""

import json
from pathlib import Path

import registry
import supervisor
from test_supervisor_builders import make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _capture_with_resume(*, resume: str, ctx: int) -> str:
    return (
        "● welcome\n"
        "────────────────────────────────────────\n"
        f"❯ {resume}\n"
        "────────────────────────────────────────\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
        "  ⏵⏵ bypass permissions on\n"
    )


def _record_post_respawn(*, sup: supervisor.Supervisor, repo: str, topic: str, resume: str) -> None:
    registry.write_injection_stamp(repo=repo, topic=topic, ts=900.0, stamp_path=sup.stamp_path)
    stamp_path = Path(sup.stamp_path)
    stamp_data = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp_entry = next(iter(stamp_data.values()))
    stamp_entry["post_respawn"] = {"ctx": 100, "resume": resume}
    stamp_path.write_text(json.dumps(stamp_data), encoding="utf-8")


def test_restart_never_worked_read_only_evaluation_reports_without_alerting(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    resume = supervisor.default_resume(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=_capture_with_resume(resume=resume, ctx=100))
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"], own_pane="%7")
    _record_post_respawn(sup=sup, repo=str(repo), topic=topic, resume=resume)

    first = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    assert first.status == "settling"
    clock["now"] += 61.0

    due = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    assert due.status == "restart-never-worked"
    assert supervisor.needs_attention(row=due) is True
    assert sup.alerted == {}
