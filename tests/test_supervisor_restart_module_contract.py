"""The restart module must name the fresh-session Codex contract truthfully."""

from __future__ import annotations

import _supervisor_restart


def test_restart_module_distinguishes_ready_replacement_from_crash_recovery() -> None:
    documentation = _supervisor_restart.__doc__ or ""

    assert "ready-time Codex replacement launches a fresh session" in documentation
    assert "routes to `codex resume <id>`" not in documentation
