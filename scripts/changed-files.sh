#!/usr/bin/env bash
set -euo pipefail

# `grep` exits 1 on zero matches; an empty changed set is normal.
{
  git diff --name-only origin/master...HEAD
  git diff --cached --name-only --diff-filter=AM
} | { grep -E '\.py$' || true; } | sort -u
