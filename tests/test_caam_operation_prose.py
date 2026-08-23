"""The caam operation prose must expose every operator-visible flag."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PROSE = ROOT / ".claude-plugin" / "prose" / "caam-anthropic-loop.md"
ENFORCEMENT_SOURCE = ROOT / "overseer" / "caam_enforcement.py"
WARM_SOURCE = ROOT / "overseer" / "caam_warm.py"

EXPECTED_FORWARDABLE_FLAGS = (
    "--force",
    "--dry-run",
    "--no-models",
    "--foreman-model=<fable|opus|auto>",
    "--session-model=<session>=<fable|opus|auto>",
    "--warm",
    "--no-warm",
    "CAAM_ROTATE_WARM=1",
)


def test_caam_prose_lists_every_source_backed_operator_flag() -> None:
    """Source-backed operator flags must not land after prose and stay hidden."""
    prose = PROSE.read_text(encoding="utf-8")
    enforcement_source = ENFORCEMENT_SOURCE.read_text(encoding="utf-8")
    warm_source = WARM_SOURCE.read_text(encoding="utf-8")

    assert "foreman_model" in enforcement_source
    assert "no_warm" in warm_source
    for flag in EXPECTED_FORWARDABLE_FLAGS:
        assert flag in prose


def test_caam_prose_explains_foreman_pin_persistence_and_clear() -> None:
    prose = PROSE.read_text(encoding="utf-8")

    assert "pin persists" in prose
    assert "later scheduled ticks" in prose
    assert "`--foreman-model=auto` clears the pin" in prose


def test_caam_prose_explains_session_model_exception_persistence() -> None:
    prose = PROSE.read_text(encoding="utf-8")

    assert "`--session-model=<session>=fable`" in prose
    assert "`--session-model=<session>=auto` clears that session's exception" in prose
    assert "reported in the table line as `exceptions:`" in prose


def test_caam_prose_carries_legacy_schedule_recovery() -> None:
    prose = PROSE.read_text(encoding="utf-8")

    assert "last known job id before the livespec-overseer cutover was `9117bfe3`" in prose
    assert "left no host cron entry, no user systemd timer, and no system systemd timer" in prose
    assert "open a\nClaude session in the `vps-info` checkout" in prose
    assert "creating the same `7,37 * * * *` schedule" in prose
    assert "cancel any replacement livespec-overseer schedule" in prose
    assert "Do not wrap the recovery invocation in `/loop`" in prose


def test_caam_prose_records_host_schedule_measurement() -> None:
    prose = PROSE.read_text(encoding="utf-8")

    assert "measured by the plan owner on 2026-08-23T06:5xZ" in prose
    assert "work-item `overseer-54k2za.31`" in prose
    assert "no `/etc/cron*` file mentioned `caam`" in prose
    assert "`sysstat-rotate.timer` and `logrotate.timer` are log rotation" in prose


def test_caam_prose_explains_cutover_operator_false_alarms() -> None:
    prose = PROSE.read_text(encoding="utf-8")

    assert "a `session-gone` row for topic `caam-anthropic-loop`" in prose
    assert "plan thread rather than the legacy watcher" in prose
    assert (
        "Do not repair that row by restarting the\nlegacy watcher seat into this repository"
        in prose
    )
    assert "resumed session whose model reads as `unknown` is also expected" in prose
    assert "bounded by the one-hour per-session memo" in prose
    assert "`homelab-foreman`" in prose
    assert "genuinely running Fable" in prose
