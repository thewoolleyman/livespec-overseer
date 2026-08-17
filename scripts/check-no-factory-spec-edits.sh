#!/usr/bin/env bash
set -euo pipefail

# overseer-57f2 half (i), maintainer-ratified 2026-08-17: factory-authored
# commits must never touch SPECIFICATION/. No escape hatch — a marker hatch
# would be spoofable by the very pipeline being guarded. Spec changes route
# through propose-change -> independent review -> revise; factory spec work
# waits on the pipeline-level fix (bd-ib-2x16, orchestrator tenant).
#
# The range is origin/master..HEAD, so post-merge master runs see an empty
# range and pass; enforcement happens on PR branches via the ci-green
# aggregate and inside the factory sandbox's own `just check`.

offending="$(git log origin/master..HEAD --author='<noreply@fabro\.sh>' --format='%h %ae %s' -- SPECIFICATION/)"

if [[ -n "$offending" ]]; then
  {
    echo "Factory-authored commits must not touch SPECIFICATION/ (overseer-57f2)."
    echo "Spec changes route through propose-change -> independent review -> revise;"
    echo "factory spec work waits on bd-ib-2x16."
    echo
    echo "Offending commits (author noreply@fabro.sh touching SPECIFICATION/):"
    echo "$offending"
  } >&2
  exit 1
fi
