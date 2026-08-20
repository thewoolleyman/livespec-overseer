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

# ALLOWANCE, narrow and mechanical: a change whose every altered workflow line is
# one the automated lane can MECHANICALLY produce is permitted without a
# declaration. Two shapes qualify -- a PIN REFERENCE in any workflow file, and a
# canonical-slug line the CI-matrix reconciler writes into `ci.yml`.
#
# Why this exists: the automated pin-bump lane rewrites four workflow files on
# every sibling release, and it cannot author a declaration -- it runs from a
# reusable workflow in livespec-dev-tooling, out of this repo's reach. Binding
# the guard to CI without this would red that lane on every bump, which is an
# outage rather than a fix.
#
# Why it is not a hole: the allowance is keyed on the SHAPE of the diff, never on
# who authored it -- this guard cannot distinguish factory from host and must not
# pretend to. Any OTHER altered line -- a step, a trigger, a permission, a job, a
# job-level `needs` -- fails the allowance and requires a declaration, which is
# the entire class the guard exists to catch. Nothing here is an env var, a flag,
# or a skip lever; `.ai/ci-gate-discipline.md` forbids those absolutely and this
# allowance does not touch that prohibition.
#
# HOW THE SHAPES ARE DERIVED, which matters more than the shapes themselves.
# They are read off the PRODUCER'S WRITER SOURCE, never off observed diffs:
#
#   livespec-dev-tooling  cross_repo/ci_yaml_canonical_reconcile.py::_reconcile
#   livespec-dev-tooling  cross_repo/_ci_yaml_reconcile_parse.py
#                         ::matrix_anchor / ::batch_anchor / ::batch_line_for
#
# Reading the producer is the sanctioned cross-repo direction: this repo is a
# CONSUMER of livespec-dev-tooling (`.ai/no-circular-dependency.md`).
#
# DERIVING FROM OBSERVED DIFFS IS WHAT PRODUCED THE DEFECT THIS REPLACES. The
# previous rule was "every altered line is a pin reference", justified inline by:
#
#     Measured 2026-08-19/20 over the four most recent bumps (27404e6, a05cbb1,
#     cf916d5, 7d82d5d): every one alters ONLY these two line shapes.
#
# That sample was accurate and the inference was still void. Throughout that
# window the reconciler hard-failed every bump that had a canonical slug to adopt
# (livespec-s43svm.34), so a non-pin line was MECHANICALLY IMPOSSIBLE rather than
# merely unobserved. The rule recorded a symptom of an outage as if it were
# policy, outlived the outage, and then blocked the repaired behaviour: on the
# first wave after the fix (v1.29.3) this repo alone stayed four releases behind
# while the other seven Python consumers took the bump. A larger sample would not
# have helped -- every bump in that window was pin-only. Only reading the writer
# would have. Catalogued as `.ai/verifying-against-the-right-source.md` instance
# 34; the repair is `livespec-s43svm.36`.
aggregate_slug="check-aggregate-completeness"
ci_yaml=".github/workflows/ci.yml"

base_ref() {
  if git rev-parse --verify --quiet origin/master >/dev/null 2>&1; then
    printf 'origin/master'
  else
    printf 'HEAD'
  fi
}

base_ci_yaml() {
  git show "$(base_ref):${ci_yaml}" 2>/dev/null
}

# The bullet lines of the `matrix.target:` list that carries the aggregate slug,
# mirroring `matrix_anchor()` + `collect_entries()` in the producer: blank and
# `#`-comment lines are stepped over, and the first line that is neither a bullet
# nor blank/comment ends the list.
#
# EMPTY OUTPUT MEANS NO SUCH LIST, which is precisely the condition under which
# the producer falls back to its batched writer -- so this guard branches exactly
# where the writer branches. This repo has three `matrix.target:` lists and NONE
# of them carries the aggregate slug, so shape B below is inert here today and
# becomes live only if this repo's ci.yml gains such a list.
matrix_entry_lines() {
  awk -v agg="$aggregate_slug" '
    function flush(  i) {
      if (found) { for (i = 1; i <= n; i++) print buf[i]; exit }
      n = 0; found = 0; collecting = 0
    }
    collecting {
      if ($0 ~ /^[[:space:]]*$/ || $0 ~ /^[[:space:]]*#/) { next }
      if ($0 ~ /^[[:space:]]*-[[:space:]]*[A-Za-z0-9_-]+[[:space:]]*$/) {
        buf[++n] = $0
        tok = $0
        sub(/^[[:space:]]*-[[:space:]]*/, "", tok)
        sub(/[[:space:]]*$/, "", tok)
        if (tok == agg) { found = 1 }
        next
      }
      flush()
    }
    /^[[:space:]]*matrix:[[:space:]]*$/ { in_matrix = 1; next }
    in_matrix && /^[[:space:]]*target:[[:space:]]*$/ {
      collecting = 1; n = 0; found = 0; next
    }
  '
}

pin_reference_line() {
  local line="$1"
  [[ "$line" =~ ^[+-][[:space:]]*uses:[[:space:]]*[^[:space:]]+@v[0-9]+\.[0-9]+\.[0-9]+$ ]] && return 0
  [[ "$line" =~ ^[+-][[:space:]]*image:[[:space:]]*[^[:space:]]+:[a-z]+-v[0-9]+\.[0-9]+\.[0-9]+$ ]] && return 0
  return 1
}

# The consumer's wired canonical targets, mirroring the producer's
# `_wired_targets`: `check-targets.txt` is PRIMARY when present, and the
# justfile's `targets=(...)` array is consulted only in its absence. Read from
# the RESULTING tree, because a genuine bump adopts the slug into the justfile
# and into ci.yml in the same change.
wired_targets() {
  if [[ -f check-targets.txt ]]; then
    sed -E 's/#.*//; s/^[[:space:]]+//; s/[[:space:]]+$//' check-targets.txt \
      | grep -E '^check-[a-z0-9-]+$' || true
    return 0
  fi
  [[ -f justfile ]] || return 0
  awk '
    /targets=\(/ { inarr = 1; next }
    inarr && /^[[:space:]]*\)/ { inarr = 0; next }
    inarr {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      sub(/[[:space:]]+$/, "", line)
      if (line ~ /^check-[a-z0-9-]+$/) { print line }
    }
  ' justfile
}

# Is `slug` one the aggregate actually wires? The reconciler only ever mirrors
# slugs drawn from this set (`required = {slug for slug in targets ...}`), so a
# CI line naming anything else was not written by it.
slug_is_wired() {
  local slug="$1" t
  while IFS= read -r t; do
    [[ "$t" == "$slug" ]] && return 0
  done < <(wired_targets)
  return 1
}

# How many times `content` appears among the aggregate-bearing matrix list's
# entries on the given side ("head" = resulting file, "base" = origin/master).
matrix_entry_count() {
  local content="$1" src="$2" n=0 entry
  while IFS= read -r entry; do
    [[ "$entry" == "$content" ]] && n=$((n + 1))
  done < <(
    if [[ "$src" == "head" ]]; then
      [[ -f "$ci_yaml" ]] && matrix_entry_lines <"$ci_yaml"
    else
      base_ci_yaml | matrix_entry_lines
    fi
  )
  printf '%s' "$n"
}

# A line the canonical-CI reconciler can emit into ci.yml.
#
# ADDITIONS ONLY. Both writers exclusively INSERT; nothing in this allowance may
# authorise a REMOVAL. A check line disappearing from CI is precisely the class
# this guard exists to force review on, and an early draft accepted it because
# shape A tested only line content and never which side of the diff it was on.
# (A canonical RENAME can legitimately drop a matrix bullet; that case now needs
# a declaration, which is the correct trade -- a check leaving CI is worth one
# reviewed line.)
reconciler_emitted_line() {
  local line="$1" side content template slug expected
  side="${line:0:1}"
  content="${line:1}"
  [[ "$side" == "+" ]] || return 1

  # Shape B -- a `matrix.target:` list entry, written as `<indent>- <slug>` by
  # `_reconcile`.
  #
  # The BASE must already carry an aggregate-bearing target list. Without that
  # requirement a branch can inject the aggregate bullet into an unrelated
  # pre-existing matrix block, promoting it into "the" aggregate list on the head
  # side, and smuggle an arbitrary bullet into a job that runs
  # `just ${{ matrix.target }}`. The head list must also still contain every base
  # entry, so it is the SAME list extended rather than a different block.
  if [[ "$content" =~ ^[[:space:]]*-[[:space:]]*(check-[a-z0-9][a-z0-9-]*)[[:space:]]*$ ]]; then
    slug="${BASH_REMATCH[1]}"
    slug_is_wired "$slug" || return 1
    local base_entries head_entries entry
    base_entries="$(base_ci_yaml | matrix_entry_lines)"
    [[ -n "$base_entries" ]] || return 1
    [[ -f "$ci_yaml" ]] || return 1
    head_entries="$(matrix_entry_lines <"$ci_yaml")"
    while IFS= read -r entry; do
      [[ -z "$entry" ]] && continue
      printf '%s\n' "$head_entries" | grep -qxF -- "$entry" || return 1
    done <<<"$base_entries"
    # ...and the list itself must have GAINED this line. A `needs:` bullet can be
    # byte-identical to a real matrix entry, so mere membership is not enough.
    [[ "$(matrix_entry_count "$content" head)" -gt "$(matrix_entry_count "$content" base)" ]] || return 1
    return 0
  fi

  # Shape A -- a batched aggregate line, written by `batch_line_for` as the
  # consumer's OWN aggregate line with the aggregate slug substituted throughout.
  # The template is read from the BASE ci.yml, never the branch's, so a branch
  # cannot introduce a template that legitimises its own edits.
  template="$(base_ci_yaml | grep -F -- "just ${aggregate_slug}" | grep -vE '^[[:space:]]*#' | head -1)"
  [[ -n "$template" ]] || return 1
  [[ "$content" =~ just[[:space:]]+(check-[a-z0-9][a-z0-9-]*) ]] || return 1
  slug="${BASH_REMATCH[1]}"
  [[ "$slug" != "$aggregate_slug" ]] || return 1
  slug_is_wired "$slug" || return 1
  expected="${template//${aggregate_slug}/${slug}}"
  [[ "$content" == "$expected" ]] && return 0
  return 1
}

mechanical_only_change() {
  local diff
  diff="$(git diff --unified=0 origin/master...HEAD -- .github/workflows; git diff --unified=0 HEAD -- .github/workflows)"
  [[ -n "$diff" ]] || return 1
  local saw_content=1
  local line
  local current=""
  while IFS= read -r line; do
    case "$line" in
      +++*) current="${line#+++ b/}"; continue ;;
      ---*) continue ;;
      [+-]*) ;;
      *) continue ;;
    esac
    if pin_reference_line "$line"; then
      saw_content=0
      continue
    fi
    # The reconciler writes into ci.yml and nowhere else, so its shapes are
    # permitted there and nowhere else.
    if [[ "$current" == "$ci_yaml" ]] && reconciler_emitted_line "$line"; then
      saw_content=0
      continue
    fi
    return 1
  done <<<"$diff"
  return "$saw_content"
}

committed="$(git diff --name-only origin/master...HEAD -- .github/workflows)"
local_changes="$(git status --short -- .github/workflows)"
if [[ -n "$committed" || -n "$local_changes" ]]; then
  if mechanical_only_change; then
    exit 0
  fi
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
