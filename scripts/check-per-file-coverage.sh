#!/usr/bin/env bash
set -euo pipefail

# Clean-env producer (work-item livespec-dev-tooling-yilyxr.8, dev-tooling
# PR #1462 design): runs the suite with COVERAGE_FILE unset so the data
# measures identically to a clean CI job by construction, then checks the
# per-file 100% floor. Leaves .coverage in place for check-coverage.sh's
# consumer path (it deletes the file after reading).
env -u COVERAGE_FILE uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
env -u COVERAGE_FILE uv run python -m livespec_dev_tooling.checks.per_file_coverage
