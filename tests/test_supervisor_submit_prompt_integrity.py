"""Repo-level tests for submit_prompt confirmation integrity."""

import pytest
from _supervisor_config import SUBMIT_MAX_ENTERS
from test_supervisor_builders import codex_busy_capture, idle_capture, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def claude_composer_capture(*, text: str) -> str:
    rule = "─" * 40
    return f"● prior response\n{rule}\n❯ {text}\n{rule}\n"


def test_claude_submit_does_not_confirm_empty_box_before_paste_was_seen(*, tmp_path):
    """The startup race: queued paste is not rendered, Enter is dropped, and the first
    observed box is empty. The later visible paste proves the empty box was not a submit."""
    fake = FakeTmux()
    session = "s"
    fake.sessions.add(session)
    fake.panes[session] = [
        idle_capture(),
        claude_composer_capture(text="resume plan epic overseer-test-epic"),
        claude_composer_capture(text="resume plan epic overseer-test-epic"),
    ]
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert sup._submit_prompt(target=session, text="resume plan epic overseer-test-epic") is False

    enters = [c for c in fake.calls if c[0] == "keys" and c[2] == "Enter"]
    assert len(enters) == SUBMIT_MAX_ENTERS
    assert fake.paste_texts() == ["resume plan epic overseer-test-epic"]


def test_claude_submit_confirms_after_visible_paste_clears(*, tmp_path):
    fake = FakeTmux()
    session = "s"
    fake.sessions.add(session)
    fake.panes[session] = [
        claude_composer_capture(text="read handoff.md"),
        idle_capture(),
    ]
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert sup._submit_prompt(target=session, text="read handoff.md") is True


def test_claude_submit_confirms_on_busy_transition_after_enter(*, tmp_path):
    fake = FakeTmux()
    session = "s"
    fake.sessions.add(session)
    fake.panes[session] = [
        claude_composer_capture(text="read handoff.md"),
        "● response\n✻ Galloping… (running stop hooks… 1/3 · 24s · ↓ 1.4k tokens)\n",
    ]
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert sup._submit_prompt(target=session, text="read handoff.md") is True


def test_codex_submit_requires_busy_transition_not_visible_or_empty_composer(*, tmp_path):
    """Codex is ruled out from the Claude empty-box race: its confirm leg ignores box
    emptiness and waits for the genuine busy marker."""
    fake = FakeTmux()
    session = "s"
    fake.sessions.add(session)
    idle_codex = "● prior response\n› Write tests\n  gpt-5.5 high · /x/repo · Context 40% left\n"
    fake.panes[session] = [
        idle_codex,
        idle_codex,
        codex_busy_capture(ctx=40),
    ]
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert sup._submit_prompt(target=session, text="Write tests", expect_codex=True) is True

    enters = [c for c in fake.calls if c[0] == "keys" and c[2] == "Enter"]
    assert len(enters) == 3
