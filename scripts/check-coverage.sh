#!/usr/bin/env bash
set -euo pipefail

# Aggregate fail_under=100 gate, consume-once reuse (work-item
# livespec-dev-tooling-yilyxr.8, dev-tooling PR #1462 design): inside
# `just check` the dispatcher serializes this after the clean-env
# check-per-file-coverage producer, so the repo-root .coverage exists with a
# matching run-id handoff, is read once, and is DELETED. A root .coverage file
# without that matching handoff is stale by definition and is refused instead
# of being reported as current-tree coverage. Absent .coverage (CI standalone
# job, manual run), the clean suite runs here as before.
handoff=.livespec-coverage-handoff
if [[ -f .coverage ]]; then
  expected_run_id="${LIVESPEC_CHECK_RUN_ID:-}"
  if [[ -z "$expected_run_id" ]]; then
    echo "ERROR: stale .coverage present but LIVESPEC_CHECK_RUN_ID is unset; remove .coverage or run check-per-file-coverage inside just check first" >&2
    exit 1
  fi
  if [[ ! -f "$handoff" ]]; then
    echo "ERROR: stale .coverage present without $handoff; refusing to report stale coverage as current" >&2
    exit 1
  fi
  actual_run_id="$(<"$handoff")"
  if [[ "$actual_run_id" != "$expected_run_id" ]]; then
    echo "ERROR: stale .coverage belongs to check run '$actual_run_id', not '$expected_run_id'; refusing to report stale coverage as current" >&2
    exit 1
  fi
  echo ":: check-coverage: reading .coverage produced by check-per-file-coverage in this just check run; no duplicate suite run"
  status=0
  env -u COVERAGE_FILE uv run coverage report --fail-under=100 || status=$?
  rm -f .coverage "$handoff"
  exit "$status"
fi
rm -f "$handoff"
echo ":: check-coverage: no .coverage data file (CI standalone job); running the clean suite"
env -u COVERAGE_FILE uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
