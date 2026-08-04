#!/usr/bin/env bash
set -euo pipefail

staged="$(git diff --cached --name-only --diff-filter=AM)"
py_staged="$(printf '%s\n' "$staged" | grep -E '\.py$' || true)"
test_staged="$(printf '%s\n' "$staged" | grep -E '^tests/.*\.py$' || true)"
impl_staged="$(printf '%s\n' "$staged" | grep -E '^overseer/.*\.py$' || true)"
test_count=0
impl_count=0
if [[ -n "$test_staged" ]]; then
  test_count="$(printf '%s\n' "$test_staged" | wc -l)"
fi
if [[ -n "$impl_staged" ]]; then
  impl_count="$(printf '%s\n' "$impl_staged" | wc -l)"
fi

if [[ -z "$py_staged" ]]; then
  echo ":: doc-only mode detected (zero .py files staged): running just check-pre-commit-doc-only"
  echo ":: pre-push + CI keep the full aggregate as the load-bearing safety net"
  just check-pre-commit-doc-only
  exit $?
fi

if [[ "$test_count" -eq 1 && "$impl_count" -eq 0 ]]; then
  echo ":: Red-mode shape detected: $test_staged"
  echo ":: skipping coverage gates (commit-msg replay hook is the verifier; coverage runs at Green amend)"
  LIVESPEC_CHECK_SKIP="check-coverage check-per-file-coverage" just check
  exit $?
fi

# Green-amend shape: impl staged while HEAD still carries Red-only trailers.
head_msg="$(git log -1 --format=%B 2>/dev/null || true)"
if [[ "$impl_count" -ge 1 ]] \
  && grep -q 'TDD-Red-Test-File-Checksum:' <<<"$head_msg" \
  && ! grep -q 'TDD-Green-Verified-At:' <<<"$head_msg"; then
  echo ":: Green-amend shape detected (impl staged; HEAD carries Red-only trailers)"
  echo ":: skipping no-arg check-red-green-replay (commit-msg replay hook verifies the Green amend)"
  LIVESPEC_CHECK_SKIP="check-red-green-replay" just check
  exit $?
fi

just check
