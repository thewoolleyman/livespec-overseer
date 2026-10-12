---
topic: terminal-done-declaration
author: claude-opus-5-5
created_at: 2026-10-12T08:06:53Z
---

## Proposal: A terminal done declaration for sessions whose work is complete

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add a fourth session-written state value, `done`, meaning 'my work is complete, I want nothing further, do not restart me'. It never authorizes a restart, suppresses every wrap-up (compaction-latched included) and the keep-going nudge with no freshness window, is voided only by the same generating-past-grace evidence that voids `blocked:`, and renders as a quiet non-attention row whether its session is running or has exited. The wrap-up names it as the finished-work declaration.

### Motivation

A supervised session that has finished its work has no honest declaration (work-item overseer-efi5p6). `ready` authorizes a restart nobody wants, so the successor resumes a closed or archived plan; `blocked:` alerts the operator forever; `winding-down` on a LIVE session goes stale after fifteen minutes and the wrap-up escalation resumes; and `idle-with-context-left` is daemon-owned and must never be forged. overseer-x29.1 (closed 2026-08-03) named this gap as 'the missing terminal token: complete, parked, nothing wanted, do not restart' but scoped it out. The 2026-09-12 ruling (overseer-esvzyp) keeps archived-plan sessions supervised until their runtime exits, so archiving does not end it either. Observed 2026-10-12: session caam-spend-cap-servability archived its plan and closed its epic, and its only options were a winding-down that would go stale or a ready that would restart it into a closed plan. The maintainer approved adding the token on 2026-10-12.

### Proposed Changes

Amend spec.md §"Out-of-band state declaration" and add a new section §"The terminal declaration" immediately after §"Wind-down expiry on context recovery". Amend every enumeration of the session-written values elsewhere in spec.md to the four values.

1. In §"Out-of-band state declaration", replace "There are exactly three values a session writes — `ready`, `blocked: <one-line reason>`, and `winding-down` —" with "There are exactly four values a session writes — `ready`, `blocked: <one-line reason>`, `winding-down`, and `done` (optionally `done: <one-line summary>`) —". Replace "declining all three does not buy a reprieve" with "declining all four does not buy a reprieve".

2. In §"The supervision round", the round-opening predicate's list of declarations that prevent a round MUST include `done`: the pane MUST NOT be "carrying `blocked:`, `ready`, `done`, or a fresh `winding-down`". In the recovered-round closure's guard, the parenthetical list of session-written tokens that hold the round open MUST read (`ready`, `blocked`, `winding-down`, `done`).

3. In §"The escalating wrap-up", every wrap-up MUST tell the session "the exact state-file path and the four values it may write", and MUST name `done` as the declaration to write when its work is finished and it wants nothing further. The expiry-notice MUST likewise restate the four values. In §"The stalled-picker charter reminder", "one of the three values a session may write" becomes "one of the four values a session may write".

4. New section §"The terminal declaration", normative text:

"A session whose work is COMPLETE — its plan finished, archived, or otherwise ended, and nothing further wanted from it — MUST be able to say so honestly. It does so by writing `done` (optionally `done: <one-line summary>`) to its own state file. `done` means: my work is complete, I want nothing further, do not restart me. It is the terminal declaration, and the daemon MUST honour it as a valid session declaration, never as a malformed one.

A standing `done` declaration MUST NOT authorize a restart under any circumstances: it is not `ready`, it can never certify against a round, and it never raises or lowers a certification floor. The daemon MUST NOT restart a track holding `done`, however low its remaining context falls and however long it stays idle.

While `done` stands, the daemon MUST NOT paste a wrap-up to that track at any escalation band — including a band owed because of a compaction latch, whose durable record the declaration leaves untouched — MUST NOT send it the keep-going nudge, and MUST NOT report it as not responding. Unlike `winding-down`, `done` has no freshness window: it does not go stale with age, and no amount of time alone resumes the escalation.

`done` is voided by exactly the evidence that voids a `blocked:` declaration and by nothing else: the session observed actively GENERATING — not merely running a background command at its prompt — past the same two-minute grace measured from the declaration's own modification time, where the latest pane input was not injected by a peer. Generating is incompatible with having finished; it means the session was handed more work. The void clears the DECLARATION ONLY: it MUST NOT raise a certification floor, delete the round's durable record, reset its notified bands, or otherwise close the round. After a void the track is supervised exactly as an undeclared track is, so a resumed session below its wind-down threshold receives the ordinary wrap-up.

A session that is handed new work after declaring `done` MUST clear its own `done` declaration — by deleting or overwriting its own state file — BEFORE resuming work, so no window exists in which it is working while still asserting it wants nothing. The daemon-side void is the backstop for a session that does not.

Live gate evidence still outranks `done`: a session showing an open structured picker is waiting on a human whatever it declared, and MUST be surfaced as such.

The operator surface MUST render a track holding `done` as a QUIET row — a distinct `done` status that is NOT a NEEDS YOU attention member, does not count toward the attention badge, and is never coloured as broken — both while its session is still running and after its session has exited. An exited session holding `done` MUST NOT be reported as `session-gone`; its row MUST say the session has exited. A `done` declaration standing on a track whose session has exited is an orderly ending, exactly as a `winding-down` one is."

Scenarios to add to scenarios.md (each linked from tests/heading-coverage.json; until the implementation item overseer-gzdk lands they carry `test: "TODO"` with `work_item: "overseer-gzdk"`):

- "## Scenario: A done declaration is valid and never restarts the session" — Given a session that wrote `done` to its state file, and whose remaining context is at or below the danger line, When the daemon observes the track settled and idle for any length of time, Then the declaration is not surfaced as malformed, And the daemon never restarts the session.
- "## Scenario: A done declaration suppresses every wrap-up" — Given a track holding `done` whose remaining context crosses its threshold and every lower band, including a compaction-latched round, When the daemon observes the track, Then no wrap-up is pasted, And the track is not reported as not responding.
- "## Scenario: A done declaration suppresses the keep-going nudge" — Given a track holding `done` that is idle above its threshold for longer than the nudge floor, When the daemon observes the track, Then no keep-going nudge is sent.
- "## Scenario: A done session that resumes generating has its declaration voided" — Given a track holding a `done` declaration older than the two-minute grace, When the daemon observes the session actively generating, Then the declaration is voided without raising a certification floor or closing the round, And the track is thereafter supervised as undeclared. And Given the same session merely running a background command at its prompt, Then the declaration stands.
- "## Scenario: A done track renders as a quiet row whether running or exited" — Given one track holding `done` whose session is running and another holding `done` whose session has exited, When the daemon renders its table, Then both render the quiet `done` status outside NEEDS YOU, And neither is reported as `session-gone`.
- "## Scenario: The wrap-up names done as the finished-work declaration" — Given a track that crosses its wind-down threshold with nothing declared, When the daemon pastes the wrap-up, Then the wrap-up lists all four session values And names `done` as the declaration to use when the work is finished and nothing further is wanted.

## Proposal: Wire contract for the done state-file value

### Target specification files

- SPECIFICATION/contracts.md

### Summary

State `done` in the state-file table and contract rules: its writer and meaning, its voiding rule (mirroring `blocked:` voiding, declaration-only, no floor, round untouched), the absence of any age-based staleness, and its effect on the wrap-up injection, the keep-going nudge, and the attention surface.

### Motivation

A supervised session that has finished its work has no honest declaration (work-item overseer-efi5p6). `ready` authorizes a restart nobody wants, so the successor resumes a closed or archived plan; `blocked:` alerts the operator forever; `winding-down` on a LIVE session goes stale after fifteen minutes and the wrap-up escalation resumes; and `idle-with-context-left` is daemon-owned and must never be forged. overseer-x29.1 (closed 2026-08-03) named this gap as 'the missing terminal token: complete, parked, nothing wanted, do not restart' but scoped it out. The 2026-09-12 ruling (overseer-esvzyp) keeps archived-plan sessions supervised until their runtime exits, so archiving does not end it either. Observed 2026-10-12: session caam-spend-cap-servability archived its plan and closed its epic, and its only options were a winding-down that would go stale or a ready that would restart it into a closed plan. The maintainer approved adding the token on 2026-10-12.

### Proposed Changes

Amend contracts.md §"The state file".

1. Add a row to the state-file table, after `blocked: <one-line reason>`:

| `done` (optionally `done: <one-line summary>`) | session | "My work is complete; I want nothing further; do not restart me." The terminal declaration. Never a restart authorization; suppresses every wrap-up and the keep-going nudge while it stands. |

2. After "The normal sequence is two writes: …", add: "A session whose work is complete MAY instead end with `done` rather than `ready`; it MUST then expect no restart."

3. Add contract rules:

- "`DONE` VOIDING, independent of the ready-side expiry and governed by the same evidence as `blocked:`-side voiding. A `done` declaration MUST be voided only when the session is observed actively GENERATING past the two-minute grace measured from the declaration's own modification time, and MUST NOT be voided on a background-command observation, an idle observation, a peer-injected input, or any age alone. The void clears the DECLARATION ONLY: the daemon MUST NOT delete the round's sidecar key, MUST NOT reset its notified bands, MUST NOT otherwise close the round, and MUST NOT raise the certification floor."
- "A `done` declaration has no freshness window. It MUST NOT be expired, staled, or treated as absent on account of its age."

4. In §"The wrap-up injection", every wrap-up MUST list the four session values and MUST NOT be pasted to a track holding `done`. In §"The keep-going nudge", the nudge MUST NOT be sent to a track holding `done`, and its text MUST name `done` as the declaration for a session whose work is finished.

5. In §"Attention surface", a track holding `done` — running or exited — MUST NOT be an attention member and MUST render the quiet `done` row status; an exited one MUST NOT render `session-gone`.
