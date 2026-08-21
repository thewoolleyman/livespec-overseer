#!/usr/bin/env bash
set -euo pipefail

mapfile -t staged < <(
  git diff --cached --name-only --diff-filter=AM |
    grep -E '\.py$' |
    grep -Ev '(^|/)_vendor/' ||
    true
)
if [[ "${#staged[@]}" -eq 0 ]]; then
  exit 0
fi

uv run ruff check --fix --exit-zero "${staged[@]}"
uv run ruff format "${staged[@]}"
git add "${staged[@]}"
