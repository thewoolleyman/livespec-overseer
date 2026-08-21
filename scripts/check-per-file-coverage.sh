#!/usr/bin/env bash
set -euo pipefail

# Clean-env producer (work-item livespec-dev-tooling-yilyxr.8, dev-tooling
# PR #1462 design): runs the suite with COVERAGE_FILE unset so the data
# measures identically to a clean CI job by construction, then checks the
# per-file 100% floor. Leaves .coverage in place for check-coverage.sh's
# consumer path (it deletes the file after reading). The marker stores the
# shared resolver's id and travels with .coverage across the CI job boundary.
reuse_stamp=.livespec-coverage-reuse-token
rm -f "$reuse_stamp"
env -u COVERAGE_FILE uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
if reuse_id="$(scripts/coverage-reuse-id.sh)"; then
  printf '%s\n' "$reuse_id" > "$reuse_stamp"
else
  echo ":: check-per-file-coverage: no reusable coverage provenance id; leaving no marker"
fi
env -u COVERAGE_FILE uv run python -m livespec_dev_tooling.checks.per_file_coverage
