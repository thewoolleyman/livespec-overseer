"""Claude's generated input placeholder is idle, but user-authored text is not."""

import signals

__all__: list[str] = []


def _capture(*, prompt: str) -> str:
    return "\n".join(
        [
            "● prior response",
            "─" * 40,
            f"❯ {prompt}",
            "─" * 40,
            "  Opus 5 (1M context) | /x/repo | Ctx: 73% left",
            "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents",
            "",
        ]
    )


def test_generated_try_placeholder_is_idle_but_typed_text_is_not() -> None:
    suggestion = 'Try "how does test_supervisor_status_snapshot.py work?"'
    placeholder = _capture(prompt=f"\x1b[2m{suggestion}\x1b[0m")
    typed = _capture(prompt=suggestion)

    assert signals.is_idle_input(capture_text=placeholder) is True
    assert signals.input_box_ready(capture_text=placeholder) is True
    assert signals.is_idle_input(capture_text=typed) is False
    assert signals.input_box_ready(capture_text=typed) is False
