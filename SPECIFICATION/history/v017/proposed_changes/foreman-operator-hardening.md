---
topic: foreman-operator-hardening
author: foreman-improvements
created_at: 2026-08-18T21:30:04Z
---

## Proposal: Foreman relay-and-escalation evidentiary discipline

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Five operator discipline rules, learned from a live 2026-08-18 incident where a consensus-panel verdict was relayed to a worker with no corroborable record and a reasonable corroboration request was misread as an authority challenge, become ratified requirements on the foreman operator role rather than living only in a session handoff file.

### Motivation

A consensus panel ran to a unanimous verdict for a worker whose row was 'working' (a prose question, not a picker); the foreman-consensus journaling path that would have recorded it could not run for a prose-question panel, so the verdict was relayed as an unattributed paste. The worker correctly refused to act on an unverifiable assertion and asked for a corroborated journal entry or a direct instruction; the foreman misread this as an authority challenge, escalated on a paraphrase that dropped the actual data request, and the track stalled for hours through repeated STILL alerts the foreman explained away without re-examining. These failure modes recur unless the operator role itself is bound by ratified rules, not by whichever handoff file a given foreman session happens to have read.

### Proposed Changes

Add to SPECIFICATION/spec.md, in the section governing the foreman operator's relay and escalation behavior, five normative rules:

1. EVIDENCE-CARRYING RELAYS. Any relay from the foreman that asserts a panel outcome MUST embed the full record in its first delivery to the worker: every reviewer verdict with its rationale verbatim, the evaluator's outcome/reason/cache_key, and an on-disk path the worker can independently read. An attributed summary alone does not satisfy this requirement.
2. VERBATIM-QUOTE RULE. When the foreman classifies or escalates a worker's response, it MUST quote the worker's exact words in the escalation rather than paraphrasing them.
3. AUTHORITY-CHALLENGE GATE. Before the foreman treats a worker's pushback as an authority challenge, it MUST first determine whether the pushback can be satisfied with data the foreman already possesses or can produce; a request for corroborating evidence or data is NEVER, by itself, an authority challenge, and MUST NOT be escalated as one.
4. STILL-ALERT RE-READ RULE. A "STILL alert" is the daemon's report-only `pane-still` attention condition (a tracked session's pane content observed unchanged past the daemon's stillness bound while its row does not read idle). Two consecutive STILL alerts on the same tracked session MUST force the foreman to take a fresh pane capture and re-classify the session's state, rather than relying on any standing explanation it has already formed for the idleness. Separately, no standing explanation for an idle or still-alerted track remains valid unexamined past 30 minutes; the foreman MUST re-verify it by that point regardless of alert count.
5. ARMED-MECHANISM VALIDITY. A monitor or watch the foreman relies on is a valid mechanism only while its target is confirmed alive; because a daemon bounce can invalidate a pane- or process-scoped watch silently, any watch the foreman establishes MUST key on re-resolvable identity (e.g. a pane title) plus an explicit signal that detects a bounce (e.g. a daemon instance identifier), never on a bare pane or process identifier alone.

Add corresponding scenarios to SPECIFICATION/scenarios.md illustrating each rule's triggering condition and required foreman behavior, in the style of the existing foreman scenarios (e.g. 'A stale foreman heartbeat is surfaced as attention').

## Proposal: Non-blocking human-decision escalation for the foreman operator loop

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md
- SPECIFICATION/contracts.md

### Summary

The foreman operator contract currently permits a blocking human-decision picker to freeze the foreman's entire supervision loop indefinitely, because the foreman's own tick only proceeds while its REPL is idle; this proposal requires escalations that need a human decision to use a non-blocking pattern by default, reserving a blocking picker only for a bounded wait.

### Motivation

A blocking AskUserQuestion escalation with no answer froze the foreman's entire operator loop for approximately 12 hours on 2026-08-18, stalling supervision of every OTHER track under that foreman, not only the track whose question triggered the escalation. The foreman's cron-driven tick only fires while its own REPL is idle, so a single unanswered blocking picker is a single point of failure for the whole fleet the foreman supervises.

### Proposed Changes

Add to SPECIFICATION/spec.md a requirement that when the foreman needs a human decision it cannot make itself, it MUST default to a non-blocking escalation: the affected track becomes a new membership condition on the daemon's EXISTING mechanical attention surface (never a parallel, foreman-private status), and the foreman schedules a bounded re-check rather than blocking its own loop on an open-ended picker. The exact delivery channel for alerting a human (e.g. a push notification) is an implementation choice for contracts.md/AGENTS.md, not a spec-level requirement. A blocking picker MAY be used only as a last resort and only for a bounded wait with a defined timeout, after which the escalation reverts to the non-blocking form. This requirement applies to the FOREMAN's own decision-surfacing behavior only.

HARD CONSTRAINT (must be stated explicitly in the spec text): this requirement does not alter, in any way, who or what may authorize a restart of a tracked session. The cardinal rule -- that a session is restarted only when it declares itself ready via its own state file -- is completely unaffected; this proposal changes only how a human decision gets surfaced to the operator or maintainer.

Add a corresponding scenario to SPECIFICATION/scenarios.md: a blocking human-decision escalation with no answer must not prevent the foreman from continuing to tick and supervise every other track.
