# Goal 3 — verifying the briefs are mirrored

Measurement pass against `plan/supervisor-scratch-discipline/handoff.md` goal 3,
run 2026-08-05. The audit note (`what-was-in-tmp-supervisor.md`) asserted the 18
briefs were "mostly mirrored" from knowledge, not measurement, and expected a
nonzero unmirrored count. This note supplies the actual measurement.

## Count discrepancy, confirmed first

`tmp/supervisor/briefs/` holds exactly **16** files on this machine —
`brief-01.md` through `brief-13.md`, then `brief-15.md`, `brief-16.md`,
`brief-17.md`. `brief-14.md` and `brief-18.md` do not exist. Verified directly
(`ls`), not inferred. Whether they were ever created, were removed since the
2026-07-28 audit, or the "18" count was itself a mismeasurement is not
determinable from what's on disk now — this note states only what is
verifiable: 16 present, 2 numbers in the sequence absent.

## Per-brief trace

Each of the 16 present briefs was read, its load-bearing content identified,
and checked against the ledger, tracked files, git history, and other plan
threads for a durable landing spot.

| brief | topic | verdict | citation |
|---|---|---|---|
| 01 | ground-truth deltas (PR #21, ledger readability) + marketplace-hosting prep | mirrored | `plan/archive/ship-overseer-to-fleet/handoff.md` (PR #21 closed correction; marketplace registration) |
| 02 | two hard edges (2→3, 3→4); anti-stall "armed re-entry"; `.9` scaffold fold-in | mirrored | `.claude-plugin/prose/supervise-plan.md` ("armed re-entry"); `overseer-hbr.9` reason (PR #115); `overseer-3wt` closed |
| 03 | file 13 slices as `overseer-hbr` children w/ hand-set deps; doc corrections | mirrored | `overseer-hbr.1`–`.25` (25 children, all done); handoff.md "fully stale", "3→4" hard edge |
| 04 | build S8/S9 registry mapping; groom decisions | mirrored | `overseer-hbr.17`, `.18` done; registry 54/0 TODO |
| 05 | `overseer-fitvmo` supersession correction; lifecycle-status defect | mirrored | `overseer-fitvmo.close_reason`; `overseer-byvxlp` done; `plan/archive/supervisor-prompt-quality/` |
| 06 | `.19` gate verification; mutation-exposure measurement | mirrored | `overseer-hbr.22` reason (705/712 Phase-0 WARN, sized not fixed) |
| 07 | workflow changeset prep; non-workflow file fixes | mirrored | `release-please-config.json`, `.mise.toml`, `lefthook.yml`; changeset itself already disposed per `what-was-in-tmp-supervisor.md` |
| 08 | module-document sweep; `.16` ownership correction | mirrored | `tests/test_module_docs_match_the_repo.py`; `overseer/AGENTS.md`; `overseer-xbxkrv` done |
| 09 | 4 ripe valves (`.19` accept, `.20` approve, `xbxkrv` close-dup, `.16` status repair) | mirrored | all four done/closed with the described evidence |
| 10 | `.19` raw-close w/ refusal quote; workflow-ownership correction | mirrored | `overseer-hbr.19` reason carries the literal `accept:` refusal quote |
| 11 | land 5 workflow files | mirrored | all 5 present in `.github/workflows/` on master |
| 12 | "blocking-only" autonomy rubric (maintainer quote) | mirrored | `.claude-plugin/prose/supervise-plan.md`; `plan/archive/ship-overseer-to-fleet/supervisor-handoff.md` |
| 13 | close `.11`/`.12`/`.20` on forge evidence; verify `.14` pin propagation | mirrored | `overseer-hbr.11`, `.12`, `.14`, `.20` done |
| 15 | ship sequence `.16→.13→.15→.14`; generator content list | mirrored | `overseer-hbr.13`–`.16` done; generator content confirmed present |
| 16 | mid-wrap-up interruption lesson ("declare state before anything else"); `.13`/`.15` continuation | mirrored | `overseer/_supervisor_nudge.py`; 4 plan-thread docs; `overseer-hbr.13`–`.16` done |
| 17 | new plan thread (codex parity); the near-loss `/plan <slug>` strict-resume lesson | mirrored | `plan/archive/codex-parity-and-rollout-safety/supervisor-handoff.md` §Corrections, names "Brief 17" directly |

**Result: 16 of 16 present briefs are mirrored. 0 unmirrored.**

## This contradicts the handoff's stated expectation, and that's the finding

Goal 3's acceptance text says "a nonzero answer is the expected outcome, not a
failure." The measured answer is zero. Re-reading `what-was-in-tmp-supervisor.md`
§1, the "one already known" case it points to — brief-17's near-loss — turns out
not to be an unmirrored case either: its ending is that the lesson *survived*
(landed in `supervisor-handoff.md` §Corrections), by luck rather than by rule.
So the expectation of nonzero was itself unmeasured, same as the "mostly
mirrored" claim it followed.

The actual finding is orthogonal to the mirrored/unmirrored count: every one of
the 16 briefs still on disk traces to a real ledger disposition, a tracked
file, or a merged-and-archived plan thread. The audit's underlying worry —
content dying silently in `tmp/` — did not materialize for any brief that
survived to be measured. Two things stay open from this exercise:

1. The brief-14/brief-18 count discrepancy is unexplained by anything
   verifiable on this machine.
2. This clean result is exactly why goal 2's mechanical enforcement still
   matters: convention worked here, on this machine, for these 16 briefs — but
   the whole thread exists because convention is not guaranteed to hold, and a
   clean sample of 16 is not evidence that it always will.

Goal 3 is complete: measured, not assumed.
