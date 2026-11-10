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
# never valid" contract. Scope that authoring verdict to entries changed
# since HEAD, as the canonical dev-tooling caller does; unrelated existing
# TODOs are still reported, and release workflows retain the full scan.
# The full aggregate remains the safety net at
# pre-push and in CI.
echo ":: doc-only subset: repo-state checks for non-.py input surfaces"
just check-heading-coverage
just check-claude-md-coverage
just check-comment-line-anchors
just check-agents-ai-references-resolve
just check-plan-anchor-declared
just check-vendor-manifest
# Capture the writer's output first: a `grep -q` reader that exits on its first match
# would close the pipe early and, under pipefail, report the match as a failure.
staged_paths="$(git diff --cached --name-only)"
if grep -qx 'tests/heading-coverage.json' <<<"$staged_paths"; then
    echo ":: staged changeset edits tests/heading-coverage.json — arming the TODO-ownership release tier for entries this commit authors"
    LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST=true \
        LIVESPEC_SCOPE_HEADING_COVERAGE_TODOS_TO_HEAD_DIFF=true \
        just check-no-todo-registry
else
    just check-no-todo-registry
fi
