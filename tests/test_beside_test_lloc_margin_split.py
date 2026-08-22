"""Split-contract tests for overseer beside-test LLOC margin cleanup."""

from pathlib import Path

__all__: list[str] = []


def test_hgq4wi_43_margin_residue_is_split_into_cohesive_siblings():
    base = Path(__file__).parents[1] / "overseer"

    expected = [
        "test_foreman_session_classifier_surface.py",
        "test_supervisor_claude_name_gate.py",
        "test_supervisor_recovery_launch_edges.py",
    ]

    for name in expected:
        assert (base / name).is_file(), name
