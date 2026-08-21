#!/usr/bin/env bash
set -euo pipefail

# Clean-env producer (work-item livespec-dev-tooling-yilyxr.8, dev-tooling
# PR #1462 design): runs the suite with COVERAGE_FILE unset so the data
# measures identically to a clean CI job by construction, then checks the
# per-file 100% floor. Leaves .coverage in place for check-coverage.sh's
# consumer path, along with a run-id handoff when invoked from `just check`;
# the consumer refuses a root .coverage file without that matching handoff.
handoff=.coverage.livespec-check-run
rm -f .coverage "$handoff"
env -u COVERAGE_FILE uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
env -u COVERAGE_FILE uv run python -m livespec_dev_tooling.checks.per_file_coverage
if [[ -n "${LIVESPEC_CHECK_RUN_ID:-}" ]]; then
  printf '%s\n' "$LIVESPEC_CHECK_RUN_ID" >"$handoff"
fi
