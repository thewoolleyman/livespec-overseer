#!/usr/bin/env bash
set -euo pipefail

run_plan_anchor_metadata_check() {
  if ! command -v with-livespec-env.sh >/dev/null 2>&1; then
    echo ":: pre-push: with-livespec-env.sh not found; plan-anchor metadata check remains unarmed" >&2
    return 0
  fi
  echo ":: pre-push: running plan-anchor metadata check under credential wrapper"
  # Both assignments MUST sit inside the wrapper invocation, as arguments to `env`.
  # The wrapper's stage-1 hop is an `exec env -i` with a short allowlist, so anything
  # assigned as a PREFIX on it is discarded before the command runs. Measured on this
  # host: assigned as a prefix the lever is ABSENT downstream; assigned here it arrives.
  # PATH is passed for the same reason -- the wrapper hands down
  # /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin, which has no `just`,
  # so a prefix-form call exits 127 and `set -e` aborts every push on this host.
  with-livespec-env.sh -- env \
    PATH="$PATH" \
    LIVESPEC_STRICT_PLAN_ANCHOR_METADATA=true \
    just check-plan-anchor-metadata
}

run_plan_anchor_metadata_check

# PR gate ≡ master gate (livespec plan pr-gate-master-parity R3, livespec-citqsd):
# pre-push runs the FULL `just check` unconditionally. The prior zero-.py branch,
# which delegated a doc-only push to the check-pre-commit-doc-only subset, is
# retired — it was the local mirror of the ci.yml `detect-py-changes` skip this
# plan removes, and it let a doc-only push run fewer gates than master.
echo ":: pre-push: arming LLOC soft-warning release tier; running full just check"
failure_log="$(mktemp)"
trap 'rm -f "$failure_log"' EXIT

if ! LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=true just check \
  2> >(tee "$failure_log" >&2); then
  echo ":: pre-push: failing diagnostics reported by the gate:" >&2
  if ! grep -E '"failing"[[:space:]]*:[[:space:]]*true' "$failure_log" >&2; then
    echo ":: pre-push: no structured failing=true diagnostics found in gate stderr" >&2
  fi
  exit 1
fi
