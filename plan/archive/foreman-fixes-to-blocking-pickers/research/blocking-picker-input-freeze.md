# Blocking pickers freeze a session's async input channels

Opened 2026-08-19. Anchor work-item: `overseer-ra6s`.

## The defect class

A session parked on a blocking picker (Claude's `AskUserQuestion`, and
structurally the Codex approval/trust picker) consumes **no asynchronous
input** until a human resolves the picker. The picker is not merely a
turn-level block: it freezes *every* async channel the session has.

Two instances have been observed, and they are siblings, not duplicates.

### Leg A — operator-side (NOT this plan's scope)

A foreman's own `AskUserQuestion` escalation froze its entire cron-driven
supervision loop for ~12h on 2026-08-18, because the foreman's tick fires
only while its REPL is idle. One unanswered picker stalled supervision of
every *other* track under that foreman.

**Already owned and already ratified elsewhere.** `overseer-dz2skw`
(closed) routed the non-blocking-escalation design through
`/livespec:propose-change` -> independent review -> `/livespec:revise`,
landing SPECIFICATION v017 in PR #1105 (merged): a non-blocking escalation
requirement in `spec.md` "Relay and escalation discipline", a NEEDS YOU
membership paragraph in `contracts.md`, and a new scenario. Its two
implementation halves are open children of epic `overseer-au3pt3`
(foreman-improvements): `overseer-au3pt3.1` (daemon attention-surface
membership condition) and `overseer-au3pt3.2` (prose promotion into
`.claude-plugin/prose/foreman.md`). Both are ACTIVE/dispatched.

This plan **cites** Leg A and does not touch it. See "Boundary" below.

### Leg B — delivery-side (THIS PLAN'S SCOPE)

Observed live 2026-08-19 on session `delivery-path-speed-and-caching`
(repo `livespec-console-beads-fabro`). The session parked on an
`AskUserQuestion` picker making a dispatch-vs-park routing decision. Its
foreman then sent a cross-session `SendMessage` whose content was
**decision-relevant context for that exact picker** — the fleet
ClusterQueue resize had discharged the escalation leg motivating the
picker's option 2, mooting its rationale.

The delivery rendered as a queued composer block below the picker overlay
(`@ livespec-console-beads-fabro-foreman> ...`) and was never consumed.
The human answering the picker could not see that better information had
arrived unless they happened to scroll the pane. The sender received no
signal that its delivery had parked.

The result is a **silent mutual stall**: the decision waits for a human,
and the context that would change the decision waits for the decision.

## Why this is worth a durable fix rather than a one-off

The failure is silent on both ends and self-concealing. The sender's
`SendMessage` succeeds — delivery *did* happen, into the pane — so there
is no error to observe. The recipient's human sees a well-formed picker
with no indication that its premises are stale. Nothing in the system
currently reports the conjunction. The cost scales with how long the
picker lives, and long-lived pickers are exactly the ones most likely to
accumulate late-arriving context.

It also degrades the fleet's most-recommended coordination primitive: if
cross-session delivery is unreliable precisely when a session is waiting
on a decision, operators learn to distrust it generally.

## Mechanism, grounded in this repo's code

The daemon already carries most of the substrate this fix needs.

- `overseer/signals.py:176` — `_GATE_CURSOR_RE = re.compile(r"[❯›]\s*\d+\.")`
  and `is_structured_gate(...)` detect a structured picker gate on both the
  Claude and Codex glyphs. This is best-effort and documented as such.
- `overseer/_supervisor_picker_stall.py:55` — `picker_open = request.obs.gate`,
  i.e. the picker-open projection is already computed per row, and already
  drives a `picker-stalled` attention condition once a stall bound elapses.
- `overseer/_supervisor_snapshot.py:98` — `"picker_open": row.picker_open`
  is already published on the daemon's snapshot row. So the "is this session
  parked on a picker?" check is **already mechanical for any operator or
  sender**, needing no new daemon surface at all.
- `overseer/signals.py:272` — `input_box_text(...)` reads the Claude composer
  when a non-empty `❯` box is visible.
- `overseer/_supervisor_restart_attention.py:64` — an existing attention
  condition already derives from composer text
  (`signals.input_box_text(capture_text=obs.capture) == expected_resume`).
  This is direct precedent that a composer-derived attention condition is
  architecturally in-bounds and cheap at capture time.

The one genuinely missing signal is the **queued-delivery block** shape.
`input_box_text` keys on an `❯` line sandwiched between two border rules;
a queued cross-session delivery renders differently (the observed
`@ <sender>> ...` block below the overlay). No existing detector matches it.
Its exact signature must be captured from a real pane before being encoded
— this repo's own signal comments are consistently written from verified
live captures, and a guessed regex would be both unverifiable and
over-fitted.

## Fix directions (from `overseer-ra6s`), refined

### D1 — Sender-side routing rule (prose + spec-bearing)

Never `SendMessage` decision-relevant input to a session whose daemon row
shows `picker_open` / `blocked:human`. Deliver through the picker's own
type-in relay, or hold until the picker clears.

Refinement: the row **already** exposes `picker_open`, so the precondition
check is mechanical today and costs a sender one snapshot read. This is the
cheapest of the three directions and the only one that prevents the stall
rather than reporting it. It should land first.

Note the rule needs a stated fallback, not just a prohibition: "hold" with
no bound recreates the same stall on the sender's side. The rule must say
where held context goes and when the sender re-checks.

### D2 — Mechanical detection (daemon attention condition)

A row that is `blocked:human` / `picker_open` **and** whose pane shows a
queued `@ <sender>` composer block becomes an attention condition, alerting
the operator and, where reachable, the sender.

Refinement, and the reason this direction is spec-routed rather than
straight-to-code: **NEEDS YOU membership is ratified surface.** v017 added
a NEEDS YOU membership paragraph to `contracts.md`. Adding a new membership
condition therefore goes through `/livespec:propose-change` -> independent
review -> `/livespec:revise` before implementation, exactly as `overseer-dz2skw`
did and exactly as `overseer-au3pt3.1` now implements. That precedent is
this repo's own, one day old, and should be followed rather than re-derived.

The condition must be report-only and edge-triggered, and must authorize no
act — the cardinal rule in `overseer/marker-protocol.md` (a session is
restarted only after it declares itself `ready`) is untouched by this plan
in any direction. Nothing here adds a timer- or heuristic-driven restart path.

Do not confuse this with the existing `picker-stalled` condition, which is
keyed on picker age alone and says nothing about parked inbound deliveries;
nor with `escalation_exhausted`, which is wrap-up escalation and unrelated.

### D3 — Picker-authoring discipline (prose)

A session raising a long-lived picker states in the picker text where
late-arriving context should be routed (e.g. "if new facts arrive, answer
'Type something' with them").

Refinement: this is the recipient-side complement of D1 and is small enough
that it folds into D1's prose change rather than carrying its own item.
It is also the only leg that helps when the sender is a human rather than a
supervising session, since a human sender will not consult a daemon row.

## Boundary with the foreman-improvements track (epic `overseer-au3pt3`)

Agreed split, recorded so neither track duplicates the other:

| | foreman-improvements (`overseer-au3pt3`) | this plan |
|---|---|---|
| leg | A: operator-side | B: delivery-side |
| question | how does a foreman surface *its own* need for a human decision without freezing its loop? | how does *inbound* async context reach a session already parked on a picker — and who is told when it cannot? |
| spec status | ratified (v017, PR #1105) | to be proposed |
| open children | `au3pt3.1` (daemon NEEDS YOU membership), `au3pt3.2` (prose) | this plan's own children |

The two touch the same daemon attention surface, so the sequencing
constraint is real: this plan's D2 condition should land **after**
`au3pt3.1` establishes the v017 membership condition, reusing its shape
rather than inventing a parallel one. That is a dependency on the sibling
track's timeline, not a claim on its scope.

`overseer-ra6s` moves from `overseer-au3pt3` to this plan's epic as the
anchor bug, which is the re-parenting the commissioning directive
anticipated; foreman-improvements keeps Leg A entire.

## Open questions

- The queued-delivery pane signature is unverified. It must be captured
  live before D2 encodes it.
- Whether the sender-side rule can be made *mechanical* (a guard in the
  delivery path) rather than only prose is worth evaluating, but the
  delivery path is the harness's `SendMessage`, not this repo's code — so
  prose plus a daemon-side report is likely the whole reachable surface
  from here. Recorded rather than resolved.
