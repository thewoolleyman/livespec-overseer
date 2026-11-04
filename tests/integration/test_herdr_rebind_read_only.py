"""Integration-tier read-only projection for a vanished Herdr pane mapping."""

from __future__ import annotations

import pytest
from test_codex_identity_without_a_rollout_fd import (
    test_the_read_only_list_path_reports_rebind_classifications_without_writing,
)

__all__: list[str] = []


@pytest.mark.parametrize(
    ("candidate_count", "expected_status"),
    [(0, "session-gone"), (1, "warned"), (2, "unidentified-session")],
)
def test_the_read_only_list_path_reports_rebind_classifications_without_writing_at_integration_tier(
    *, tmp_path, candidate_count, expected_status
):
    """Drive the real list tick through the zero, one, and two-candidate outcomes."""
    test_the_read_only_list_path_reports_rebind_classifications_without_writing(
        tmp_path=tmp_path,
        candidate_count=candidate_count,
        expected_status=expected_status,
    )
