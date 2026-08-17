#!/usr/bin/env bash
set -euo pipefail

# Aggregate fail_under=100 gate, consume-once reuse (work-item
# livespec-dev-tooling-yilyxr.8, dev-tooling PR #1462 design): inside
# `just check` the dispatcher serializes this after the clean-env
# check-per-file-coverage producer, so the repo-root .coverage exists,
# measures identically to a clean CI job by construction, is read once
# and DELETED — no stale-data reports possible. Absent the file (CI
# standalone job, manual run), the clean suite runs here as before.
if [[ -f .coverage ]]; then
  echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
  status=0
  env -u COVERAGE_FILE uv run coverage report --fail-under=100 || status=$?
  rm -f .coverage
  exit "$status"
fi
echo ":: check-coverage: no .coverage data file (CI standalone job); running the clean suite"
env -u COVERAGE_FILE uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
