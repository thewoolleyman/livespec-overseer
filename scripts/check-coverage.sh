#!/usr/bin/env bash
set -euo pipefail

# Aggregate fail_under=100 gate, consume-once reuse (work-item
# livespec-dev-tooling-yilyxr.8, dev-tooling PR #1462 design): inside
# `just check` the dispatcher serializes this after the clean-env
# check-per-file-coverage producer, so the repo-root .coverage exists,
# measures identically to a clean CI job by construction, carries the shared
# resolver's current reuse id, is read once and DELETED — no stale-data reports
# possible. Absent a matching id, the clean suite runs here as before.
reuse_stamp=.livespec-coverage-reuse-token
reuse_id=""
if reuse_id="$(scripts/coverage-reuse-id.sh)"; then
  :
else
  reuse_id=""
fi
if [[ -f .coverage && -f "$reuse_stamp" && -n "$reuse_id" ]] && [[ "$(cat "$reuse_stamp")" == "$reuse_id" ]]; then
  echo ":: check-coverage: reading current .coverage from matching provenance marker; no duplicate suite run"
  status=0
  rm -f "$reuse_stamp"
  env -u COVERAGE_FILE uv run coverage report --fail-under=100 || status=$?
  rm -f .coverage
  exit "$status"
fi
if [[ -f .coverage ]]; then
  echo ":: check-coverage: ignoring existing .coverage without matching provenance marker; running the clean suite"
  rm -f .coverage "$reuse_stamp"
else
  echo ":: check-coverage: no reusable .coverage data file; running the clean suite"
fi
env -u COVERAGE_FILE uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
