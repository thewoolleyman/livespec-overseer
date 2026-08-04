#!/usr/bin/env bash
set -euo pipefail

if [[ -f .coverage ]]; then
  echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
  uv run coverage report --fail-under=100
else
  echo ":: check-coverage: no .coverage data file (CI standalone job); running the suite"
  uv run pytest -n "$(scripts/test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
fi
