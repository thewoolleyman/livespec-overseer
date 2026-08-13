"""Integration-tier coverage for SPECIFICATION v013's supervisor completion gate."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GENERATOR_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"
_SHARED_LAYER = _REPO_ROOT / ".ai" / "supervisor-protocol.md"
_BINDER = _REPO_ROOT / "tests" / "prompts" / "fixtures" / "exemplar-supervisor-handoff.md"


_SCHEMA_NEEDLES = (
    "supervision_active",
    "objective",
    "open_obligations",
    "completion_disposition",
    "wake_producer",
    "plan-complete",
    "maintainer-blocking",
    "non-terminal disposition",
)
_FAIL_CLOSED_NEEDLES = (
    "missing",
    "malformed",
    "stale",
    "unreadable",
    "any open obligation",
    "unknown completion disposition",
    "unknown wake-producer evidence",
    "refuse completion",
)
_PRODUCER_NEEDLES = (
    "live_pid",
    "expected_command",
    "identity",
    "authoritative registered producer identity",
    "prose claim is never proof",
)
_COLD_REENTRY_NEEDLES = (
    "cold-open",
    "from this marker",
    "re-query fresh ledger and forge state",
    "ended turn is never the wake mechanism",
)
_BOUNDARY_NEEDLES = (
    "Driver-owned Stop/completion gate",
    "not the overseer daemon",
    "never authorizes a daemon restart",
    "MUST NOT infer",
    "final-response text or pane text",
)
_ADDITIVE_NEEDLES = (
    "ordinary user messages are additive",
    "stop supervising <topic>",
    "replace supervision objective",
)


def _combined_current_contract() -> str:
    return "\n\n".join(
        (
            _GENERATOR_PROSE.read_text(encoding="utf-8"),
            _SHARED_LAYER.read_text(encoding="utf-8"),
            _BINDER.read_text(encoding="utf-8"),
        )
    )


def _missing_needles(*, text: str, needles: tuple[str, ...]) -> list[str]:
    lowered = " ".join(text.lower().split())
    return [needle for needle in needles if needle.lower() not in lowered]


def _completion_contract_failures(*, text: str) -> list[str]:
    failures: list[str] = []
    groups = (
        ("structured-supervisor-state-schema", _SCHEMA_NEEDLES),
        ("fail-closed-completion-conditions", _FAIL_CLOSED_NEEDLES),
        ("verifiable-wake-producer", _PRODUCER_NEEDLES),
        ("external-cold-reentry", _COLD_REENTRY_NEEDLES),
        ("driver-owned-boundary", _BOUNDARY_NEEDLES),
        ("additive-user-messages", _ADDITIVE_NEEDLES),
    )
    for name, needles in groups:
        if _missing_needles(text=text, needles=needles) != []:
            failures.append(name)
    return failures


def test_supervisor_completion_gate_contract_is_realized_in_generated_output() -> None:
    assert _completion_contract_failures(text=_combined_current_contract()) == []


def test_completion_gate_contract_rejects_fail_closed_inputs() -> None:
    damaged = (
        _combined_current_contract()
        .replace("malformed", "mistyped")
        .replace(
            "any open obligation",
            "some open obligations",
        )
    )
    failures = _completion_contract_failures(text=damaged)
    assert "fail-closed-completion-conditions" in failures
    assert "driver-owned-boundary" not in failures


def test_completion_gate_contract_rejects_unverifiable_wake_producers() -> None:
    damaged = (
        _combined_current_contract()
        .replace("prose claim", "written claim")
        .replace("Prose claim", "Written claim")
        .replace("claim is never proof", "claim may be enough")
    )
    failures = _completion_contract_failures(text=damaged)
    assert "verifiable-wake-producer" in failures


def test_completion_gate_contract_accepts_only_terminal_dispositions() -> None:
    text = _combined_current_contract()
    assert (
        _missing_needles(
            text=text,
            needles=("plan-complete", "exactly one genuine maintainer-blocking question"),
        )
        == []
    )
    damaged = text.replace("non-terminal", "progress")
    assert "structured-supervisor-state-schema" in _completion_contract_failures(text=damaged)


def test_completion_gate_contract_requires_external_cold_reentry() -> None:
    damaged = _combined_current_contract().replace(
        "ended turn is never",
        "ended turn may be",
    )
    assert "external-cold-reentry" in _completion_contract_failures(text=damaged)


def test_completion_gate_contract_keeps_user_messages_additive() -> None:
    text = _combined_current_contract()
    assert _missing_needles(text=text, needles=_ADDITIVE_NEEDLES) == []
    damaged = text.replace("additive", "resetting")
    assert "additive-user-messages" in _completion_contract_failures(text=damaged)
