#!/usr/bin/env bash
set -euo pipefail

declaration=".livespec-workflow-edit-exemption"

line_count() {
  sed '/^$/d' | wc -l | tr -d ' '
}

declared_value() {
  local key="$1"
  local lines
  lines="$(grep -E "^${key}=" "$declaration" || true)"
  if [[ "$(printf '%s\n' "$lines" | line_count)" != "1" ]]; then
    return 1
  fi
  printf '%s\n' "${lines#*=}"
}

valid_declaration() {
  if [[ ! -f "$declaration" ]]; then
    echo "Missing workflow edit exemption declaration: $declaration" >&2
    return 1
  fi
  if ! git ls-files --error-unmatch "$declaration" >/dev/null 2>&1; then
    echo "Workflow edit exemption declaration must be tracked: $declaration" >&2
    return 1
  fi
  # The declaration must be authored BY THIS CHANGE, not inherited from master.
  # A declaration lands on master alongside the workflow edit it exempted, so a
  # file-existence test would let that first legitimate use disable the guard
  # permanently: every later branch would inherit a valid declaration and every
  # later workflow edit would pass having declared nothing. Requiring the
  # declaration in this branch's own diff (or staged/unstaged, for the pre-commit
  # moment) keeps one exemption bound to one reviewed change.
  local declared_here
  declared_here="$(git diff --name-only origin/master...HEAD -- "$declaration")"
  local declared_pending
  declared_pending="$(git status --short -- "$declaration")"
  if [[ -z "$declared_here" && -z "$declared_pending" ]]; then
    echo "Workflow edit exemption declaration is inherited, not authored by this change." >&2
    echo "An exemption is per-change: add or update $declaration in this branch." >&2
    return 1
  fi

  local work_item
  local reason
  if ! work_item="$(declared_value "work_item")"; then
    echo "Workflow edit exemption declaration must contain exactly one work_item= line." >&2
    return 1
  fi
  if ! reason="$(declared_value "reason")"; then
    echo "Workflow edit exemption declaration must contain exactly one reason= line." >&2
    return 1
  fi
  if [[ ! "$work_item" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "Workflow edit exemption work_item must be a single ledger id token." >&2
    return 1
  fi
  if [[ -z "$reason" ]]; then
    echo "Workflow edit exemption reason must be non-empty." >&2
    return 1
  fi

  # The work_item value is documentary by design here. This shell guard stays
  # offline and auditable; ledger-id liveness belongs to the shared resolver.
  return 0
}

committed="$(git diff --name-only origin/master...HEAD -- .github/workflows)"
local_changes="$(git status --short -- .github/workflows)"
if [[ -n "$committed" || -n "$local_changes" ]]; then
  if valid_declaration; then
    exit 0
  fi
  {
    echo "GitHub workflow file changes require a tracked exemption declaration."
    echo "Declaration file: $declaration"
    echo "Required fields: work_item=<ledger-id> and reason=<reviewable reason>"
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
