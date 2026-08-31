"""The caam operation prose must expose every operator-visible flag."""

from __future__ import annotations

import re
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PROSE = ROOT / ".claude-plugin" / "prose" / "caam-anthropic-loop.md"
# Both halves of enforcement, because which one consumes the flag is an internal
# split (`caam_enforcement` orchestrates, `caam_enforcement_orchestrated` holds the
# model policy) and this control is about the flag reaching enforcement AT ALL.
ENFORCEMENT_SOURCES = (
    ROOT / "overseer" / "caam_enforcement.py",
    ROOT / "overseer" / "caam_enforcement_orchestrated.py",
)
WARM_SOURCE = ROOT / "overseer" / "caam_warm.py"
FLAG_SOURCE = ROOT / "overseer" / "caam_anthropic_loop.py"

# `--scheduled` is the invocation marker the harness itself supplies, not an
# operator flag the prose forwards, so it is excluded from the derived set.
NON_FORWARDABLE_FLAGS = frozenset(("--scheduled",))

# Keep-warm is on by design (overseer-54k2za.52); the `CAAM_ROTATE_WARM=1` opt-in
# env is retired, so no env flag is required to appear in the prose.
EXPECTED_ENV_FLAGS: tuple[str, ...] = ()


def _parser_flags() -> frozenset[str]:
    """Derive the operator flags `parse_flags` actually recognises, from its source.

    Deliberately NOT a hand-maintained list. The two defects this gate exists to
    catch -- `overseer-54k2za.22` and `overseer-54k2za.39` -- were both a flag
    landing in the parser while the prose (and this gate's own allowlist) went on
    not mentioning it. An allowlist can only catch a flag someone remembered to
    add to it, so it could not have caught either, and would not catch a third.
    """
    source = FLAG_SOURCE.read_text(encoding="utf-8")
    prefixed = set(re.findall(r'startswith\(\s*"(--[a-z0-9-]+)"', source))
    # The boolean flags are the keys `parse_flags` seeds, plus the warm opt-in.
    booleans: set[str] = set()
    seeded = re.search(r"values = \{name: False for name in \(([^)]*)\)\}", source)
    if seeded:
        booleans = {
            f"--{name.strip().strip(chr(34)).replace('_', '-')}"
            for name in seeded.group(1).split(",")
            if name.strip()
        }
    warm = set(re.findall(r'_WARM_FLAG(?::\s*Final)?\s*=\s*"(--[a-z0-9-]+)"', source))
    return frozenset(prefixed | booleans | warm) - NON_FORWARDABLE_FLAGS


def test_caam_prose_lists_every_source_backed_operator_flag() -> None:
    """Source-backed operator flags must not land after prose and stay hidden."""
    prose = PROSE.read_text(encoding="utf-8")
    enforcement_source = "".join(path.read_text(encoding="utf-8") for path in ENFORCEMENT_SOURCES)
    warm_source = WARM_SOURCE.read_text(encoding="utf-8")

    assert "foreman_model" in enforcement_source
    assert "no_warm" in warm_source

    derived = _parser_flags()
    # Control: the derivation must actually find the flag surface. An empty or
    # near-empty set would make every assertion below vacuously true, which is
    # the failure mode that lets a check pass while checking nothing.
    assert len(derived) >= 7, derived
    assert "--protected-account" in derived, derived
    assert "--foreman-model" in derived, derived

    missing = sorted(flag for flag in derived if flag not in prose)
    assert not missing, f"operator flags absent from the operation prose: {missing}"

    for env_flag in EXPECTED_ENV_FLAGS:
        assert env_flag in prose


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
