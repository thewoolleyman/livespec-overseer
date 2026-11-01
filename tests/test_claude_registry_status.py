"""Mirror the Claude registry freshness regression in the configured test tree."""

from overseer.test_supervisor_claude_registry_status import (
    test_evaluate_rereads_joined_claude_status_after_cycle_snapshot,
)

__all__: list[str] = []


def test_evaluation_uses_the_registry_status_written_after_discovery(*, tmp_path) -> None:
    """The same-cycle freshness regression stays covered by the configured test tree."""
    test_evaluate_rereads_joined_claude_status_after_cycle_snapshot(tmp_path=tmp_path)
