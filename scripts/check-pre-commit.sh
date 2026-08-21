#!/usr/bin/env bash
set -euo pipefail

staged="$(git diff --cached --name-only --diff-filter=AM)"
py_staged="$(printf '%s\n' "$staged" | grep -E '\.py$' || true)"
test_staged="$(printf '%s\n' "$staged" | grep -E '^tests/.*\.py$' || true)"
test_count=0
if [[ -n "$test_staged" ]]; then
  test_count="$(printf '%s\n' "$test_staged" | wc -l)"
fi

union_skip_targets() {
  LIVESPEC_EXISTING_SKIP="${LIVESPEC_CHECK_SKIP:-}" LIVESPEC_REQUIRED_SKIP="$*" uv run python - <<'PY'
import os

from overseer.pre_commit_gate import union_skip_targets

print(
    union_skip_targets(
        existing=os.environ.get("LIVESPEC_EXISTING_SKIP", ""),
        required=os.environ.get("LIVESPEC_REQUIRED_SKIP", "").split(),
    )
)
PY
}

if [[ -z "$py_staged" ]]; then
  echo ":: doc-only mode detected (zero .py files staged): running just check-pre-commit-doc-only"
  echo ":: pre-push + CI keep the full aggregate as the load-bearing safety net"
  just check-pre-commit-doc-only
  exit $?
fi

impl_staged="$(
  LIVESPEC_STAGED_PATHS="$staged" uv run python - <<'PY'
import os
from pathlib import Path

from livespec_dev_tooling.checks.commit_pairs_source_and_test import (
    derive_source_prefixes,
    is_vendored_path,
)
from livespec_dev_tooling.config import load_config

prefixes = derive_source_prefixes(config=load_config(repo_root=Path(".")))
for staged_path in os.environ.get("LIVESPEC_STAGED_PATHS", "").splitlines():
    if (
        staged_path.endswith(".py")
        and staged_path.startswith(prefixes)
        and not is_vendored_path(rel_path=Path(staged_path))
    ):
        print(staged_path)
PY
)"
impl_count=0
if [[ -n "$impl_staged" ]]; then
  impl_count="$(printf '%s\n' "$impl_staged" | wc -l)"
fi

if [[ "$test_count" -eq 1 && "$impl_count" -eq 0 ]]; then
  echo ":: Red-mode shape detected: $test_staged"
  echo ":: skipping coverage gates (commit-msg replay hook is the verifier; coverage runs at Green amend)"
  LIVESPEC_CHECK_SKIP="$(union_skip_targets check-coverage check-per-file-coverage)" just check
  exit $?
fi

# Green-amend shape: impl staged while HEAD still carries Red-only trailers.
head_msg="$(git log -1 --format=%B 2>/dev/null || true)"
if [[ "$impl_count" -ge 1 ]] \
  && grep -q 'TDD-Red-Test-File-Checksum:' <<<"$head_msg" \
  && ! grep -q 'TDD-Green-Verified-At:' <<<"$head_msg"; then
  echo ":: Green-amend shape detected (impl staged; HEAD carries Red-only trailers)"
  echo ":: skipping no-arg check-red-green-replay (commit-msg replay hook verifies the Green amend)"
  LIVESPEC_CHECK_SKIP="$(union_skip_targets check-red-green-replay)" just check
  exit $?
fi

just check
