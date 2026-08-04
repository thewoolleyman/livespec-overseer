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

if uv run python -m livespec_dev_tooling.green_token check 2>&1; then
  echo ":: pre-push: green token matched - tree byte-identical to last green check; skipping full aggregate (CI is authoritative)"
  exit 0
fi

just check
