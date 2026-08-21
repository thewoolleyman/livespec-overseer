#!/usr/bin/env bash
set -euo pipefail

# Aggregate fail_under=100 gate, consume-once reuse (work-item
# livespec-dev-tooling-yilyxr.8, dev-tooling PR #1462 design): inside
# `just check` the dispatcher serializes this after the clean-env
# check-per-file-coverage producer, so the repo-root .coverage exists,
# measures identically to a clean CI job by construction, carries the
# aggregate's current reuse token, is read once and DELETED — no stale-data
# reports possible. Absent a matching token, the clean suite runs here as
# before.
reuse_stamp=.livespec-coverage-reuse-token
if [[ -f .coverage && -f "$reuse_stamp" && -n "${LIVESPEC_COVERAGE_REUSE_TOKEN:-}" ]] && [[ "$(cat "$reuse_stamp")" == "$LIVESPEC_COVERAGE_REUSE_TOKEN" ]]; then
  echo ":: check-coverage: reading current aggregate .coverage; no duplicate suite run"
  status=0
  env -u COVERAGE_FILE uv run coverage report --fail-under=100 || status=$?
  rm -f .coverage "$reuse_stamp"
  exit "$status"
fi
if [[ -f .coverage ]]; then
  echo ":: check-coverage: ignoring existing .coverage without current aggregate token; running the clean suite"
  rm -f .coverage "$reuse_stamp"
else
  echo ":: check-coverage: no reusable .coverage data file; running the clean suite"
fi
env -u COVERAGE_FILE uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
