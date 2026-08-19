"""The supervisor send idiom must be scoped to Claude Code at the command site."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SEND_MARKER = "only after verifying"
_CLAUDE_CODE_MARKER = "CLAUDE CODE-SPECIFIC"
_HARNESS_RULE_NEEDLES = (
    "identify the harness from its footer",
    "confirm that harness's submit idiom",
)
_STOP_RULE_NEEDLES = (
    "after two failed keystrokes",
    "durable file",
)
_SEND_IDIOM_FILES = (
    _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md",
    _REPO_ROOT / ".ai" / "supervisor-protocol.md",
)


def _text_for(*, path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _command_site_windows(*, text: str) -> list[str]:
    lines = text.splitlines()
    indexes = [index for index, line in enumerate(lines) if _SEND_MARKER in line]
    return ["\n".join(lines[max(0, index - 8) : min(len(lines), index + 3)]) for index in indexes]


def _send_idiom_failures(*, text: str) -> list[str]:
    lowered = text.lower()
    failures: list[str] = []
    windows = _command_site_windows(text=text)
    if windows == []:
        failures.append("missing-send-idiom-point-of-use")
    if [window for window in windows if _CLAUDE_CODE_MARKER not in window] != []:
        failures.append("send-idiom-not-marked-claude-code-specific-at-point-of-use")
    for needle in _HARNESS_RULE_NEEDLES:
        if needle not in lowered:
            failures.append(f"missing-harness-rule:{needle}")
    for needle in _STOP_RULE_NEEDLES:
        if needle not in lowered:
            failures.append(f"missing-stop-rule:{needle}")
    return failures


def test_supervisor_send_idiom_is_harness_scoped_at_the_point_of_use() -> None:
    """THE GATE. The command-site send procedure cannot read as universal."""
    failures = {
        str(path.relative_to(_REPO_ROOT)): _send_idiom_failures(text=_text_for(path=path))
        for path in _SEND_IDIOM_FILES
    }
    assert {path: found for path, found in failures.items() if found} == {}


def test_removing_the_point_of_use_marker_makes_the_gate_red() -> None:
    """POSITIVE CONTROL. A marker-only check must be able to fail."""
    for path in _SEND_IDIOM_FILES:
        text = _text_for(path=path)
        assert _CLAUDE_CODE_MARKER in text
        sabotaged = text.replace(_CLAUDE_CODE_MARKER, "Claude Code", 1)
        assert "send-idiom-not-marked-claude-code-specific-at-point-of-use" in (
            _send_idiom_failures(text=sabotaged)
        )
