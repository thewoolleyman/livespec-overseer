"""Tests for package-wide constraint scope."""

from __future__ import annotations

import ast
from pathlib import Path

__all__: list[str] = []


def _assigned_literal(*, source: str, name: str) -> object:
    """The literal value assigned to module-level `name` in `source`."""
    assigned = [
        node.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    ]
    assert len(assigned) == 1, f"{name} must be assigned exactly once at module level"
    return ast.literal_eval(assigned[0])


def test_caam_operation_modules_are_outside_supervision_loop_network_audit():
    constraints = Path("overseer/test_package_constraints.py").read_text(encoding="utf-8")

    assert 'not path.name.startswith("caam_")' in constraints
    assert "operation is specified to poll Anthropic's usage endpoint" in constraints


def test_the_supervision_loop_network_allowlist_holds_exactly_its_two_sanctioned_entries():
    """The allowlist must not grow quietly; every member is named here.

    It carried ONE entry until SPECIFICATION v052 ratified the herdr pane
    backend, whose only control surface is a Unix socket — so the loop cannot
    reach the ratified backend at all while `socket` is excluded.

    The two entries are admitted on DIFFERENT grounds and that difference is the
    point: the OTLP emitter genuinely reaches the network, while the herdr
    transport's AF_UNIX socket has no route off the host. The second ground is a
    claim about a module's content, so the pairing assertion below requires the
    check that enforces it to exist — an allowlist entry alone cannot keep
    AF_INET out of the module it exempted.

    This reads the VALUE rather than matching one formatted line, which the
    previous version did. A literal substring match on the assignment is exact
    about content but also about layout, so re-wrapping the dict would redden it
    while a semantically identical change went unnoticed either way.
    """
    source = Path("overseer/test_package_constraints.py").read_text(encoding="utf-8")
    allowlist = _assigned_literal(source=source, name="_SUPERVISION_NETWORK_ALLOWLIST")

    assert allowlist == {
        "_supervisor_otel.py": ["http", "urllib"],
        "herdr_transport.py": ["socket"],
    }
    assert "except the dedicated OTLP emitter" in source
    assert "test_only_the_otlp_emitter_can_reach_off_the_host" in source, (
        "the herdr `socket` allowance is granted because AF_UNIX cannot leave the "
        "host; the check holding it to that claim must ship alongside it"
    )


def test_daemon_runtime_dependency_guard_is_wired_with_a_control():
    constraints = Path("overseer/test_package_constraints.py").read_text(encoding="utf-8")

    assert "test_the_daemon_import_chain_needs_no_runtime_dependencies" in constraints
    assert "test_daemon_import_chain_reports_a_reachable_runtime_dependency" in constraints
    assert '"_supervisor_core.py": ["livespec-runtime"]' in constraints
