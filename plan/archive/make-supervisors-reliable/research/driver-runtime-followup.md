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

## Routed Driver work

On 2026-08-14, the bounded Driver item was filed as
`livespec-driver-codex-yx5rve` — **Enforce structured supervisor completion in
the Codex Stop hook** — and passed its Definition-of-Ready routing as `ready`.

The first capture attempt raised `AttributeError` because a direct Python
invocation loaded the Driver checkout's older `livespec_runtime` instead of the
orchestrator bundle's vendored runtime. Re-running the sanctioned capture
package with its bundled runtime resolved the model/writer pairing and wrote the
item normally. This was an invocation import-path issue, not an outstanding
package/schema repair. Do not create a duplicate replacement item.

## Next action

Drive `livespec-driver-codex-yx5rve` through
`livespec-driver-codex`'s normal factory and PR gates. Before any retry, inspect
the factory run history and its publish branch/PR. After landing, append the PR,
CI verification, and closed item disposition to `overseer-ocj2yi` before
deciding whether this plan is complete.
