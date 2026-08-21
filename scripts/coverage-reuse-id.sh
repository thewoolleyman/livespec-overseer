#!/usr/bin/env bash
set -euo pipefail

# Coverage reuse provenance resolver.
#
# CI jobs use GitHub's run id plus run attempt because both the producer and
# consumer receive those values independently, they are stable within one
# workflow attempt, and they change on both a new run and a re-run. Local runs
# use the tracked Git tree state so `just check-per-file-coverage` followed by
# `just check-coverage` can reuse data without an aggregate-only environment
# token, while tracked source changes invalidate old markers. The id is stored
# in .livespec-coverage-reuse-token beside .coverage.
if [[ -n "${GITHUB_RUN_ID:-}" || -n "${GITHUB_RUN_ATTEMPT:-}" ]]; then
  if [[ -z "${GITHUB_RUN_ID:-}" || -z "${GITHUB_RUN_ATTEMPT:-}" ]]; then
    exit 1
  fi
  printf 'github-run:%s:attempt:%s\n' "$GITHUB_RUN_ID" "$GITHUB_RUN_ATTEMPT"
  exit 0
fi

if [[ -n "${LIVESPEC_COVERAGE_REUSE_TOKEN:-}" ]]; then
  printf 'explicit:%s\n' "$LIVESPEC_COVERAGE_REUSE_TOKEN"
  exit 0
fi

if ! root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  exit 1
fi

digest="$(
  {
    git -C "$root" rev-parse HEAD
    git -C "$root" diff --binary HEAD -- .
  } | sha256sum | awk '{ print $1 }'
)"
printf 'git-tree:%s\n' "$digest"
