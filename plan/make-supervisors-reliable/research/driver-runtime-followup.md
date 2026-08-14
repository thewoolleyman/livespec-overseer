# Driver runtime follow-up

## Purpose

`SPECIFICATION` v013 and the merged overseer realization establish the
supervisor state contract, but the actual fail-closed turn-completion control is
owned by the agent Driver. This note records the transfer boundary and the
current evidence required for a fresh planning session to continue it.

## Completed overseer-owned slice

- Plan epic: `overseer-ocj2yi`.
- Specification v013 was ratified in PR #891.
- The local realization item `overseer-ztekkk` merged in PR #896 after successful
  CI run 31762024122.
- The merged contract requires a structured `.supervisor-state`, declared
  terminal dispositions, independently verifiable wake producers, cold-open
  re-entry, and additive user messages while supervision remains active.

The implementation deliberately did not add semantic completion inference to
the overseer daemon. The daemon remains unable to infer completion from a pane
or final response.

## Remaining Driver-owned slice

The target is `/data/projects/livespec-driver-codex`. Its `livespec/hooks/`
directory is the shipped, self-contained Codex hook surface. The next item must
implement a Codex Stop hook that reads
`tmp/overseer/<topic>/.supervisor-state` and fails closed whenever active
supervision has missing, malformed, stale, or open-obligation state, an invalid
disposition, or unverified wake evidence. It may allow completion only for the
structured plan-complete case or one genuine maintainer-blocking question.

The hook must never inspect assistant final-response text or tmux pane text, and
it must not move semantic judgment into the overseer daemon. Its tests must
exercise the packaged installation shape as well as the marker/producers cases.

## Current transfer blocker

On 2026-08-14, filing this Driver item through the sanctioned
`capture-work-item` package failed before writing a record. The installed
orchestrator build's `WorkItem` model lacks `awaits_scope_override`, while its
writer unconditionally reads that attribute. The resulting
`AttributeError` means no Driver item identifier exists yet. Do not hand-write a
replacement ledger record; refresh or repair the orchestration package/schema
pair, then re-run the standard capture flow and its Definition-of-Ready routing.

## Next action

Restore a compatible `capture-work-item` implementation for
`livespec-driver-codex`, file the bounded Stop-hook work item with the acceptance
above, and drive it through that repository's normal factory and PR gates. Then
append its resulting item id and disposition to `overseer-ocj2yi` before deciding
whether this plan is complete.
