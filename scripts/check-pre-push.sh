#!/usr/bin/env bash
set -euo pipefail

# Three dots: diff against the MERGE-BASE, so commits that arrived on master
# after this branch forked are not attributed to the push.
changeset="$(git diff --name-only origin/master...HEAD)"

run_plan_anchor_metadata_check() {
  if command -v with-livespec-env.sh >/dev/null 2>&1; then
    echo ":: pre-push: running plan-anchor metadata check under credential wrapper"
    # PATH is re-declared INSIDE the wrapper invocation on purpose. The wrapper
    # re-execs through `sudo` + `env -i` with a short allowlist, so a caller's
    # PATH does not survive the hop: on a host where `just` and `uv` come from
    # mise shims rather than a system prefix, the wrapper hands the check a
    # PATH of `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`
    # and the recipe dies with `env: 'just': No such file or directory`, exit
    # 127, before the check ever runs. Setting it after the scrub — the same
    # shape the GitHub-App installation pin needs — is what makes this gate
    # REACHABLE, which is the property the check exists to have. A sandbox or
    # CI image with a system-wide `just` never sees this and so never caught it.
    LIVESPEC_STRICT_PLAN_ANCHOR_METADATA=true \
      with-livespec-env.sh -- env \
        PATH="$PATH" \
        LIVESPEC_STRICT_PLAN_ANCHOR_METADATA=true \
        just check-plan-anchor-metadata
  else
    echo ":: pre-push: with-livespec-env.sh not found; plan-anchor metadata check remains unarmed" >&2
  fi
}

run_plan_anchor_metadata_check

py_changed="$(printf '%s\n' "$changeset" | grep -E '\.py$' || true)"
if [[ -z "$py_changed" ]]; then
  echo ":: doc-only push detected (zero .py changes vs the origin/master merge-base): running check-pre-commit-doc-only"
  just check-pre-commit-doc-only
  exit $?
fi

echo ":: pre-push: Python changes detected - arming LLOC soft-warning release tier"
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
