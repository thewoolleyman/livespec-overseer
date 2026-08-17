#!/usr/bin/env bash
set -euo pipefail

# Doc-only pre-commit subset (work-item livespec-dev-tooling-yilyxr.10,
# mirroring dev-tooling PR #1459): previously a no-op, so zero-.py
# changesets ran nothing locally and repo-state breakage surfaced only in
# CI. Runs the cheap repo-state checks whose input surfaces are the files
# a doc-only changeset can touch. check-no-todo-registry stays in its
# per-commit warn-only tier EXCEPT when the staged changeset itself edits
# tests/heading-coverage.json: authoring an unowned TODO entry is refused
# (release tier armed) per the check's own "an unowned TODO entry is
# never valid" contract. The full aggregate remains the safety net at
# pre-push and in CI.
echo ":: doc-only subset: repo-state checks for non-.py input surfaces"
just check-heading-coverage
just check-claude-md-coverage
just check-comment-line-anchors
just check-agents-ai-references-resolve
just check-plan-thread-anchor-declared
just check-vendor-manifest
if git diff --cached --name-only | grep -qx 'tests/heading-coverage.json'; then
    echo ":: staged changeset edits tests/heading-coverage.json — arming the TODO-ownership release tier for this commit"
    LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST=true just check-no-todo-registry
else
    just check-no-todo-registry
fi
