# foreman-autonomy-hardening — opening research note, 2026-08-20

Plan record discipline: the ledger is authoritative over this directory; plan
state, next action, and handoffs live on the ledger anchor `overseer-vx4ky3`
read through the plan timeline.

## Problem

The 2026-08-20 maintainer investigation of the stalled livespec-dev-tooling
fleet (report: https://claude.ai/code/artifact/264f5d4f-6aec-4795-8431-b6adaa6a4dd6 ,
measured against foreman session transcripts, `tmp/overseer/foreman/panel/` in
livespec-dev-tooling, and this repo's foreman modules) found the foreman skill
stalls whole repos by escalating work it is mechanically unable to do:

1. The actuator whitelist (`overseer/foreman_act_types.py`) has no ledger
   mutation beyond `work_item_file` — no priority edit, no comment, no epic —
   so every routed ledger request becomes a maintainer escalation.
2. `foreman-consensus` is an evaluator only: it requires `--reviewer-responses`
   and nothing in the plugin produces them, while `prose/foreman.md` claims the
   panel is convened "via foreman-consensus". One session improvised reviewer
   subagents (2026-08-19 04:16Z, livespec-dev-tooling foreman transcript); the
   next session correctly concluded reviewers were unobtainable and froze.
3. Panel output is confined to the same eleven action ids with `human_valve`
   excluded, so even a unanimous panel cannot authorize a ruling.
4. `blocked_session_answer` demands consensus evidence even when the picker
   option is the plan's own ledger-recorded next action (rop-railway picker,
   parked 16h on its own recorded next action).
5. `hard-tick-budget` cancels the cron and raises a resume picker: 13 hours
   with no foreman on 2026-08-19/20.
6. Tick reports re-argue a standing "still yours" list every tick.

## Children (filed on the anchor as ready work items)

1. Foreman ledger actions: `work_item_update` (priority, parent),
   `work_item_comment`, `foreman_epic_create` — same revalidation + journal.
2. A convenable panel: a `foreman-panel` step that produces reviewer_responses
   for the pinned identities and invokes `foreman-consensus`; request builder
   refuses verdict-hinting question text; prose corrected.
3. Panel verdict vocabulary: a unanimous panel may authorize a typed ruling
   (answer picker option N, set priority, adopt a named basis, re-parent a
   plan child); floors unchanged; spec amendment routed via propose-change.
4. Recorded-next-action rule: `blocked_session_answer` without a panel when
   the option text matches the newest handoff's single next action.
5. Auto-resume with backoff on `hard-tick-budget`; no resume picker.
6. Tick-report discipline in the prose: standing items listed once by id,
   route-before-escalate, no contract-refusal boilerplate.
7. Seat-model measurement: run foreman seats on claude-sonnet-5 in a bounded
   window; compare pickers, escalation-phrase rate, mutations per tick, cost.

## Route

In-session worker (this repo's product `.py` + prose + SPECIFICATION are the
targets; child 3 is spec-touching and rides propose-change → revise, which the
maintainer authorized to run autonomously on 2026-08-20). Factory dispatch
allowed for children that are pure `.py`+prose once acceptance is set.

## Out of scope (explicit deferrals)

- Daemon row-truth defects (absent foreman rows, wrong session states) —
  already tracked as overseer-y4ty and neighbours.
- Any change to the cardinal restart rule in overseer/marker-protocol.md.
- Fleet-wide model routing beyond the child-7 measurement.
