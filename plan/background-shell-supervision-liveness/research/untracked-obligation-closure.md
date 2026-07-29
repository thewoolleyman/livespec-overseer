# Closure criteria for the four gap-untracked ratified obligations

> Companion to `control-plane-liveness.md`. It exists because the epic's
> prescribed closure check is VACUOUS for two slices, and this file is where
> the correct check is written down. Measured against the RATIFIED v003 tree
> (post-`ed55630`), not against the proposal.

## 1. Why this file exists

`detect_impl_gaps` emits candidates only from sentences carrying the literal
token `MUST`. Four obligations ratified in v003 are written in indicative,
RESERVED, or only-when voice, so they produce **no gap id at all**. The epic's
traceability comment then prescribes:

> Closure check: re-run detect_impl_gaps --since-version v002 after each slice
> lands; its gap ids must leave the set.

For a slice with no gap ids that sentence is **vacuously true with zero work
done**. It is not a weak check for `.4` and `.6`; it is not a check.

## 2. The four obligations, re-verified against the ratified files

`MUST`-token count per heading, measured on `SPECIFICATION/spec.md` and
`SPECIFICATION/contracts.md` at `ed55630`:

| File | Heading | `MUST` tokens |
|---|---|---|
| spec.md | The cardinal rule | 1 |
| spec.md | Out-of-band state declaration | **0** |
| spec.md | The supervision round | **0** |
| spec.md | The escalating wrap-up | 2 |
| spec.md | The restart | **0** |
| spec.md | The keep-going nudge | **0** |
| spec.md | The watch-set declaration | **0** |
| spec.md | Track discovery and the mapping store | **0** |
| spec.md | Session-name derivation | **0** |
| spec.md | Surface-only startup | **0** |
| spec.md | Supervised runtimes | 3 |
| spec.md | Non-interference with tracked work | 1 |
| spec.md | Notify, never block | 1 |
| spec.md | Fail-soft posture | 9 |
| contracts.md | The state file | **0** |
| contracts.md | The restart interlock | 1 |
| contracts.md | The wrap-up injection | **0** |
| contracts.md | The keep-going nudge | **0** |
| contracts.md | Durable stores | 1 |
| contracts.md | Daemon invocation | **0** |
| contracts.md | Bootstrap preconditions | **0** |
| contracts.md | Attention surface | 2 |

The four untracked obligations, each with the coordinate that proves it:

| # | Obligation (v003 edit) | Location | Why no gap id |
|---|---|---|---|
| **U1** | Blocked age-band escalation (EDIT 3) | `spec.md:360-364` | Heading "Notify, never block" carries exactly ONE `MUST`, at `:356` on alert self-sufficiency — a DIFFERENT sentence. The age-band clause itself has none. |
| **U2** | The entire pair nudge, incl. the bounded busy exception (EDIT 6) | `spec.md:160-196` | Heading "The keep-going nudge" has **zero** `MUST` across all 37 lines. |
| **U3** | The `-supervisor` reservation (EDIT 4) | `spec.md:253-261` | Heading "Session-name derivation" has **zero** `MUST`. Written as "is RESERVED" / "No worker entity may be…". |
| **U4** | The canonical-path rule (EDIT 7) | `contracts.md:50-55` | Heading "The state file" has **zero** `MUST`. Written as "is honored for an ACT only when…". |

**One arithmetic correction to `handoff.md` §7.** It reports per-heading counts
as if candidates equal `MUST` tokens, and gives Fail-soft posture as 8. The
detector emits one candidate per *sentence*, so a sentence carrying several
`MUST`s yields one candidate — `spec.md:416-419` alone carries four in a single
sentence. Fail-soft posture is **9 tokens** across fewer sentences. This changes
no conclusion: U1–U4 sit in zero-`MUST` (or wrong-sentence) territory under
either measure, which is splitter-independent.

## 3. Where the risk actually lives — narrower than §7 states

§7 frames remedy (b) as "record explicit non-gap-tracked closure criteria on
`.4`, `.6` and `.5`'s untracked halves". **Measured: those criteria already
exist and are correct.** Do not re-author them.

| Slice | Its acceptance line today |
|---|---|
| `.4` | "ACCEPTANCE. Owed test 3 (this item owns it — lane A owns only the age projection)." |
| `.5` | "ACCEPTANCE. Owed tests 5 and 13's lane-C arms … including that a worker's ready can never restart its supervisor and vice versa (crossed-file sabotage goes red), and that a symlinked state dir or file is refused." |
| `.6` | "ACCEPTANCE. Owed tests 6 and 13's lane-D arms, including content-immunity …; the counter reaching the operator line on the second nudged episode; the guard composition sabotage-verified one guard at a time." |

Each already says *verify by owed tests*, and `.5`'s explicitly names the
canonical-path half (U4). U3 is carried by `.5` scope item 2 and by owed test
13's "the `-supervisor` reservation refuses at derivation, discovery, AND the
CLI (case-insensitively)".

So the ONE defective artifact is the **epic's traceability comment**, whose
gap-id mapping covers `.1`, `.2`, `.3`, `.5` and omits `.4` and `.6` entirely,
and whose final sentence then prescribes the gap-id check as *the* closure
check. An implementer who follows the epic rather than the slice gets a green
signal for `.4` and `.6` having written no code.

**Remedy (b), correctly scoped, is one sentence on one artifact** — not three
slice rewrites.

## 3b. 2026-07-29 measurement: the gap-id check is unsatisfiable for EVERY slice, not merely vacuous for two

Measured the day `.1` merged (PR #243, `86cb0b6` on master):
`detect_impl_gaps --since-version v002` still emits ALL 20 candidate ids,
including `.1`'s mapped `gap-ekwoq4ey`. That is by construction, not a bug in
the run: the detector's module docstring states "Gap-id derivation is a pure
function of the spec-file path + canonical heading path + rule text", and the
skill is "intrinsically non-mutating" — it consults neither the
implementation nor the work-items store. A gap id leaves the emitted set ONLY
when the SPEC text changes (or a file drops out of the since-version diff),
NEVER because code landed.

Consequence: "its mapped gap ids must leave the set" — the epic comment's
current sentence, and this file's own §4 draft before this revision — is a
check that can never go green for ANY slice. The gap-ledger-side closure
signal that actually works is the one the `implement` skill prescribes:
re-run `capture-impl-gaps` in DRY-RUN mode and require the slice's mapped
gap ids to re-CLASSIFY as implemented (classification is the step that reads
the code; the mechanical detect set is just the candidate universe — fixed at
20 for v002→v003). The owed tests remain the substance; the dry-run
re-classification is the echo.

## 4. Prepared text for the consent-gated ledger write

Ledger writes in this thread are consent-gated, so this is DRAFTED, NOT
APPLIED. When consent lands, replace the epic comment's final sentence with:

> Closure check, per slice: verify by the slice's OWED TESTS (its ACCEPTANCE
> line), then confirm the gap-ledger echo by re-running `capture-impl-gaps`
> in DRY-RUN mode — the slice's mapped gap ids must re-classify as
> implemented. Do NOT use `detect_impl_gaps` set-membership as a closure
> signal: its gap-id set is a pure function of the spec text and never
> shrinks when code lands (measured 2026-07-29, `.1` merged and
> `gap-ekwoq4ey` still emits). Two slices have NO mapped gap ids at all —
> `.4` and `.6`, plus `.5`'s `-supervisor` reservation and canonical-path
> halves — because those ratified obligations lack the literal token `MUST`
> and the detector is `MUST`-keyed; they close on their owed tests alone. See
> `plan/background-shell-supervision-liveness/research/untracked-obligation-closure.md`.
> An empty or unchanged gap set NEVER means the epic is done.

## 5. Consolidated closure criteria, per untracked obligation

The owed tests that constitute done for U1–U4, gathered from
`control-plane-liveness.md` items 3, 5, 6, 7 and 13 and the ratified prose.

### U1 — blocked age-band escalation → slice `.4`

Bands ruled {4 h, 24 h, then daily}.

- One alert per band per declaration: 4 h fires once, 24 h fires once, daily thereafter.
- A re-declaration starts the bands afresh (bookkeeping keyed to declaration mtime).
- Per-tick re-alerting is impossible — a standing block emits nothing between boundaries.
- The embedded age is quantized to the boundary just crossed, so a drifting age emits no new line (owed test 7).
- A daemon restart re-states at most the HIGHEST crossed band, once.
- The declaration is NEVER voided by the surfacing path — the pinned bound keeps its load-bearing assertion.
- Young declarations from the oscillation never escalate (round-starvation owns that trap).

### U2 — the pair nudge and its bounded exception → slice `.6`

- Both members stalled past the floor with no human wait ⇒ exactly ONE nudge, into the **SUPERVISOR**, once per stall episode.
- Suppression, each proved separately: a structured gate, registry `waiting`, or a standing `blocked:` on EITHER member ⇒ no nudge, surface instead.
- A generating member (registry `busy`, or spinner for a runtime with no registry) ⇒ no stall at all.
- **The bounded exception, proved in both directions:** the paste MAY land while the supervisor's only busy evidence is a background command at a verified-empty, settled prompt — and NEVER while generating, over a gate, over a declared block, while a round is open, or on a fresh wind-down acknowledgement.
- A runtime whose empty input state is not positively verifiable is NEVER pair-nudged (Claude-only v1).
- The nudge marker never clobbers a session-written value.
- Content-immunity: a Claude supervisor pane full of pasted spinner text still stalls, nudges, and escalates.
- Progress is the runtime's authoritative report OR ctx moving between two KNOWN readings; displayed TEXT is never progress evidence for a session whose runtime reports authoritatively.
- Escalation N = 2: the consecutive-nudged-episodes counter reaches the operator line on the second nudged episode, naming both panes, supervisor first, and that the autonomous remedy already failed; it resets only on WORKER progress or a durable un-stall.
- The pair pass composes its OWN identity/TOCTOU/settled guard chain — sabotage any one guard and it goes red.

### U3 — the `-supervisor` reservation → slice `.5`

- Refused at derivation, at discovery admission, AND at the CLI — three sites, each proved.
- Compared case-insensitively (`-SUPERVISOR`, `-Supervisor` both refused).
- A `plan/<x>-supervisor/` directory is refused by discovery and surfaced BY NAME.
- The cross-repository collision qualifier can never mint one.
- A pair member's name derives from the worker's PLAN TOPIC plus suffix, never from the hosting tmux session — the `session_of` trap, `_supervisor_launch.py:52`, which today would derive a nonexistent name.
- The respawn preserves the `-supervisor` suffix.

### U4 — the canonical-path rule → slice `.5`

- A symlinked state DIRECTORY is refused as no-declaration and surfaced by name.
- A symlinked state FILE likewise.
- Crossed-file sabotage goes red in BOTH directions: worker→worker and worker→supervisor — one entity's write can never satisfy another entity's authorization.
- A legitimately symlinked CHECKOUT still passes, because the expected base is canonicalized identically — the false-positive guard.
- An aliased path can never authorize a restart. Code coordinate: `signals.py:339-341`, `state_path` is a plain `Path` join today, so reads follow symlinked parents.

## 6. Remedy (a) is unchanged and still future

Raising U1–U4 to `MUST` form in a fresh propose-change is semantically
identical and would fix detection for every consumer, but it edits ratified
prose and therefore needs its own `/livespec:revise` cycle. It is NOT a
prerequisite for landing `.4`–`.6`; this file is what unblocks them safely in
the meantime.
