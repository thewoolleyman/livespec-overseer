"""Regression coverage for coverage.py source filtering."""

from __future__ import annotations

from pathlib import Path

from coverage import Coverage
from coverage.files import GlobMatcher

__all__: list[str] = []


ROOT = Path(__file__).resolve().parent.parent


def coverage_omit_matcher() -> GlobMatcher:
    cov = Coverage(config_file=str(ROOT / "pyproject.toml"))
    cov.load()
    return GlobMatcher(cov.get_option("run:omit"), "omit")


def test_coverage_omits_host_installed_absolute_tool_paths() -> None:
    matcher = coverage_omit_matcher()

    assert matcher.match(str(Path("/usr/local/bin/bd-guard-emit.py"))) is True


def test_coverage_still_traces_first_party_product_paths() -> None:
    matcher = coverage_omit_matcher()

    assert matcher.match(str(ROOT / "overseer" / "supervisor.py")) is False
