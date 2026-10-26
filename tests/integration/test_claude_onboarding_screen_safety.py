"""Safety coverage for unfamiliar Claude Code onboarding displays."""

from __future__ import annotations

from tests.integration.test_claude_onboarding_screens import (
    THEME_PICKER,
    onboarding_case,
    sent_keys,
    workspace_trust,
)

__all__: list[str] = []


def test_unfamiliar_trust_and_changed_reread_send_no_onboarding_key(*, tmp_path):
    _repo, fake, sup, track = onboarding_case(
        tmp_path=tmp_path,
        capture=workspace_trust(folder="relative-folder", accept_selected=False),
    )

    relative = sup.evaluate(track=track, act=True)
    assert relative.status != "blocked-onboarding"

    fake.panes[track.topic] = workspace_trust(
        folder="/data/projects/repository",
        accept_selected=False,
    ).replace("Yes, I trust this folder", "Maybe later")
    malformed = sup.evaluate(track=track, act=True)
    assert malformed.status != "blocked-onboarding"

    fake.panes[track.topic] = ["\n" + THEME_PICKER, "unfamiliar Claude screen"]
    changed = sup.evaluate(track=track, act=True)
    assert changed.status == "blocked-onboarding"
    assert sent_keys(fake=fake) == []
