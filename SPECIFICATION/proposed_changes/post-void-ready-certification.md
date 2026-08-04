---
topic: post-void-ready-certification
author: claude-opus-5
created_at: 2026-08-04T15:52:54Z
---

## Proposal: Voiding a declaration MUST NOT close the supervision round

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The ratified text names exactly one event that closes a supervision round — the restart — but the daemon also closes a round when it voids a stale `ready`, deleting the round's durable key and resetting its notified escalation bands. That single divergence causes TWO independent ratified-rule violations: it destroys the round record a later declaration needs in order to certify, and it defeats the escalation spam-proofing that spec.md §"The escalating wrap-up" ratifies, by manufacturing a fresh round on every void. The second is a defect in its own right, verifiable from the daemon log without reference to any certification question. This finding states, normatively, that voiding a declaration clears the DECLARATION ONLY and MUST NOT delete the round's durable record or reset its bands. It is a DIVERGENCE from already-ratified text and needs no new contract.

**This finding MUST NOT be implemented on its own.** It removes an unintended but load-bearing backstop, and the proposal "A fresh ready written after a void certifies against the void floor" in this same file is what replaces it. The binding sequencing constraint, and the failure it prevents, are stated at the end of this finding's Proposed Changes.

### Motivation

spec.md §"The supervision round" says the round "closes when the daemon restarts the session — which deletes the state file and the round's stamp together". contracts.md §"The state file" says the daemon "DELETES the file as it restarts the session, together with the round's stamp". contracts.md §"Durable stores" says "closing a round deletes the key entirely, so no round datum outlives its round". scenarios.md §"Scenario: A fresh ready declaration triggers the atomic restart" is the only scenario in which the stamp is deleted. Against that, every ratified statement of the void — scenarios.md §"Scenario: A ready declaration is voided when its session resumes work", spec.md §"The restart", and contracts.md §"The state file" stale-declaration-voiding bullet — speaks of the DECLARATION alone and says nothing about the round. The shipped prose agrees: overseer/marker-protocol.md describes round clearing only on the restart path.

The daemon nonetheless closes the round on a void, and the path is exact: overseer/_supervisor_state.py:63-64 (void_if_stale, past the 120s grace) calls clear_state; overseer/_supervisor_state.py:45 (clear_state) calls registry.clear_injection_stamp; overseer/_registry_stamps.py:174-194 deletes the whole sidecar key, both the round timestamp and the notified bands. It is reached from overseer/_supervisor_busy.py:100 and overseer/_supervisor_blocked.py:73. clear_injection_stamp's own docstring says it is "Called by the daemon when it restarts a track", so the void diverges from the function's stated contract as well as from the spec.

**First violation — escalation spam-proofing is defeated, and this one stands alone.** spec.md §"The escalating wrap-up" ratifies that each band "fires at most once per round" and that the notified set is durable so "a daemon restart never re-sends a band already sent". contracts.md §"The wrap-up injection" repeats it. Because each void deletes the key, a session that oscillates between declaring `ready` and resuming work is re-warned indefinitely: every void manufactures a fresh round, and every band below the current context level fires again. Measured on the livespec-overseer `foreman` track, 2026-08-03: 41 wrap-up injections and 39 voids alternating on a roughly two-and-a-half-minute period between 06:57:00Z and 08:52:59Z, with zero restarts ever recorded for that track. One command over tmp/overseer/daemon.log reproduces it:

    grep "injected wrap-up into <repo>::foreman" tmp/overseer/daemon.log | sed 's/.*bands //' | sort | uniq -c

It returns 23 occurrences of [50, 40, 30], 8 of [50, 40, 30, 20], 6 of [50, 40], and 4 of [50] — 41 lines, and band 50 appears in every one of them.

The lemma that makes those counts evidence is NO-REPEAT, not no-shrink. Each logged set is that paste's DUE set — the bands crossed and NOT yet notified — so within a single round the logged sets legitimately shrink as bands are consumed, and a shrink proves nothing. What cannot happen within one round is a band appearing in TWO due sets, because notifying it removes it from every later due computation. Band 50 appearing in 41 consecutive due sets therefore requires at least 40 resets of the notified set, which is to say at least 40 round closes with no restart among them. This violation needs no certification argument to stand: a supervised session was keystroked forty-one times where the ratified ceiling for a round is five.

**Second violation — the round record a later declaration needs is destroyed.** This is the one that produces the deadlock this thread was opened for, and it is argued in the finding on the certification floor below.

The same measurement corrects a premise this project reasoned from for a time: the failure was believed to be BAND EXHAUSTION, a round whose bands had all fired and could not re-arm. The evidence shows the opposite — bands reset on every void and were never exhausted.

### Proposed Changes

Amend `SPECIFICATION/spec.md` §"The supervision round". After the existing sentence naming the restart as the round close, the specification MUST state that the restart is the only event that closes a DELIVERED round, and that no other daemon behavior — voiding a declaration included — MAY delete such a round's durable record or reset its notified escalation bands.

That clause MUST carve out the un-opening of a round whose wrap-up never landed, and the carve-out is a fail-closed requirement rather than an exemption. A round is OPENED speculatively: the stamp is recorded before the message is pasted, so that a declaration answering the wrap-up is always newer than it. When that opening paste FAILS, no wrap-up was delivered and there is no round for any declaration to answer. The daemon MUST therefore delete the stamp it just wrote, leaving the track un-rounded, and MUST NOT leave a standing round behind an undelivered message. Without this carve-out the clause above would forbid an existing mechanism and leave a stamp with no wrap-up behind it, against which any `ready` — a handoff convention, a state file inherited from a predecessor, an unprompted write by a session that was never told to declare — would certify and authorize a kill. That is the same class this file's finding on the certification floor refuses, and the round-close clause MUST NOT re-admit it.

The distinction the specification MUST draw is between a round that was DELIVERED and one that was merely attempted: only a delivered round is closed by the restart alone; an undelivered one is un-opened immediately and is never a round at all.

Amend `SPECIFICATION/contracts.md` §"The state file", stale-declaration-voiding bullet. It MUST state that voiding clears the DECLARATION only: the daemon MUST delete the state file and MUST NOT delete the round's sidecar key, MUST NOT reset its notified bands, and MUST NOT otherwise close the round. The same requirement applies to both voiding rules — the `ready` void past the grace and the `blocked:` void on observed generating evidence — because both currently take the same round-closing path.

The ORDER of the void's two steps MUST be specified rather than left to an implementation, because the two orderings fail in opposite directions across a crash. The daemon MUST record the void instant (per the certification-floor finding below) BEFORE deleting the state file. A crash between the two then leaves a raised floor and a surviving declaration, which fails closed; the reverse order leaves a deleted declaration and no floor, which is harmless only until the delete itself fails. A failed floor record MUST be surfaced to the operator and MUST NOT abort the delete attempt.

Only the `ready` void raises the certification floor. A `blocked:` void MUST NOT raise it: a `blocked:` token can never certify a restart under any circumstances, so raising a floor on its account would be a durable write with no authorization consequence, and leaving that unstated invites two implementations with different sidecar contents and different test expectations.

Amend `SPECIFICATION/contracts.md` §"Durable stores", the round-sidecar bullet. The sentence "Opening a round resets its bands; closing a round deletes the key entirely" MUST be qualified so that key deletion is tied to the restart specifically rather than to any round-ending event, and it MUST state that a voided declaration leaves the key in place.

Amend `SPECIFICATION/scenarios.md` §"Scenario: A ready declaration is voided when its session resumes work". It MUST gain two outcome lines: that the round's durable record survives the void, and that the round's already-notified escalation bands are NOT reset, so a band already sent is not re-sent merely because a declaration was voided.

A new scenario MUST be added to `SPECIFICATION/scenarios.md` pinning the observed spam defect directly:

    ## Scenario: Repeated voiding never re-sends an already-notified band

    Given a session that repeatedly declares ready and then resumes work below its threshold

    When each declaration is voided past the grace

    Then no escalation band already notified in the open round is sent again

    And the round's durable record and notified bands survive every void

The corresponding `tests/heading-coverage.json` link MUST be added atomically with the new scenario, per `non-functional-requirements.md` §"Scenarios".

Nothing in this finding changes what a void does to the DECLARATION: a `ready` older than the two-minute grace observed on a busy or gated tick MUST still be cleared, and a younger one MUST still survive its own turn's busy tail.

**Binding sequencing constraint: this finding MUST NOT be implemented unless the certification floor introduced by the finding "A fresh ready written after a void certifies against the void floor" lands in the SAME change.** The two are not independent findings that merely happen to be ordered. Implemented alone, this finding is a REGRESSION in the interlock's failure mode, even though each finding is individually correct.

The reason is a backstop that is undocumented and unintended, but real. Today a void does two things: it deletes the state file, and it closes the round. The first is fail-soft by ratified design — spec.md §"Fail-soft posture" requires that "a storage error on the overseer's own files is reported and survived, never raised out of the supervision loop", and the daemon accordingly logs a failed unlink and continues. The second currently rescues the first: because the round is closed regardless, a declaration that survives its own voiding cannot certify against anything, and the interlock's first precondition fails.

Remove the round close alone, and that rescue disappears. A declaration whose delete failed still carries a modification time LATER than the round-open stamp, because it was written during that round — so it satisfies every precondition and authorizes a restart. The daemon would then honor a declaration it had already voided, which is exactly what scenarios.md §"Scenario: A ready declaration is voided when its session resumes work" and spec.md §"The restart" forbid: such a declaration MUST be "voided rather than honored later". The window is not narrow. The void runs only on a busy or gated observation, so a failed delete gets further attempts only while the pane stays busy; the moment the session goes idle, the surviving declaration takes the restart path directly.

To be precise about what does and does not break, because the distinction matters to a reviewer checking this claim: this does NOT produce two kills from one declaration. The restart closes the round on its own ratified path, so no further certification follows. What it produces is a single kill authorized by a declaration the daemon had already determined to be false — a session killed at a moment it never asserted was safe.

The certification floor removes the dependency entirely. With the floor raised to the instant of the void, a surviving declaration fails precondition 3 by construction, because it necessarily predates its own voiding. Deletion becomes a hygiene measure rather than a correctness mechanism, which is the property that makes these two findings safe together and unsafe apart. An implementation MUST therefore treat them as one unit of work, and any work-item decomposition MUST NOT split them across separately-landing changes.

## Proposal: A report-only attention membership MUST NOT suppress the below-threshold branch

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

spec.md §"Fail-soft posture" already forbids a report-only attention membership from suppressing an independently qualified escalation-band wrap-up, and the daemon violates that rule for the uncertifiable-declaration member by evaluating it ahead of the below-threshold branch, which makes that branch unreachable. This finding states the rule in a form that binds the ORDER of evaluation rather than only the authorization, and separately closes a same-section divergence in which the wrap-up paste predicate is looser than its ratified terms. Both are DIVERGENCES from already-ratified text and need no new contract. This finding also records a sequencing constraint that a naive fix would get wrong.

### Motivation

spec.md §"Fail-soft posture" says of the report-only attention memberships: "They do not suppress an independently qualified escalation-band wrap-up under §'The supervision round'; that wrap-up is authorized by its own complete predicate, never by the attention condition." scenarios.md §"Scenario: An undeclared session at the danger line is reported, never restarted" carries the same rule for the danger member: "But it does not suppress an independently qualified escalation-band wrap-up." contracts.md §"Attention surface" lists "a track carrying a standing declaration that cannot certify past its bounded floor" as one of those report-only members.

The daemon violates that rule for exactly that member. In overseer/_supervisor_evaluate_idle.py the `ready-uncertifiable` branch at lines 97-100 precedes the below-threshold branch at lines 121-132, which is the branch that reaches the wrap-up injection. Once the declaration passes the fifteen-minute attention floor (CONDITION_CONTINUITY_GAP, overseer/_supervisor_config.py:143) the below-threshold branch becomes unreachable for as long as that declaration stands UNREWRITTEN, because its age only grows. The suppression is not unconditional: the surface keys its age on the declaration file's own modification time (overseer/_supervisor_liveness.py:147-149), so a session that REWRITES `ready` resets the age below the floor and re-opens the below-threshold branch for another fifteen minutes. That detail matters for diagnosis, because it means the observed `foreman` capture was held by the shell-evidence predicate rather than by branch ordering during those windows — the two blockers bind at different times, and attributing every tick to the ordering defect would misdescribe the failure. The ordering defect is nonetheless real and is what makes a standing untouched declaration a permanent dead end. The attention condition is doing precisely what the ratified sentence forbids: suppressing the branch rather than letting the branch's own predicate decide. The branch arrived with the v004 uncertifiable-declaration-attention work (commit 5c54cb7), so the change that was authored to REPORT the dead end is what made it permanent.

The rule as written is not wrong, but it is stated as an authorization property ("never authorized by the attention condition") and the defect is an ORDERING property ("the branch is never reached"). An implementation can satisfy the letter while violating the intent, which is what happened. It needs to bind evaluation order.

Separately, and in the opposite direction, contracts.md §"The wrap-up injection" says the pane "MUST NOT be ... carrying `blocked:` or `ready`" and that "an uncertifiable `ready` remains report-only and is not pasted into". The daemon applies that exclusion only when shell evidence is present: overseer/_supervisor_threshold.py:98-100 treats the RAW `ready` token as disqualifying only in the shell-only case, and otherwise consults the certifiable-ready predicate, which is false when no round is open. So a non-shell track carrying an uncertifiable `ready` IS pasted into, contrary to the ratified sentence.

That second divergence carries a sequencing hazard worth recording explicitly, because it inverts the usual reasoning. The unratified permissiveness is currently the only reason this deadlock is rare rather than universal: on a non-shell track the wrap-up fires inside the fifteen-minute window, wakes the session, and the session re-declares against the newly written stamp and restarts. Tightening the paste predicate to match the ratified letter WITHOUT the certification path proposed separately in this same file would remove that escape and make the deadlock apply to every supervised track. The two changes are therefore ordered, not independent.

### Proposed Changes

Amend `SPECIFICATION/spec.md` §"Fail-soft posture". The existing sentence stating that report-only memberships do not suppress an independently qualified escalation-band wrap-up MUST be strengthened to bind evaluation order as well as authorization: a report-only attention membership MUST NOT be evaluated in a position that prevents the below-threshold branch from being reached, and the ONLY thing that may suppress a wrap-up is the wrap-up's own complete paste predicate under §"The supervision round". The section MUST name the standing-uncertifiable-declaration member specifically as bound by this rule, since that is the member for which the ordering property is load-bearing.

The same section MUST state that a track's rendered status MAY reflect a report-only membership while the below-threshold branch still runs its own reporting and its own predicate evaluation — surfacing a dead end and evaluating the wrap-up are independent obligations, and satisfying the first MUST NOT discharge the second.

Amend `SPECIFICATION/contracts.md` §"The wrap-up injection". The `ready` exclusion in the paste predicate MUST be stated as applying uniformly to ANY `ready` token on disk — certifiable or not, and regardless of whether background-shell evidence is present or absent, and regardless of runtime. The daemon MUST NOT keystroke over a standing declaration. The section MUST also record that this uniform exclusion depends on the post-void certification path existing: an implementation MUST NOT tighten this predicate before that path is in place, because doing so removes the only route by which a track carrying an uncertifiable declaration currently recovers without a person.

**The tightening also has a residual that MUST be stated rather than discovered, because it is a REGRESSION against shipped behavior for one class of track.** The certification floor reaches only a track that has been in a round: a declaration standing on a track with neither an injection stamp nor a recorded void — a state file inherited from an out-of-band predecessor, a lost sidecar, an unprompted convention write — gets no floor, deliberately. Today such a track SELF-HEALS when it carries no background-shell evidence, because the looser predicate pastes a wrap-up within each fifteen-minute window, the session re-declares against the fresh stamp, and it restarts. After the uniform exclusion, that track can never open a round, never certify, and — because the exclusion suppresses every paste — receives NO further escalation-band warnings while its remaining context runs to exhaustion. The specification MUST name this outcome, MUST require the track be surfaced as attention for as long as it stands, and MUST NOT describe the state as self-healing.

A scenario MUST be added to `SPECIFICATION/scenarios.md` pinning that residual:

    ## Scenario: A declaration on a track that was never in a round is surfaced, not healed

    Given a track whose state file declares ready

    And the track has neither an injection stamp nor a recorded void

    When the daemon observes the track below its wind-down threshold

    Then no wrap-up is pasted, because the pane carries a standing declaration

    And the declaration certifies nothing, because the track has no certification floor

    And the track is surfaced to the operator for as long as the declaration stands

The corresponding `tests/heading-coverage.json` link MUST be added atomically with the new scenario, per `non-functional-requirements.md` §"Scenarios".

Two scenarios MUST be added to `SPECIFICATION/scenarios.md`:

    ## Scenario: A standing uncertifiable declaration does not suppress the below-threshold branch

    Given a track below its wind-down threshold carrying a ready declaration that cannot certify

    And the declaration has stood past the attention floor

    When the daemon evaluates the track

    Then the track is surfaced as carrying a declaration that cannot certify

    And the below-threshold branch is still evaluated on its own terms

    And any suppression of the wrap-up comes from the paste predicate, never from the attention membership

    ## Scenario: A pane carrying a standing declaration is never pasted into

    Given a track below its wind-down threshold whose state file declares ready

    When the wrap-up paste predicate is evaluated

    Then no wrap-up is pasted into that pane

    And the outcome is the same whether or not background-shell evidence is present

The corresponding `tests/heading-coverage.json` links MUST be added atomically with the new scenarios, per `non-functional-requirements.md` §"Scenarios".

Nothing in this finding authorizes any act. Every membership named here remains report-only, and a fresh session-written `ready` remains the sole restart authorization.

## Proposal: A fresh ready written after a void certifies against the void floor

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

This is the genuinely UNRATIFIED half of this change, and the question the plan thread exists to answer: whether a session whose declaration was voided may ever certify a later one without a new wrap-up. It proposes that voiding RAISE the round's certification floor to the instant of the void, so that certification remains the same timestamp comparison it already is, and a declaration written strictly after the void certifies without requiring a new round. The voided declaration itself can never satisfy that floor, because its modification time necessarily precedes its own voiding — so the one-declaration-one-kill guarantee holds by construction rather than by deleting the round.

### Motivation

Today a session whose `ready` is voided has no mechanical route back to a restart. Certification requires an injection stamp (contracts.md §"The restart interlock", precondition 1); a stamp is written only when a wrap-up injects; and contracts.md §"The wrap-up injection" forbids pasting into a pane that carries a standing `ready`. So once a declaration stands, no new round can open for it to answer, and the session can re-declare forever without effect. Observed on the livespec-overseer `foreman` track: the session declared sincerely at approximately 2026-08-03T20:04Z, was reported at 20:19:04Z as "ready cannot certify (15m): no supervision round open" and again at 00:04:06Z as "(4h)", and sat in the attention block at seventeen percent remaining context until a person intervened.

spec.md §"Fail-soft posture" already anticipates the SHAPE of this state — it says a track "can sit in a state in which no supervision round can open" and MUST be surfaced — but it enumerates the causes it foresaw: "a busy classification that never ends, a standing `blocked:` declaration, an alternation between the two". This cause is not among them, and the asymmetry is the argument. Each of those three is a state the session can LEAVE by its own action: stop being busy, retract the block. This one it cannot leave, because it has already done the only thing the cardinal rule accepts — it declared. Surfacing is the correct response to a session that will not act; it is the wrong response to a session that has acted and cannot be heard.

The change is closer to the ratified letter than it may read. Certification is ALREADY a timestamp comparison rather than an abstract test of whether a round is open: scenarios.md §"Scenario: A ready declaration from a prior round never restarts" turns on a declaration "whose modification time predates this round's injection stamp". "Written after the void" is the same KIND of test the interlock already performs, against a different floor. What the interlock guards against is the REUSE of one declaration to authorize a second kill, not the existence of a newer sincere one.

The guarantee holds by construction, which is the property that makes this safe rather than merely convenient. A declaration is voided only after it has stood past the grace, so the voided declaration's modification time is necessarily EARLIER than the instant of its voiding. Raising the floor to that instant therefore disqualifies the voided declaration permanently, using the same comparison that certifies its successor. No deletion is required to prevent the replay, which is why this supersedes the cruder alternative of simply not closing the round: leaving the floor at the original round-open stamp would let an arbitrarily old declaration certify, degrading the interlock to "newer than the first-ever injection" — the exact hazard the sidecar's round-scoping exists to prevent.

Scoping matters and is deliberate. A track that has never been in a round has no floor of either kind, so a bare `ready` written outside any round — a handoff convention, an unprompted write, a forged one — still certifies nothing. This proposal does not create a general "a session may request its own restart" affordance; it restores certification only on a track that already participated in the protocol and was voided for a condition that has since ceased to apply.

**That scoping MUST be stated as a property of the TRACK, not of the declarer, because the floor cannot distinguish them and it would be false to claim otherwise.** A void record is evidence that a wrap-up was delivered to that track and answered on it. It is NOT evidence that the session declaring today is the session that received it. The gap is reachable and is documented as occurring in this fleet: a supervised session replaced OUT-OF-BAND — hand-restarted, cleared, or respawned after a crash — leaves its successor occupying the same pane under the same derived name, inheriting the predecessor's state-file directory, and passing the full identity gate. The successor writes `ready` after the predecessor's void instant, certifies against a floor established by a wrap-up it never received, and is killed at whatever context it holds. Under shipped behavior the first void closes that window by deleting the round record; under this proposal nothing but a restart closes it.

The remedy is NOT a new principle. `contracts.md` §"The restart interlock" already ratifies the right one — "a declaration authorizes the restart of the session that wrote it, never of whatever session later occupies that pane" — and holds the restart when the observed identity "has changed since the `ready` was first seen". That test is scoped to the observation window, so a successor's own first-seen declaration passes it trivially. The specification MUST widen the anchor: the daemon MUST record the identity of the session live at the pane when a round is OPENED and when a declaration is VOIDED, and a declaration MUST NOT certify when the identity live at the pane differs from the identity recorded against the floor it is certifying against. A differing identity MUST hold the restart and surface the track, exactly as the existing identity rule requires. The daemon already derives a `session_identity` token "sufficient for a consumer to detect that the session behind a row changed" for the status snapshot (`contracts.md` §"Durable stores"), so this binds an existing observable rather than inventing one.

This also resolves, at its root, the residual named in the finding on the paste predicate above: what makes an inherited declaration dangerous is not that it is uncertifiable but that it belongs to a session that no longer exists. An identity-bound declaration is recognizable as inherited, which is the fact both findings need and neither could express while a declaration was anonymous.

### Proposed Changes

Amend `SPECIFICATION/contracts.md` §"The restart interlock". Preconditions 1 and 3 MUST be restated in terms of a per-round CERTIFICATION FLOOR rather than the injection stamp alone:

1. A certification floor exists for the track, and it is anchored on a USABLE round timestamp. The floor is the round's injection stamp; where a `ready` declaration has since been voided, the floor is the LATER of that stamp and the instant of the most recent such void. A track with no injection stamp MUST fail the check, whatever else its record holds — a recorded void instant WITHOUT a usable round timestamp, or a stamp or void instant present but unreadable or non-numeric, is MALFORMED: it MUST be surfaced by name and MUST fail the check, never resolved by falling back to whichever value remains usable.
2. The state file's token is exactly `ready` (unchanged).
3. The state file's modification time is STRICTLY newer than the certification floor.

The section MUST state that where both a stamp and a void instant exist, the LATER of the two governs, so the comparison always fails closed.

The exclusion of a voided declaration MUST be stated as a property of the RECORDED floor rather than as a property of wall-clock time, because the naive form is falsifiable. The daemon computes a declaration's age and records the void instant from separate readings of a clock that is not guaranteed monotonic; a backward step between them could record a void instant EARLIER than the modification time of the declaration it voids, and that declaration would then satisfy its own floor. The specification MUST therefore require that a recorded void instant be no earlier than the voided declaration's own modification time plus the voiding grace. With that requirement the exclusion holds by construction and costs nothing; without it, "can never" is an overstatement that a clock step falsifies.

**The specification MUST NOT claim that the floor alone carries the one-declaration-one-kill guarantee, because it does not, and two different mechanisms carry it on two different paths.** On the VOID path the guarantee rests on a disjunction: either the state-file delete succeeds, or the floor record succeeds. Both are fail-soft storage operations under §"Fail-soft posture", so the honest statement is that a voided declaration is excluded whenever EITHER succeeded — which is the same degree of redundancy the daemon has today, where either the delete or the round-close must succeed, and is neither better nor worse. Where BOTH fail in the same observation, the declaration survives with an unraised floor; that outcome MUST be surfaced as an attention condition rather than described as impossible. On the RESTART path the guarantee is carried by the deletion of the round record, exactly as it is today: the floor is CLEARED at restart, not raised, so it plays no part. Restating the guarantee as floor-carried would put a falsehood into the contract.

The daemon MUST record the void instant durably, in the round sidecar, so the floor survives a daemon restart. `SPECIFICATION/contracts.md` §"Durable stores" MUST be amended so the round-sidecar value carries the void instant AND the recorded session identity, alongside the round timestamp, the notified bands, and the round-scoped resume-pending flag. The restart MUST clear both together with the rest of the key, so no floor and no identity outlives its round.

`SPECIFICATION/contracts.md` §"The restart interlock" MUST carry the identity binding as a precondition in its own right: a declaration MUST NOT certify when the session identity live at the pane differs from the identity recorded against the floor being certified against. A differing identity MUST hold the restart and surface the track rather than failing silently, and an identity that cannot be determined MUST be treated as differing — fail-closed, per §"Fail-soft posture".

Amend `SPECIFICATION/spec.md` §"The supervision round" to state that a round's certification floor MAY rise within the round — when a declaration is voided — and that a rising floor never re-opens a band, never authorizes a paste, and never resets the notified bands.

Amend `SPECIFICATION/spec.md` §"The cardinal rule" with an explicit non-weakening sentence: a restart MUST still be authorized ONLY by a session-written `ready`; the certification floor governs WHICH declaration may authorize a restart and never whether the daemon may infer one. The daemon MUST NOT restart on a timer, on idleness, on the age of a declaration, or on how low remaining context has fallen.

Acting on a passed interlock MUST remain gated on the live pane evidence contracts.md §"The restart interlock" already requires — a verified empty idle input state, a settled pane, no busy signals including no background-shell evidence, and a positive identity check. A session that oscillates between declaring and resuming work is therefore still never killed mid-work: the settled-idle gate at restart time is what protects it, and this finding does not relax it.

Five scenarios MUST be added to `SPECIFICATION/scenarios.md`. The first two pin the identity binding:

    ## Scenario: A successor session never certifies against its predecessor's floor

    Given a track whose declaration was voided, leaving a certification floor

    And the supervised session at that pane was replaced out of band

    When the successor session writes ready after that floor

    Then the interlock holds, because the identity at the pane differs from the identity recorded against the floor

    And the track is surfaced to the operator rather than restarted

    ## Scenario: An undeterminable session identity fails the interlock closed

    Given a track carrying a ready declaration newer than its certification floor

    And the session identity live at the pane cannot be determined

    When the daemon evaluates the restart interlock

    Then the interlock fails and no restart occurs

    And the track is surfaced rather than silently skipped

And three pin the floor itself:

    ## Scenario: A ready declaration written after a void certifies without a new round

    Given a session whose earlier ready declaration was voided when it resumed work

    And the session later writes ready again, after the instant of that void

    And the pane is idle, settled, and positively identified as this track's session

    When the daemon evaluates the restart interlock

    Then the interlock passes and the session is restarted

    And no new wrap-up was required to authorize it

    ## Scenario: A voided declaration never certifies against its own void

    Given a ready declaration that was voided past the grace

    And the state file still carries that same declaration unchanged

    When the daemon evaluates the restart interlock

    Then the interlock fails, because the declaration predates the instant of its own voiding

    ## Scenario: A ready declaration on a track that was never in a round certifies nothing

    Given a track with no injection stamp and no recorded void

    And a state file declaring ready

    When the daemon evaluates the restart interlock

    Then the interlock fails and the track is surfaced as carrying a declaration that cannot certify

The corresponding `tests/heading-coverage.json` links MUST be added atomically with the new scenarios, per `non-functional-requirements.md` §"Scenarios".

The shipped operator prose MUST be brought into step in the same change: `overseer/marker-protocol.md` §"What `ready_valid` validates (the restart interlock)" MUST describe the certification floor and MUST stop implying that a declaration written outside a round is always report-only, and `.claude-plugin/prose/overseer.md` MUST replace the `ready-uncertifiable` remedy sentence "a human must clear the declaration or open a sanctioned round" with the mechanical path, retaining the human remedy only for a track that has genuinely never been in a round.

**Binding sequencing constraint, reciprocal to the one stated in the finding "Voiding a declaration MUST NOT close the supervision round".** That finding MUST NOT be implemented without this one in the same change. Removing the round close on a void, without this floor, leaves the one guarantee that a voided declaration is never honored later resting solely on a state-file delete that spec.md §"Fail-soft posture" explicitly permits to fail. This floor is what makes that deletion a hygiene measure rather than a correctness mechanism: a surviving declaration predates its own voiding and therefore fails the comparison by construction. The two findings MUST land together, and a work-item decomposition MUST NOT separate them.

This constraint does NOT bind the finding "A report-only attention membership MUST NOT suppress the below-threshold branch", which is independent of both and MAY land on its own — with the single exception, stated in that finding, that its tightening of the paste predicate MUST NOT precede this floor.
