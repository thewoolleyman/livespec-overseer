# Supervisor Handoff - daemon-liveness-truth (TERMINAL)

## STOP. THIS TRACK IS COMPLETE AND ARCHIVED. THERE IS NOTHING TO SUPERVISE.

You were handed this path by a respawn prompt. That prompt is stale by design —
it names a fixed path, and this thread archived on **2026-08-03**. This file
exists ONLY so that prompt resolves to something true instead of a missing file.

**Do not resume this thread. Do not invent work for it. Do not adopt its
successors.** Your correct action is at the bottom of this file and it is short.

The real thread now lives at **`plan/archive/daemon-liveness-truth/`** — both
records (`handoff.md`, `supervisor-handoff.md`) and the research note moved
there. Read them if you want history; nothing there is pending.

## What this track delivered, so you can recognise it as finished

Epic `overseer-x29` and all four children are CLOSED.

| child | what it was | outcome |
|---|---|---|
| `overseer-j1r` | a live, in-tmux, working track reported the alarming `session-gone` | fixed, PR #468 |
| `overseer-mkx` | a deliberately torn-down track stayed red forever | fixed, PR #477 |
| `overseer-oydugu` | rung 3 had no executable gate at all | built, PR #521 |
| `overseer-x29.1` | the cardinal contract did not describe the meaning PR #477 gave `winding-down` | documented, PR #545 |

Both daemon fixes shipped in `v0.16.1` and were verified running in the live
daemon — not merely merged, not merely released.

## Three findings this track paid for, each contradicting a premise it started with

1. **The two original defects did NOT share a root.** The epic argued both came
   from the declaration-vocabulary gap. For `overseer-j1r` that was wrong: the
   root was registry-name PROVENANCE (`nameSource: derived`), nothing to do with
   tokens or declarations.
2. **`overseer-mkx`'s own account of its symptom was wrong.** It claimed a
   torn-down track rendered as *hung mid-wrap-up*; `alert_non_responder` needs a
   LIVE pane at danger context, so a gone session never reaches it. The real
   symptom was `session-gone`, forever.
3. **`overseer-oydugu`'s central premise was false, and that is what unblocked
   it.** The item and charter correction C20 both describe the answering turn as
   *"prose, question marks, no picker"* — the control a naive detector would
   wrongly flag, and the stated reason the slice sat `blocked: needs-human`.
   Measured: the answering prose and the `AskUserQuestion` call share one
   `message.id`. One message. The hazard was inferred from rendered text and
   never measured against the record.

## The limit this track did NOT close, stated rather than dropped

**The rung-3 gate's RECALL is unmeasured and cannot be measured from its
corpus** — exactly one true positive exists. Precision is 1/1 against ten true
negatives, and it was exercised once against a live out-of-corpus transcript, but
a violation phrased without a signposting heading is invisible to it by
construction. It is a precision-first first cut, to be widened in writing when a
new positive is recorded — never by loosening the pattern until something passes.

**Live Stop-hook wiring was deliberately not built.** Repo-wide wiring adds a
production seam and worker-pane blast radius beyond the item's fixture-based
acceptance, on n=1 evidence. That remains open ground for whoever records the
second positive.

**And `winding-down` now carries two meanings**, disambiguated by liveness. The
maintainer took that trade deliberately on 2026-08-03: a session that declared
`winding-down` and then genuinely CRASHED is permanently indistinguishable from
one that finished cleanly. Do not "fix" that blind spot without re-opening the
decision recorded on `overseer-x29.1`.

## Where surviving work went — none of it is yours

Nothing from this track was left unhomed. The two dispatch hazards it measured
(a queued fabro run evicted before executing, leaving a phantom `active`/`fabro`
claim; and the stale-plugin-build trap) are recorded in the repo's own
`AGENTS.md`, not carried here.

## Your correct action

Report that this track is complete and archived, then stand down. Do not start
work. If you were respawned into this pane, say so plainly and stop.
