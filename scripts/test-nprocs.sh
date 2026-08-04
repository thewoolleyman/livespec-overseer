#!/usr/bin/env bash
set -euo pipefail

if [[ "${LIVESPEC_CI_LANE:-local}" == "hosted" ]]; then
  printf '%s\n' auto
  exit 0
fi

if [[ -n "${LIVESPEC_TEST_PARALLELISM:-}" ]]; then
  printf '%s\n' "$LIVESPEC_TEST_PARALLELISM"
  exit 0
fi

cores="$(nproc 2>/dev/null || printf '%s\n' 4)"
workers=$((cores / 4))
if [[ "$workers" -lt 1 ]]; then
  workers=1
fi
printf '%s\n' "$workers"
