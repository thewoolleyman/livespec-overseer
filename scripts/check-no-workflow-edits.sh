#!/usr/bin/env bash
set -euo pipefail

committed="$(git diff --name-only origin/master...HEAD -- .github/workflows)"
local_changes="$(git status --short -- .github/workflows)"
if [[ -n "$committed" || -n "$local_changes" ]]; then
  {
    echo "Factory branches must not modify .github/workflows/."
    if [[ -n "$committed" ]]; then
      echo
      echo "Committed workflow changes:"
      echo "$committed"
    fi
    if [[ -n "$local_changes" ]]; then
      echo
      echo "Local workflow changes:"
      echo "$local_changes"
    fi
  } >&2
  exit 1
fi
