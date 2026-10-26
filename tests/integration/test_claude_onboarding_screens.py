"""Integration coverage for Claude Code's first-run onboarding screens.

The fixtures below are captured from the Claude Code v2.1.310 first-run flow.
They deliberately keep the complete, screen-defining text rather than using
keyword-like fragments: an unfamiliar or partial screen is ambiguous and must
not receive an onboarding keystroke.
"""

from __future__ import annotations

import contextlib
import io as _io

import _supervisor_config

from overseer import registry, supervisor
from overseer.test_supervisor_builders import (
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


THEME_PICKER = """Let's get started.

Choose the text style that looks best with your terminal

❯ Dark mode
  Light mode
  Dark mode (colorblind-friendly)
  Light mode (colorblind-friendly)

To change this later, run /theme
"""

SECURITY_NOTES = """Security notes:

1. Claude can make mistakes
You should always review Claude's responses, especially when running code.

2. Due to prompt injection risks, only use it with code you trust
For more details see:
https://code.claude.com/docs/en/security

Press Enter to continue…
"""


def workspace_trust(*, folder: str, accept_selected: bool) -> str:
    exit_marker = "  " if accept_selected else "❯ "
    accept_marker = "❯ " if accept_selected else "  "
    return (
        "Accessing workspace:\n\n"
        f"{folder}\n\n"
        "Quick safety check: Is this a project you created or one you trust? "
        "(Like your own code, a well-known\n"
        "open source project, or work from your team). If not, take a moment to review "
        "what's in this folder "
        "first.\n\n"
        "Claude Code'll be able to read, edit, and execute files here.\n\n"
        "Security guide\n\n"
        f"{exit_marker}No, exit\n"
        f"{accept_marker}Yes, I trust this folder\n"
    )


def onboarding_case(*, tmp_path, capture: str | list[str]):
    repo, topic = make_plan(tmp_path=tmp_path, topic="claude-onboarding")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: 1000.0,
        watch_repos=[str(repo)],
    )
    track = mapped_track(repo=repo, topic=topic, session=session)
    write_fresh_supervisor_state(repo=repo, topic=topic)
    return repo, fake, sup, track


def sent_keys(*, fake: FakeTmux) -> list[str]:
    return [call[2] for call in fake.calls if call[0] == "keys"]


def test_first_run_onboarding_is_classified_and_resolved_after_each_reread(*, tmp_path):
    repo, fake, sup, track = onboarding_case(
        tmp_path=tmp_path,
        capture=THEME_PICKER,
    )
    fake.panes[track.topic] = [
        THEME_PICKER,
        THEME_PICKER,
        SECURITY_NOTES,
        SECURITY_NOTES,
        workspace_trust(folder=str(repo), accept_selected=False),
        workspace_trust(folder=str(repo), accept_selected=False),
        workspace_trust(folder=str(repo), accept_selected=True),
    ]

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        theme = sup.evaluate(track=track, act=True)
        security = sup.evaluate(track=track, act=True)
        trust = sup.evaluate(track=track, act=True)

    assert [theme.status, security.status, trust.status] == [
        "blocked-onboarding",
        "blocked-onboarding",
        "blocked-onboarding",
    ]
    assert sent_keys(fake=fake) == ["Enter", "Enter", "Down", "Enter"]
    events = err.getvalue()
    assert "theme picker" in events
    assert "security-notes" in events
    assert "workspace-trust" in events
    assert str(repo) in events
    assert events.count("onboarding-keystroke") == 4


def test_foreign_workspace_trust_is_an_attention_row_without_a_keystroke(*, tmp_path):
    repo, fake, sup, track = onboarding_case(
        tmp_path=tmp_path,
        capture=workspace_trust(folder="/data/projects/other", accept_selected=False),
    )

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        row = sup.evaluate(track=track, act=True)

    assert row.status == "blocked-onboarding"
    assert supervisor.needs_attention(row=row) is True
    assert "/data/projects/other" in (row.note or "")
    assert sent_keys(fake=fake) == []
    assert "workspace-trust" in err.getvalue()
    assert "/data/projects/other" in err.getvalue()
    assert str(repo) not in (row.note or "")


def test_read_only_onboarding_reports_without_keystroking(*, tmp_path):
    _repo, fake, sup, track = onboarding_case(tmp_path=tmp_path, capture=SECURITY_NOTES)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        row = sup.evaluate(track=track, act=False)

    assert row.status == "blocked-onboarding"
    assert sent_keys(fake=fake) == []
    assert err.getvalue() == ""


def test_partial_or_unchanged_onboarding_never_becomes_a_picker_stall(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 0.0)
    partial = THEME_PICKER.removesuffix("To change this later, run /theme\n")
    _repo, fake, sup, track = onboarding_case(tmp_path=tmp_path, capture=partial)

    partial_row = sup.evaluate(track=track, act=True)
    assert partial_row.status != "blocked-onboarding"
    assert sent_keys(fake=fake) == []

    fake.panes[track.topic] = THEME_PICKER
    onboarding_row = sup.evaluate(track=track, act=True)

    assert onboarding_row.status == "blocked-onboarding"
    assert onboarding_row.status != "picker-stalled"
