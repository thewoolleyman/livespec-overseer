#!/usr/bin/env bash
set -euo pipefail

# Three dots: diff against the MERGE-BASE, so commits that arrived on master
# after this branch forked are not attributed to the push.
changeset="$(git diff --name-only origin/master...HEAD)"
py_changed="$(printf '%s\n' "$changeset" | grep -E '\.py$' || true)"
if [[ -z "$py_changed" ]]; then
  echo ":: doc-only push detected (zero .py changes vs the origin/master merge-base): running check-pre-commit-doc-only"
  just check-pre-commit-doc-only
  exit $?
fi

echo ":: pre-push: Python changes detected - arming LLOC soft-warning release tier"
LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=true just check
