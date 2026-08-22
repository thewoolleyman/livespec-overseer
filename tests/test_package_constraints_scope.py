"""Tests for package-wide constraint scope."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []


def test_caam_operation_modules_are_outside_supervision_loop_network_audit():
    constraints = Path("overseer/test_package_constraints.py").read_text(encoding="utf-8")

    assert 'not path.name.startswith("caam_")' in constraints
    assert "operation is specified to poll Anthropic's usage endpoint" in constraints


def test_daemon_runtime_dependency_guard_is_wired_with_a_control():
    constraints = Path("overseer/test_package_constraints.py").read_text(encoding="utf-8")

    assert "test_the_daemon_import_chain_needs_no_runtime_dependencies" in constraints
    assert "test_daemon_import_chain_reports_a_reachable_runtime_dependency" in constraints
    assert '"_supervisor_core.py": ["livespec-runtime"]' in constraints
