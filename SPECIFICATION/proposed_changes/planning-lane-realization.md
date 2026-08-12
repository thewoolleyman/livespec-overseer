---
topic: planning-lane-realization
author: claude-fable-5
created_at: 2026-08-12T00:07:35Z
---

## Proposal: Realize the ratified Planning Lane contract in the overseer spec

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

Ratification MUST also co-edit `../tests/heading-coverage.json` — see
§"Co-edited non-spec files" below.

### Amendment history

Round 1 of the independent adversarial review (2026-08-12) returned six
blockers. This revision clears all six; the amendments are marked inline as
`[R1-n]` against the blocker they answer, and summarized in §"What round 1
changed". The review was performed by Opus 5 under a maintainer-authorized
one-off deviation from the Fable-model requirement, so the ratification record
for this proposal MUST read `reviewer_model: opus`, never `fable`.

### Summary

Replace the overseer's file-handoff vocabulary with the ratified Planning Lane
contract from livespec v197/v198. The governed plan's ledger epic is the durable
plan-state surface: supervisor handoffs are appended there as ledger entries
through the orchestrator's sanctioned plan surface, and worker and supervisor
respawns are prompted to read ledger-held plan state. The PR-authored
`plan/<topic>/supervisor-handoff.md` binder is retired from the specification
surface, and `plan/<topic>/handoff.md` is no longer named as the worker resume
source.

Three scope boundaries, stated because round 1 found each of them assumed rather
than declared:

- **The shared role layer survives.** `.ai/supervisor-protocol.md` is NOT
  retired. The ratified record retires artifacts in the PLAN STORE; `.ai/` is a
  repo-root role layer, not the plan store, and no ratified record touches it.
  Its authoring permission, its two-layer halt-with-remedy guard, its
  worktree → pull request → review → merge discipline, and its
  "not a packaged plugin asset" status are all preserved verbatim in the edits
  below. What changes is only the medium of the PER-PLAN binder, which moves
  from a plan-tree file to ledger entries.
- **The `resume` mapping-store key survives.** Only `handoff` is retired.
  `resume` is the operator's optional per-track override of the respawn prompt —
  an overseer runtime affordance the Planning Lane record does not reach.
- **The respawn prompt gains a concrete locator.** It names the repository path
  and the plan's ledger epic id literally, so a session with no prior context can
  resolve it; and a track with no recorded epic id is not respawned at all.

This proposal also updates the four current `spec.md` prose lines that still use
old plan-thread vocabulary (re-enumerated in this tree as lines 369, 397, 400,
and 439) to the ratified `plan` vocabulary — the artifact is a **plan**; the
Planning Lane is the Spec-Plane convention that governs it.

One `## ` heading in `scenarios.md` is RENAMED and one is ADDED, so ratification
DOES owe a `tests/heading-coverage.json` co-edit; it is specified in full in
§"Co-edited non-spec files". Ratification of this proposal is a separate step
from authoring it and is not performed here.

### Motivation

livespec v197/v198 ratified the Planning Lane realization: plan state is held on
the governed plan's epic, not in a plan-tree handoff file. livespec-overseer's
own spec still predates that contract in the wrap-up obligation, restart prompt,
supervisor-pair brief, non-interference carve-out, contracts, constraints, and
operator-observable scenarios. That leaves the control-plane spec instructing
sessions and pair members to use artifacts that the fleet contract has retired.

The protected properties do not change. The daemon still never writes tracked
plan-tree files, still never reads handoff payloads as authorization, and still
restarts only after a fresh `ready` declaration passes the interlock. Two
protections are RE-DERIVED onto the new surface rather than dropped: the
supervisor respawn is still gated against resuming onto a pointer that cannot be
resolved — now the track's recorded epic id rather than a file's existence — and
the daemon still takes no content or modification-time dependence on whatever the
pointer names. What changes is the durable read-first target: it is the plan's
ledger-held state, including supervisor handoff ledger entries, rather than
`plan/<topic>/handoff.md` or `plan/<topic>/supervisor-handoff.md`.

### What round 1 changed

| # | Round-1 blocker | Amendment |
|---|---|---|
| 1 | The restart prompt became an undefined category no cold-open session could resolve; "ledger" was defined nowhere in this spec. | EDIT 3 now DEFINES ledger-held plan state and names the `epic` locator; EDIT 2 and EDIT 6 require the prompt to carry the repository path and epic id literally; EDIT 6 refuses the respawn and preserves the declaration when no epic id is recorded; a new scenario pins both clauses. |
| 2 | The probe scenario was rewritten into the never-probes case its bound integration test asserts against, with heading and `Given` retained. | EDIT 7 now renames the heading, amends the `Given`, specifies the paired `tests/heading-coverage.json` co-edit with an integration-tier reason, and cites `overseer-pfpfty.7` for the test-source change this proposal cannot carry. |
| 3 | `.ai/supervisor-protocol.md`'s permission, the two-layer guard, the commit-discipline sentence, and "Neither is a packaged plugin asset" were dropped undisclosed; EDIT 5's third target was described, not quoted. | EDIT 5 now quotes that target VERBATIM and preserves all four obligations, retiring only the plan-tree binder; the two survivors the round-1 sweep missed (`spec.md` §"Supervised runtimes" cross-reference, `scenarios.md` role-layer scenario) are amended in EDIT 5 and EDIT 7. |
| 4 | `handoff`/`resume` were called "legacy input only" while both are emitted on every rewrite and `resume` is the live respawn prompt; `spec.md`'s closed enumeration was left contradicting. | EDIT 6 now retires only `handoff`, states that retirement as a change with its rationale, keeps `resume` as the operator override, and EDIT 4 amends the closed persisted-facts enumeration to match and to name the epic locator. |
| 5 | "Planning Lane" (the convention) was installed where the ratified vocabulary requires "plan" (the artifact). | EDIT 4 now says **plan** in all four replacements; the Summary's statement of intent is corrected. |
| 6 | Both replacements granted a DIRECT Control-Plane ledger append with no sanctioned-surface routing. | EDIT 5 and EDIT 7 now route every append THROUGH the orchestrator's sanctioned plan surface and forbid a direct write to the plan epic's ledger. |

### Proposed Changes

Seven edits. Anchors re-enumerated against the working tree at proposal time.

EDIT 1 (spec.md §"The supervision round"). Replace the stale example in the
undelivered-wrap-up paragraph:

> `ready` written afterwards — a handoff convention, a state file inherited from
> a predecessor, an unprompted write by a session that was never told to declare
> — would otherwise certify against it and authorize a kill.

with:

> `ready` written afterwards — a stale resume convention, a state file inherited
> from a predecessor, an unprompted write by a session that was never told to
> declare — would otherwise certify against it and authorize a kill.

EDIT 2 (spec.md §"The escalating wrap-up" and §"The restart"). Replace the
wrap-up message obligation:

> its current remaining-context percentage; the exact state-file path and the
> three values it may write; that its handoff file is the ONLY artifact the
> successor session inherits, so drifted resume state belongs in a rewritten
> handoff, never withheld; and the truth that it will be restarted ONLY when it
> declares `ready`.

with:

> its current remaining-context percentage; the exact state-file path and the
> three values it may write; that the plan's ledger-held state is the successor
> session's durable read-first source, so drifted resume state belongs in an
> appended ledger entry, never withheld; and the truth that it will be restarted
> ONLY when it declares `ready`.

In the restart paragraph, replace `[R1-1]`:

> read your track's handoff file and follow it.

with:

> read the plan state held on this track's ledger epic and follow it — a prompt
> that MUST name the track's repository path and its recorded epic id literally,
> so a session opening with no prior context can resolve what to read without
> opening any plan-tree file.

EDIT 3 (spec.md §"Track discovery and the mapping store"). Replace the discovery
paragraph's file-handoff tail and the bounded file probe `[R1-1]`:

> Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes
> any file inside a plan directory (per §"Non-interference with tracked work");
> the conventional handoff path it derives is a pointer handed to sessions,
> never opened by the overseer. One bounded exception: for a track with a
> CURRENTLY MATCHING live session (the liveness gate), the daemon MAY test the
> EXISTENCE of exactly one named artifact, plan/<topic>/supervisor-handoff.md —
> no open, no read, no hash, no content or mtime dependence, and no probe of any
> kind for tracks without a live session. This is the ONLY file-level probe the
> discovery path may ever perform.

with:

> Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes
> any file inside a plan directory (per §"Non-interference with tracked work").
> The read-first target it hands to sessions is the plan's LEDGER-HELD PLAN
> STATE: the append-only, individually attributed and timestamped handoff
> entries carried on the governed plan's ledger epic, whose id the mapping store
> persists as that track's `epic` value. The daemon holds that id as an OPAQUE
> LOCATOR — it hands the id to sessions, and it never reads those entries, never
> hashes them, and never inspects them as restart authorization. The discovery
> path performs no file-level probe inside a plan directory.

EDIT 4 (spec.md §"Track discovery and the mapping store" and §"Session-name
derivation"). Apply the ratified `plan` vocabulary to the four term-bearing
prose lines called out by this work item `[R1-5]`. The artifact is a **plan**;
the **Planning Lane** is the Spec-Plane convention that governs plans, and is
not itself a thing that is archived, closed, or transferred to:

- Replace "Whoever archives a plan thread MUST leave NOTHING at its live path"
  with "Whoever archives a plan MUST leave NOTHING at its live path".
- Replace "When a plan thread would close with anything unresolved" with "When
  a plan would close with anything unresolved".
- Replace "TRANSFERRED to a different or new NON-ARCHIVED plan thread and/or
  work-item" with "TRANSFERRED to a different or new NON-ARCHIVED plan and/or
  work-item".
- Replace "a plan-thread worker, wrapped up, nudged, or respawned into a plan
  handoff" with "a plan worker, wrapped up, nudged, or respawned into
  ledger-held plan state".

In the same section, replace the mapping store's closed persisted-facts
enumeration, which the retirement in EDIT 6 would otherwise leave contradicting
`[R1-4]`:

> The store persists ONLY facts that cannot be re-derived from the filesystem:
> the topic-to-session mapping, a custom resume line, a per-track threshold
> override, and a pinned session identity.

with:

> The store persists ONLY facts that cannot be re-derived from the filesystem:
> the topic-to-session mapping, the plan's ledger epic id, a custom resume line,
> a per-track threshold override, and a pinned session identity. The epic id
> qualifies because re-deriving it would mean reading a file inside a plan
> directory, which the daemon never does.

EDIT 5 (spec.md §"Supervised runtimes" and §"Non-interference with tracked
work"). Replace the supervisor-pair artifact contract with the ledger-held
Planning Lane contract, preserving the shared role layer and the
resume-onto-a-dead-pointer protection.

In the pair identity paragraph, replace `[R1-1]` `[R1-6]`:

> its wrap-up and keep-going messages are entity VARIANTS whose paths, session
> name, and commit ritual refer to the supervisor's own artifacts —
> `plan/<topic>/supervisor-handoff.md`, committed through the repository's own
> discipline — and never to the worker's handoff; and its restart preserves the
> suffixed session name and hands the fresh session exactly one prompt: read the
> supervisor handoff and follow it. The respawn is additionally gated on that
> artifact EXISTING, re-checked immediately before the act, so a `ready` with no
> artifact preserves the declaration and surfaces the existing capture offer
> instead of resuming onto a dead pointer; the daemon takes no content or
> modification-time dependence on the artifact, so brief freshness remains the
> supervisor's own protocol obligation, discharged by committing the brief before
> declaring `ready`.

with:

> its wrap-up and keep-going messages are entity VARIANTS whose paths, session
> name, and append ritual refer to the supervisor's own layer — the supervisor
> handoff entries on the governed plan's ledger epic, appended through the
> orchestrator's sanctioned plan surface — and never to the worker's own
> read-first state; and its restart preserves the suffixed session name and hands
> the fresh session exactly one prompt: read the supervisor handoff entries on
> this track's ledger epic and follow them, with the repository path and the epic
> id named literally. The respawn is additionally gated on that epic id being
> RECORDED for the track, re-checked immediately before the act, so a `ready`
> with no recorded epic preserves the declaration and surfaces the existing
> capture offer instead of resuming onto a pointer the fresh session cannot
> resolve; the daemon takes no content or modification-time dependence on those
> entries, so brief freshness remains the supervisor's own protocol obligation,
> discharged by appending the brief through that sanctioned plan surface before
> declaring `ready`.

Replace the attention sentence:

> supervision died mid-handoff and the brief is at risk

with:

> supervision died mid-brief and the ledger entry is at risk

Replace the cross-reference in the paragraph that introduces the supervisor pair,
which after this edit points at a section granting two authoring permissions
rather than one artifact permission `[R1-3]`:

> A tracked session MAY have an attended SUPERVISOR session beside it (the
> artifact permission is in §"Non-interference with tracked work").

with:

> A tracked session MAY have an attended SUPERVISOR session beside it (the
> authoring permissions are in §"Non-interference with tracked work").

Replace the two §"Non-interference with tracked work" paragraphs below, quoted
here verbatim as a single contiguous target `[R1-3]`:

> The overseer's DAEMON — the unattended observation and restart loop — NEVER
> touches files under any repository's plan tree. The handoff and everything
> beside it are the supervised session's own workflow: the overseer enumerates
> plan DIRECTORIES to discover tracks and points sessions at the conventional
> handoff path, but the daemon never opens, writes, or hashes those files — the
> restart interlock deliberately inspects nothing beyond the state-file token
> for the same reason. The one bounded exception, consistent with that
> enumeration — an existence test is not an open, write, or hash — is the
> supervision-artifact probe: for a track with a CURRENTLY MATCHING live
> session, the daemon MAY test whether the single reserved
> plan/<topic>/supervisor-handoff.md exists, never opening, reading, or hashing
> it, and it probes not at all for a track without a live session, exactly as
> §"Track discovery and the mapping store" permits.
>
> An ATTENDED Control-Plane operator skill (supervise-plan) MAY create exactly
> TWO named artifacts in a watched repository: the shared role layer
> `.ai/supervisor-protocol.md`, and the per-thread binder
> `plan/<topic>/supervisor-handoff.md`. The binder is intentionally thin and is
> NOT complete on its own; it MUST be read together with the shared layer, and
> it MUST emit a guard that HALTS with a labelled REMEDY if that layer is absent.
> Both MUST be written exclusively through that repository's own documented
> commit discipline — worktree, then pull request, then review, then merge —
> never directly to a primary checkout. Neither is a packaged plugin asset; the
> skill writes both into the consuming repository's own tree. An authored
> artifact is NOT overseer runtime state: the "exactly two places" sentence
> below and the startup gitignore refusal continue to bind the daemon's runtime
> state verbatim.

with:

> The overseer's DAEMON — the unattended observation and restart loop — NEVER
> touches files under any repository's plan tree. The plan state and everything
> beside it are the supervised session's own workflow: the overseer enumerates
> plan DIRECTORIES to discover tracks and points sessions at ledger-held plan
> state, but the daemon never opens, writes, or hashes plan-tree files and never
> reads plan-state text as restart authorization — the restart interlock
> deliberately inspects nothing beyond the state-file token for the same reason.
> The discovery path performs no file-level probe inside a plan directory.
>
> An ATTENDED Control-Plane operator skill (supervise-plan) authors the same two
> layers it always has, on two different media. It MAY create exactly ONE named
> artifact in a watched repository — the shared role layer
> `.ai/supervisor-protocol.md` — and it authors the per-plan binder as supervisor
> handoff entries on the governed plan's ledger epic. The binder is intentionally
> thin and is NOT complete on its own; it MUST be read together with the shared
> layer, and it MUST emit a guard that HALTS with a labelled REMEDY if that layer
> is absent. `.ai/supervisor-protocol.md` MUST be written exclusively through that
> repository's own documented commit discipline — worktree, then pull request,
> then review, then merge — never directly to a primary checkout. The binder's
> handoff entries MUST be appended THROUGH the orchestrator's sanctioned plan
> surface, never by a direct write to the plan epic's ledger and never by creating
> or updating `plan/<topic>/supervisor-handoff.md` through the pull request path.
> Neither layer is a packaged plugin asset; the skill writes the shared layer into
> the consuming repository's own tree and the binder onto that repository's own
> plan epic. Neither is overseer runtime state: the "exactly two places" sentence
> below and the startup gitignore refusal continue to bind the daemon's runtime
> state verbatim.

EDIT 6 (contracts.md §"The restart interlock", §"The wrap-up injection",
§"The keep-going nudge", and §"Durable stores"). Replace the restart guarantee
`[R1-1]`:

> handed exactly one prompt: read that entity's resume artifact —
> `<repo>/plan/<topic>/handoff.md` for a worker,
> `<repo>/plan/<topic>/supervisor-handoff.md` for a supervisor pair member —
> and follow it.

with:

> handed exactly one prompt: read that entity's ledger-held plan state — the
> handoff entries on the governed plan's ledger epic for a worker, or the
> supervisor handoff entries on that same epic for a supervisor pair member —
> and follow it. The prompt MUST name the track's repository path and the plan's
> epic id LITERALLY, so a session opening with no prior context can resolve what
> to read without opening any plan-tree file; a prompt naming only a category is
> not a pointer. A track with NO recorded epic id is not respawned at all: the
> `ready` declaration is PRESERVED and the track surfaced, exactly as for a
> respawn that failed, so a declaration is never spent on a prompt the fresh
> session cannot resolve.

Replace the wrap-up message obligation:

> the handoff path as the sole artifact the successor inherits (with the
> instruction to REWRITE it on drift, never withhold the declaration)

with:

> the ledger-held plan state as the successor's durable read-first source, named
> by repository path and epic id (with the instruction to APPEND a ledger entry
> on drift, never withhold the declaration)

Replace the keep-going sentence:

> The message points the session back at its handoff

with:

> The message points the session back at its ledger-held plan state

Replace the mapping-store durable-key sentence `[R1-4]`:

> Durable keys: `topic`, `repo`, `tmux`, `handoff`, `resume`, `epic`,
> `pinned_session_id`, plus `ctx_threshold` ONLY when a per-track override is
> set

with:

> Durable keys: `topic`, `repo`, `tmux`, `resume`, `epic`, `pinned_session_id`,
> plus `ctx_threshold` ONLY when a per-track override is set. The `epic` value is
> the plan-state locator the read-first chain resolves against, and it is REQUIRED
> for any track whose session may be restarted. This revision RETIRES the
> `handoff` key — a change, not a description of existing legacy: it named a
> plan-tree artifact the Planning Lane contract has retired, so rewrites MUST NOT
> emit it, and a legacy row still carrying it is read without error and rewritten
> without it. The `resume` key is NOT retired; it remains the operator's optional
> per-track override of the respawn prompt, and when it is absent the daemon
> derives that prompt from `repo` and `epic`

EDIT 7 (constraints.md §"Filesystem boundaries" and scenarios.md). Replace the
constraints paragraph's attended authoring sentence `[R1-3]` `[R1-6]`:

> The attended Control-Plane authoring exception permits supervise-plan to
> create exactly two reviewed artifacts, `.ai/supervisor-protocol.md` and
> `plan/<topic>/supervisor-handoff.md`.

with:

> The attended Control-Plane authoring exception permits supervise-plan to create
> exactly ONE reviewed artifact, `.ai/supervisor-protocol.md`, under that
> repository's reviewed commit discipline, and to author the per-plan binder as
> supervisor handoff entries appended to the governed plan's ledger epic THROUGH
> the orchestrator's sanctioned plan surface — never by a direct write to that
> ledger, and never by creating or updating `plan/<topic>/supervisor-handoff.md`
> through the pull request path.

In scenarios.md, replace:

> And the message names the state-file path, the three writable values, and the
> handoff path

with:

> And the message names the state-file path, the three writable values, and the
> ledger-held plan state

Replace `[R1-1]`:

> And hands the fresh session exactly one prompt pointing at the track's handoff

with:

> And hands the fresh session exactly one prompt naming the track's repository
> and its plan epic id

Rename the supervision-artifact probe scenario's `## ` heading `[R1-2]`, because
its body now asserts that no probe occurs and the old heading asserted the
opposite. Replace:

> ## Scenario: The supervision-artifact existence probe is liveness-gated and existence-only

with:

> ## Scenario: Discovery performs no file-level probe inside a plan directory

Replace that scenario's now-inert precondition, whose live-session clause existed
only to gate the retired probe:

> Given a watched repository containing a plan directory whose track has a currently matching live session

with:

> Given a watched repository containing a plan directory, with or without a currently matching live session

Replace that scenario's body:

> Then it MAY test whether plan/<topic>/supervisor-handoff.md exists
>
> And it never opens, reads, or hashes that file and never depends on its content
> or mtime
>
> And for a track without a live matching session it performs no file-level
> probe at all

with:

> Then it performs no file-level probe inside the plan directory
>
> And it never opens, reads, or hashes plan-tree handoff files as authorization
>
> And it points the session at ledger-held plan state instead

Replace the role-layer scenario's precondition, which still names the retired
plan-tree binder `[R1-3]`:

> Given a supervise-plan-authored binder whose required shared role layer `.ai/supervisor-protocol.md` is absent

with:

> Given supervise-plan-authored binder entries on a plan's ledger epic whose required shared role layer `.ai/supervisor-protocol.md` is absent

Its `## ` heading — "A missing supervisor role layer halts the binder with a
remedy" — is deliberately UNCHANGED: "binder" continues to name the per-plan
layer, whose medium changes while its guard obligation does not.

Finally, ADD one scenario to scenarios.md, immediately after the renamed probe
scenario, pinning the locator requirement and the refusal that protects it
`[R1-1]`:

> ## Scenario: A respawn prompt names the plan epic and repository so a cold-open session can resolve it
>
> Given a track whose mapping row records the plan's ledger epic id
>
> When the daemon respawns the session after a fresh `ready` declaration passes the interlock
>
> Then the single pasted prompt names that repository path and that epic id literally
>
> And a track with no recorded epic id is not respawned, its `ready` declaration is preserved, and the track is surfaced

### Co-edited non-spec files

Per `SPECIFICATION/spec.md` §"Self-application", ratification MUST carry
`../tests/heading-coverage.json` in the same `resulting_files[]` payload as the
spec edits above, with exactly two changes `[R1-2]`:

1. **Renamed heading.** The existing entry whose `spec_file` is `scenarios.md`
   and whose `heading` is
   `## Scenario: The supervision-artifact existence probe is liveness-gated and existence-only`
   changes its `heading` to
   `## Scenario: Discovery performs no file-level probe inside a plan directory`,
   its `test` to `TODO`, and its `reason` to:

   > Re-pointed by the Planning Lane realization. The previously bound
   > integration-tier test asserts the probe HAPPENS on the live-session pass
   > (`assert _HANDOFF in live_probes`), which is the exact opposite of what this
   > scenario now asserts, so the binding cannot be carried forward. Scenario
   > headings must map to an integration-tier-or-above test, never a unit-tier
   > one; replace TODO with that test ID through work-item `overseer-pfpfty.7`.

2. **Added heading.** A new entry with `spec_root` `SPECIFICATION`, `spec_file`
   `scenarios.md`, `heading`
   `## Scenario: A respawn prompt names the plan epic and repository so a cold-open session can resolve it`,
   `test` `TODO`, and `reason`:

   > Added by the Planning Lane realization to pin the respawn prompt's concrete
   > locator and the refusal that protects it. Scenario headings must map to an
   > integration-tier-or-above test, never a unit-tier one; replace TODO with
   > that test ID through work-item `overseer-pfpfty.7`.

Both `reason` strings name the integration tier, which
`check-heading-coverage` direction 4 requires of a `TODO` entry on a
`scenarios.md` heading.

**Test source is deliberately out of scope here.** A proposed change carries
spec files and their governed co-edits; it cannot carry test source. The
integration test currently bound to the renamed heading,
`tests/integration/test_discovery_and_relay.py::test_scenario_the_supervision_probe_is_liveness_gated_and_existence_only`,
asserts at line 282 that the probe happens — deliberately, so that a daemon
which never probes could not pass it — and must be re-pointed or retired once
this proposal ratifies. That work, and the replacement of both `TODO` entries
above with real integration-tier test ids, is filed as **`overseer-pfpfty.7`**
under epic `overseer-pfpfty` in repository `livespec-overseer`.
