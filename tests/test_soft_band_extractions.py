"""Tests for the hgq4wi.5 soft-band decompositions."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

__all__: list[str] = []


@pytest.mark.parametrize(
    ("module_name", "source_name", "public_names"),
    [
        ("_signals_context", "signals", ("parse_ctx_remaining", "strip_ansi")),
        (
            "_signals_pane_identity",
            "signals",
            ("pane_is_claude", "pane_is_codex", "pane_is_shell", "path_in_repo"),
        ),
        (
            "tmuxio_protocols",
            "tmuxio",
            ("PaneDriver", "SessionNameDriver", "WindowLayoutDriver"),
        ),
        ("_codex_session_models", "codex_sessions", ("CODEX_COMM", "CodexSession")),
        (
            "_claude_sessions_mcp_wrappers",
            "_claude_sessions_subshell",
            ("is_mcp_wrapper_shell",),
        ),
        (
            "_registry_stamp_resume",
            "_registry_stamps",
            ("read_resume_pending", "set_resume_pending"),
        ),
        ("_registry_store_rows", "_registry_store", ("track_to_row", "validated_row")),
        ("_supervisor_wrapup_injection", "_supervisor_restart", ("maybe_inject",)),
        (
            "_supervisor_ready_alerts",
            "_supervisor_liveness",
            ("uncertifiable_ready_surface",),
        ),
        (
            "_supervisor_ready_notice",
            "_supervisor_ready_alerts",
            ("STRANDED_READY_NOTICE_AFTER", "maybe_deliver_stranded_ready_notice"),
        ),
        (
            "_supervisor_pane_still",
            "_supervisor_stall_watch",
            (
                "PANE_STILL_STATUS",
                "StallWatchRequest",
                "StallWatchResult",
                "WATCH_TARGET_GONE_STATUS",
                "apply_stall_watch",
            ),
        ),
    ],
)
def test_soft_band_extractions_keep_public_facades(
    *, module_name: str, source_name: str, public_names: tuple[str, ...]
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / f"{module_name}.py"
    assert module_path.is_file()

    extracted = importlib.import_module(module_name)
    source = importlib.import_module(source_name)
    for name in public_names:
        assert hasattr(extracted, name)
        assert getattr(source, name) is getattr(extracted, name)
