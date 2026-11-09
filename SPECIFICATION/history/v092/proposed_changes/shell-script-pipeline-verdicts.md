---
topic: shell-script-pipeline-verdicts
author: claude:fleet-flaky-tests
created_at: 2026-11-09T18:43:37Z
---

## Proposal: A pipefail script judges a pipeline only from a reader that drains its input

### Target specification files

- SPECIFICATION/non-functional-requirements.md
- SPECIFICATION/scenarios.md

### Summary

Add a `## Shell script pipeline verdicts` section to non-functional-requirements.md, mirroring livespec-dev-tooling's ratified rule of the same name. A `set -o pipefail` script of this repository judges a pipeline's success only from a reader that consumes its whole input, never from an early-exiting reader such as `grep -q` or `head -n 1`, and gives the same verdict on an input larger than a pipe buffer as on a small one. Add the matching scenario to scenarios.md.

### Motivation

overseer-ng3b3w, the livespec-overseer share of the fleet pipefail sweep (plan fleet-flaky-tests, epic livespec-dev-tooling-zwveqp), was refused at the R316 launch-time Definition of Done preflight at 2026-11-09T18:31:31Z: "The reference line 'References: ## The isolated live exercise' does not govern either assertion". No heading of this spec governs pipe correctness in repository shell scripts. "## The isolated live exercise" covers only overseer-live-exercise.sh's namespace behaviour, so at most 2 of the 4 sites; non-functional-requirements.md "## Spec" covers hermetic tests; constraints.md "## Determinism boundary" covers the daemon. The four sites, from livespec-dev-tooling's sweep matcher over origin/master 303e7c18ce: scripts/check-pre-commit-doc-only.sh:24 (`git diff --cached --name-only | grep -qx ...`), scripts/overseer-live-exercise-codex-herdr.sh:487 (`pane_capture ... | grep -qF ...`), scripts/overseer-live-exercise.sh:141 (`sed -n ... | head -n 1`) and :234 (`find ... -print -quit | grep -q .`). Under pipefail an early-exiting reader closes its pipe before the writer finishes; the writer takes SIGPIPE and a match reads as a failure, only under load, so it presents as a flake. livespec-dev-tooling ratified this rule for itself (non-functional-requirements.md "## Shell script pipeline verdicts", worded "every shell script this repository ships"), so a consumer inherits nothing from it; the orchestrator's share cited its own "## Provisional fleet launch scripts". legacy-coordinator-agent accepted this repository-local mirror (option b). Under its rule K the end state is fleet-wide: a separate livespec core propose-change, filed after this one at a low band, will carry the rule for later fleet members. It does not block this proposal or overseer-ng3b3w, whose References line is repointed to the new heading once this is ratified.

### Proposed Changes

In SPECIFICATION/non-functional-requirements.md, insert the following section immediately before `## Scenarios`:

```markdown
## Shell script pipeline verdicts

Every shell script this repository ships or runs in its tests, in whichever directory it lives, that runs with `set -o pipefail` MUST judge a pipeline's success only from a reader that consumes the pipeline's whole input. A pipeline whose exit status the script uses MUST NOT end in a reader that can exit before its writer finishes — `grep -q`, `grep --quiet`, `grep -m N`, `head -n N`, `head -c N`, or an `awk` program that calls `exit` — because under `pipefail` the writer's SIGPIPE (exit 141) turns a match into a failure. Where only a membership test is wanted, the script SHOULD use a here-string (`grep -q PAT <<<"$var"`), a reader that drains its input (`grep PAT >/dev/null`), or a grouping whose status excludes the writer's. Such a script MUST give the same verdict on an input larger than a pipe buffer (64 KiB) as on a small one. A pipeline whose status the script does not use, or one that runs where `pipefail` is off, is out of scope. Scenario: "A pipefail script reports a match in a large input as a match".
```

In SPECIFICATION/scenarios.md, append the following scenario at the end of the file:

```markdown
## Scenario: A pipefail script reports a match in a large input as a match

Given a shell script of this repository that runs with `set -o pipefail` and tests whether its input contains a pattern

When the input contains the pattern near its start and is larger than 64 KiB

Then the script MUST report the pattern as present

And its verdict MUST be the same as for a 200-byte input that contains the pattern
```

The revise that ratifies this proposal adds one `## ` heading to each file. It MUST add `tests/heading-coverage.json` entries for both in the same change: the non-functional-requirements.md heading and the scenario heading, each a spec-first `TODO` whose `reason` acknowledges an owed integration-tier test, with `"work_item": "overseer-ng3b3w"`, registered in the repository's heading-coverage debt register if it keeps one.
