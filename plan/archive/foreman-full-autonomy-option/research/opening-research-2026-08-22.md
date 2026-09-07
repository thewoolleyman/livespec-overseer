# foreman-full-autonomy-option — opening research note, 2026-08-22

Plan record discipline: the ledger is authoritative over this directory. Plan
state, next action, handoffs and scope events live on the ledger anchor
`overseer-3h4s5w` and are read through the plan timeline. This note is
research only.

## What the maintainer asked for (2026-08-22, this session, verbatim intent)

Add a `full_autonomy` option to the `livespec-overseer` section of
`.livespec.jsonc` with these properties:

1. It OVERRIDES every other human-gating and autonomy option for the repo,
   across ALL livespec settings (core `spec_governance`, the orchestrator's
   `dispatcher` policy, and this plugin's own valve disposition).
2. It DELEGATES full maintainer authority and decision-making responsibility to
   the `<repo-slug>-foreman` tmux session and process.
3. Workers may not argue with a full-autonomy foreman. A worker may disagree
   with an instruction up to three times; the THIRD time it is instructed to
   take the same action it MUST commit and take it.
4. Staying stalled and not moving its assigned plan track forward is NOT an
   allowed action for a worker whose foreman is in full autonomy. The only
   acceptable reason for a stall is a hard system / infra / quota / credential
   error that is not resolvable by any other means.
5. The consensus panel gains a new MODE: today a single dissent is a veto;
   under full autonomy the panel decides by MAJORITY OPINION. That mode must be
   introduced as a LEVER on the consensus disposition, not hard-wired.
6. Everything is to be as MECHANICAL as possible, with minimal reliance on LLM
   judgement — accepted up front that this will not be fully achievable.

The maintainer's seed prompt is the standing-orders text already recorded
verbatim on the foreman seat anchor `overseer-z5fo4y` (first at
2026-08-20T22:38:36Z, re-issued 2026-08-21T22:38:29Z). Those two comments ARE
the behavioural spec for the foreman half of this plan; this note does not
restate them. The sentence that carries the most design weight is: "Contested
calls go to a cross-vendor consensus panel and MAJORITY OPINION WINS IN ALL
CASES; the only escalation left is a security concern a panel cannot resolve."

A related plan, `foreman-table`, is about to be opened (not yet filed at the
time of writing). Its column 4 — "why you (foreman) are not taking action to
unblock, ESPECIALLY IF YOU HAVE BEEN DIRECTED TO TAKE FULL AUTONOMY" — is a
CONSUMER of what this plan ships: it needs a mechanical `full_autonomy` reading
and mechanical stall / unheeded-ruling conditions to render against. This plan
must therefore expose those as data (runtime JSON, daemon attention
conditions), not as prose the table would have to re-derive.

## What exists today — measured 2026-08-22 against origin/master `11542a9`

### The standing orders are a ledger comment, not a setting

`full_autonomy` exists nowhere in the tree (`grep -rn full_autonomy` over
`*.py`, `*.md`, `*.jsonc`: zero hits). The orders exist only as two comments on
`overseer-z5fo4y`, typed into the foreman pane by the maintainer and transcribed
by the seat. They are: not portable to another repo without retyping; not
readable by the daemon, the actuator, the evaluator, or the grooming seat; and
not inherited by a worker unless a foreman remembers to relay them. Every
mechanical surface in this repo behaves today as if they did not exist — which
is precisely why the foreman that received them filed `overseer-5stpf2` as
"the directive says act and the tooling cannot express it".

### The one setting that exists, and its resolver

`.livespec.jsonc` → `"livespec-overseer": { "foreman_valve_disposition":
"consensus" }`, read by `overseer/foreman_valve_policy.py`
(`effective_valve_disposition`), observable via the `foreman-valve-disposition`
executable. Enumerated `report-only` | `consensus`; anything else fails closed
to `report-only` with `recognized: false`. Consumed by
`overseer/foreman_act_consensus.py` `_pre_evidence_refusal`, which refuses any
human-valve act unless the effective value is `consensus`.

### The decision matrix: what "a single dissent is a veto" actually means

`overseer/foreman_consensus_decision.py`. Two authorizing paths exist:

- `unanimous` — zero `needs-human` verdicts AND all three typed actions
  canonically equal.
- `minority_override` — EXACTLY one `needs-human` reviewer and EXACTLY two
  `unblock` reviewers who agree with each other, AND a `minority_report_round`
  in which both unblockers re-affirm, AND the action is reversible AND
  rollback-bounded. Reviewed and narrowed deliberately at Phase C
  (`overseer-ncx`).

Everything else escalates with `action: human_valve`. The vetoes fire BEFORE
the matrix, in `reviewer_validation_reason`, and each is a single-reviewer
short-circuit: `insufficient_information` (any reviewer), `hard_risk_dissent`
(any reviewer with `needs-human` + `hard_risk: true`),
`non_anthropic_needs_human_dissent` (the one non-Anthropic reviewer returning
`needs-human`), `unpinned_model_identity`, `free_form_action`,
`unknown_verdict`. Then in the matrix: three `unblock` reviewers splitting 2-1 on
WHICH action → `typed_action_disagreement` → escalate.

### The majority path is IN FLIGHT RIGHT NOW — do not redo it

`overseer-5stpf2` (P2, `active`, assignee `fabro`, factory `hp`, remote run
`01M0K7V4B32Y`, dispatched 2026-08-21T22:42:00Z) implements the majority path
the re-issued standing orders demanded. Its publish branch
`feat/overseer-5stpf2` is **PR #1476, OPEN**, CI queued at 23:13Z when this note
was written. Its diff, read from the forge:

- adds `majority()` / `majority_action()` to `foreman_consensus_decision.py`:
  when `needs_human` is EMPTY and exactly one canonical action is held by
  exactly two reviewers, outcome `majority`, reason
  `two_unblock_typed_actions_equal`;
- `majority_action` returns `None` unless EVERY action is a
  `blocked_session_answer` — so majority is scoped to picker answers only;
- `foreman_act_consensus._authorized_panel_action` accepts outcome in
  `{"majority", "unanimous"}`;
- control legs (a)–(d) from the item's acceptance, built on the recorded
  fixture `tests/fixtures/foreman-consensus/recorded-picker-reviewer-responses.json`.

Three things about it shape this plan:

1. **It is UNCONDITIONAL.** No configuration value gates the majority outcome;
   once #1476 merges, every repo whose disposition is `consensus` decides picker
   answers by majority. The maintainer's item 5 above — "introduce it as a
   lever" — is exactly the delta this plan owes: make `majority` conditional on
   a decision-rule setting that `full_autonomy` selects, and keep today's
   unanimous behaviour as the default for a repo that declares nothing.
2. **It does not touch the pre-matrix vetoes.** A single
   `insufficient-information`, a non-Anthropic `needs-human`, or any hard-risk
   dissent still vetoes before `majority_action` is ever reached. "Majority
   opinion wins in all cases" is therefore NOT yet true after #1476; it is true
   only for the 2-1-on-which-answer shape the item measured. This plan's
   majority mode must define what each veto becomes under majority.
3. **It drifts from the ratified spec the moment it merges.** `SPECIFICATION/
   spec.md` §foreman still says a human valve may be acted on "ONLY when a
   cross-vendor review panel returns a unanimous typed verdict" and "The foreman
   MUST escalate ... when the panel disagrees". #1476 was dispatched on the
   standing orders, which by their own text supersede "the foreman prose, for
   this repository" — they cannot supersede the specification. The spec child
   below ratifies the majority outcome together with the lever, so the drift
   is closed rather than left as a finding.

### The floors this plan collides with, and who owns each

This repo's `SPECIFICATION/spec.md` §foreman (ratified through v026):

- "Under the consensus disposition the foreman MAY act on a human valve ONLY
  when a cross-vendor review panel returns a unanimous typed verdict".
- "No configuration value MAY authorize the foreman to dispose of a truly
  unresolvable decision, nor of any decision that is human-gated BY DESIGN —
  drift acceptance, a spec-change slice, a regroom or backlog bounce, or a
  human-only acceptance. ... Such a floor MUST NOT be relaxable by any
  configuration key; relaxing one requires a ratified amendment to this
  specification."
- "The foreman MUST escalate, and MUST NOT act, when consensus evidence is
  unavailable or insufficient, when the panel disagrees, when any reviewer
  returns an insufficient-information verdict, or when the audit journal
  append fails."
- "A dissent that is not vendor-aligned with the majority MUST NOT be
  overridable by the remaining reviewers. An outcome reached by overriding a
  minority report MUST NOT be recorded as unanimous."
- `constraints.md`: "The foreman MUST NOT widen its own authority on the basis
  of any evidence it produced itself, and MUST NOT set its own disposition."
- `contracts.md` §"The foreman valve disposition": enumerated set, safe default
  `report-only`, observable without running the foreman, not settable by the
  foreman.

Those floors are exactly what `full_autonomy` is asked to relax, and the spec
itself names the route: a ratified amendment. That is a `propose-change` →
`revise` child, and this repo's `spec_governance` is already armed to run it
without a maintainer prompt (`revise_decision_mode: delegated`,
`ratification_review: auto-spawn` with `fable`, `spec_pr_merge:
auto-on-green`).

Two of the floor categories are NOT this repo's to relax, because the spec
binds to them BY REFERENCE ("DEFINED BY the governing orchestrator contract,
not by this tree"):

- **Orchestrator** (`livespec-orchestrator-beads-fabro/SPECIFICATION/contracts.md`
  §"Every needs-human escalation still reaches a human"): "The Dispatcher MUST
  NOT auto-resolve a `blocked_reason: needs-human` item; it MUST surface every
  such item to a human. A decision that is human-gated BY DESIGN — a spec-change
  slice, a regroom / backlog bounce, or a `human-only` acceptance — MUST stay
  escalated even when the Dispatcher is fully confident."
- **livespec core** (`livespec/SPECIFICATION/spec.md` §spec_governance):
  `drift_acceptance_mode: consensus` "MAY own a drift acceptance only when
  UNANIMOUS cross-vendor evidence ... is present, fresh, and conforming";
  `revise_decision_mode: consensus` "requires evidence from the separately
  ratified core consensus tier; until that tier and its evidence are
  available, `consensus` requires maintainer input and arms no unattended
  decision" (spec.md:275) — i.e. it is INERT today, which is why this repo runs
  `delegated`.

A foreman in this repo disposing an orchestrator `needs-human` item, or
accepting drift on a majority, would violate THOSE specs regardless of what
this one says. So the cross-repo half of "override ALL livespec settings" is
necessarily a FILING into those tenants (reporting is always allowed; admitting
or prioritising there is not — `.ai/supervisor-protocol.md` §"FILE cross-repo
freely"), and the actuator must keep refusing those two categories until the
owning contracts ratify the relaxation.

### The levers that already exist, and where each sits today

All readable from this repo's `.livespec.jsonc` (2026-08-22):

| key | owner | value here | max-autonomy value |
|---|---|---|---|
| `spec_governance.propose_change_mode` | livespec | `batch` | `batch` |
| `spec_governance.critique_mode` | livespec | `batch` | `batch` |
| `spec_governance.in_flight_alignment` | livespec | `default-align` | `default-align` |
| `spec_governance.revise_decision_mode` | livespec | `delegated` | `delegated` (`consensus` is inert, spec.md:275) |
| `spec_governance.ratification_review` | livespec | `auto-spawn` | `auto-spawn` + model set |
| `spec_governance.ratification_reviewer_model` | livespec | `fable` | non-null |
| `spec_governance.spec_pr_merge` | livespec | `auto-on-green` | `auto-on-green` |
| `spec_governance.drift_acceptance_mode` | livespec | **absent → `human`** | `consensus` |
| `livespec-orchestrator-beads-fabro.dispatcher.acceptance_mode` | orchestrator | `ai-only` | `ai-only` |
| `livespec-orchestrator-beads-fabro.dispatcher.auto_approve_ready` | orchestrator | `true` | `true` |
| `livespec-overseer.foreman_valve_disposition` | this repo | `consensus` | `consensus` |

Only `drift_acceptance_mode` is below its ceiling here. That table is the seed
of the mechanical override in D5 below.

### Adjacent plans and items, so nothing is redone

- `plan/archive/foreman-autonomy-hardening` (archived 2026-08-21): delivered the
  convenable panel, typed-ruling ratification (v026), the recorded-next-action
  carve-out, and auto-resume on `hard-tick-budget`. Its "panel output confined
  to action ids with `human_valve` excluded" and "floors unchanged" framing is
  the posture this plan is asked to relax.
- `plan/foreman-improvements` (live, epic `overseer-au3pt3`): owns
  `overseer-5stpf2` (above); `overseer-b6q2` (P1 READY — implement the v026
  typed-ruling vocabulary; the worker three-strikes relay in D8 rides on a
  typed ruling payload, so it depends on b6q2); `overseer-a3l6x2` (P2 READY —
  panel-first positive criterion + report-only `consensus-overdue` attention
  condition; under full autonomy that condition becomes load-bearing);
  `overseer-cdwm` and `overseer-au3pt3.12` (panel tooling-outage and cache
  poisoning defects — each makes a tooling failure look like a panel verdict,
  which under majority rule is more dangerous, not less).
- `plan/foreman-picker-mutes-its-own-loop` (live, opened 2026-08-22, epic
  `overseer-lixhd3`): an open `AskUserQuestion` suppresses the foreman's own
  cron. That plan owns the LOOP-side remedy. This plan only makes a foreman
  picker under full autonomy mechanically visible (D9) and never has the daemon
  answer it.
- `plan/supervision-safety-and-attention-truth`: holds the v023 panel record;
  its attention-truth theme is where D7's report-only conditions belong
  architecturally (same `evaluate()`/attention machinery, per
  `overseer/AGENTS.md` invariants).
- The 2026-08-20T23:09:58Z panel ruling on `overseer-z5fo4y`: the panel itself
  ruled that approval/acceptance stayed human-gated under the FIRST standing
  orders, by `hard_risk_dissent` from `gpt-sol`. Under this plan's majority
  mode that exact verdict (fable needs-human, gpt-sol needs-human, opus
  insufficient-information) STILL escalates — two needs-human is a majority
  for escalation, and the design below does not change that arithmetic.

### Side observation, logged not chased

`LIVESPEC_PLAN_UNATTENDED` — the variable the orchestrator's plan prose says
"the overseer daemon sets on the resume it triggers after a context-threshold
restart" so an unattended plan session takes its single recorded next action
instead of raising a picker — is set by NOTHING in this repo: zero hits across
`overseer/`, `.claude-plugin/`, `scripts/`. Every daemon-triggered worker resume
is therefore an ATTENDED resume and raises the which-action picker. This is a
direct cause of the worker-stall shape item 4 forbids, and it is cheap: the
daemon exports the variable on the restart it performs. Folded into child C7
rather than filed separately because it is the same mechanism.

## Design — decisions taken here, reported for objection

Each decision below was answerable from the code, the specs, and the recorded
orders, so it is decided rather than asked (`CLAUDE.md` §"Decision authority").

**D1 — Key shape and resolver.** `"livespec-overseer": { "full_autonomy":
true }`. Boolean only. Absent, empty, wrong-typed, or any non-`true` value
resolves to `false` — the same fail-closed rule `contracts.md` already imposes on
the valve disposition. `foreman_valve_policy.effective_valve_disposition` grows
three fields — `full_autonomy: bool`, `decision_rule: "unanimous" |
"majority"`, and `full_autonomy_source` — and `foreman-valve-disposition` prints
them, so the effective posture is observable without running the foreman.

**D2 — Implication, and what happens on contradiction.** `full_autonomy: true`
IMPLIES effective disposition `consensus` and `decision_rule: majority`,
whatever `foreman_valve_disposition` says. If that key is EXPLICITLY
`report-only` while `full_autonomy` is `true`, full autonomy wins at runtime
(the maintainer's words: it overrides all other options) AND the resolver
reports `conflict: true` AND the conformance gate in D5 fails `just check`, so
the contradiction cannot be committed. The runtime never silently picks the
cautious reading of a key the maintainer explicitly set to override it.

**D3 — The decision-rule lever, and what each veto becomes under majority.**
`decision_rule` is the lever item 5 asks for. `unanimous` is the default and is
byte-for-byte today's behaviour INCLUDING #1476's majority-on-picker-answers
being switched OFF (a 2-1 split escalates under `unanimous`, as it did before
#1476). Under `majority`:

| today (unanimous) | under `majority` |
|---|---|
| 2-1 among `unblock` reviewers on WHICH action, picker answers only (#1476) | majority action wins, for EVERY enumerated action id and every typed ruling kind (b6q2), not only `blocked_session_answer` |
| one `needs-human` + two agreeing `unblock` → `minority_override` after a minority-report round | plain majority; no minority-report round required (the round stays as-is under `unanimous`) |
| two `needs-human` + one `unblock` → escalate | unchanged — that IS the majority |
| any `insufficient-information` → veto | counts as an abstention; the other two decide if they agree, otherwise escalate |
| non-Anthropic `needs-human` → veto | a vote like any other, EXCEPT D4 |
| `hard_risk: true` `needs-human` → veto | a vote like any other, EXCEPT D4 |
| 1-1-1 → escalate | unchanged (no majority exists) |
| `panel_size_mismatch`, `unpinned_model_identity`, reviewer timeout/failure, malformed response → escalate | unchanged — these are tooling facts, not opinions (`result_decision_kind` → `tooling_outage`) |
| journal append fails → refuse | unchanged |

The verdict carries `decision_rule`, the actuator's audit record names it
(spec: journal "the governing setting"), and a majority outcome is recorded as
`majority`, never `unanimous` (spec: an overridden minority is never recorded
as unanimous — that sentence survives unchanged).

**D4 — The sole surviving veto: a security concern.** The orders say "the only
escalation left is a security concern a panel cannot resolve". Mechanically:
the reviewer response schema gains `risk_kind: "security" | "other"`, REQUIRED
whenever `hard_risk: true` (a hard-risk verdict without `risk_kind` is malformed
→ tooling outage, not a veto). Under `majority`, a `needs-human` + `hard_risk`
+ `risk_kind: security` verdict from ANY reviewer escalates with reason
`security_dissent`, and nothing overrides it. Every other hard-risk dissent is
one vote. This narrows `overseer-5stpf2`'s leg (d) ("a non-Anthropic hard-risk
dissent stays non-overridable") to the security case the orders name, and the
reviewer prompt must ask for the classification explicitly rather than infer it.

**D5 — "Overrides ALL other settings", done as conformance rather than as a
runtime reach into sibling plugins.** livespec core and the orchestrator read
their OWN keys; this plugin cannot make them read `full_autonomy` without a
cross-plugin contract, and rewriting their keys at runtime is forbidden in
spirit by "MUST NOT set its own disposition" (and in practice by
`set-config` stripping comments, `bd-ib-lmi5`). So the override is a GATE: a
new repo-local check `check-full-autonomy-config-conformance`, wired into
`just check`, that fails whenever `full_autonomy` is `true` and any key in the
levers table above is not at its max-autonomy value — naming the key, the
value found, and the value required. The table is DATA in one module, so
registering a new lever is one row. The check must carry a positive control (a
fixture with one deliberately wrong key fails for the right reason). A
declaration that cannot coexist with a less-autonomous sibling setting is what
"override" means here; the maintainer flips one key and `just check` tells them
every other key that must follow.

**D6 — Which floors survive `full_autonomy`, and the local/foreign split.**
Survive, verbatim, because they are protocol safety rather than maintainer
preference (the orders themselves name the first two): (i) the cardinal restart
rule; (ii) no keystroking into a structured gate outside `foreman-act` — the
actuator remains the only mutation path (2026-08-20T23:09:58Z ruling); (iii)
`security_dissent` (D4); (iv) journal-before-act. Relaxed under
`full_autonomy`: `foreman_act_consensus._HARD_FLOORS` =
`{truly-unresolvable, human-gated-by-design}` becomes panel-decidable by
majority — BUT only for categories THIS repo's spec owns. The constant splits
into `_LOCAL_FLOORS` (relaxable once the spec child is ratified) and
`_FOREIGN_FLOORS` (the orchestrator's `needs-human` disposition set and core's
drift acceptance), which stay refused behind a single reviewable constant that
the cross-repo children flip WITH a citation to the ratifying version in the
owning repo. That keeps "binds by reference" honest: this tree never relaxes a
floor it does not define.

**D7 — Cross-repo filings, prepared here, pulled by a host session.** Two
items, one per tenant, with the text drafted in this plan's children rather
than filed from this session, because each is a spec-change ask in ANOTHER
repo whose own foreman runs under autonomy orders: filing it is reporting, but
a mis-scoped ask there could trigger an autonomous spec amendment, which is
outward-facing. Orchestrator tenant: when the governed repo declares
`livespec-overseer.full_autonomy`, a `blocked_reason: needs-human` item and the
design-gated set route to that repo's foreman panel (majority) instead of a
human; amend contracts.md §"Every needs-human escalation still reaches a
human". livespec tenant: under the same declaration,
`drift_acceptance_mode: consensus` accepts MAJORITY cross-vendor evidence, and
`revise_decision_mode: consensus` either binds to the overseer panel as "the
separately ratified core consensus tier" or is documented as inert.

**D8 — Workers: three objections, then comply — mechanical, not remembered.**
A foreman→worker instruction is a RELAY of a typed ruling (b6q2 payload) or a
`blocked_session_answer`, and every relay is journaled by the actuator with
`(session_identity, ruling_fingerprint)`. The actuator COUNTS prior journaled
relays of the same fingerprint to the same session: the first and second carry
`objections_remaining: 2` / `1`; the THIRD carries `final: true` and a fixed
sentence stating that the worker must now take the action. A worker's
objection is countable only in one shape: a ledger comment on its plan epic
beginning `OBJECTION <fingerprint>:` — a paraphrase in a pane is not an
objection and does not consume a strike, which is what keeps the count
mechanical. The worker-side contract (plan prose, the generated charter via
`supervise-plan`, and the shared `.ai/supervisor-protocol.md` layer) states:
you MAY object in that shape up to twice; after a `final: true` relay you MUST
take the action and MUST NOT stall. Stalling is then detected, not argued (D9).

**D9 — Stalls and pickers become daemon attention conditions, report-only,
feeding the table.** Two new conditions on the existing `evaluate()` /
attention machinery, edge-triggered like `pane-still` and `picker-stalled`:

- `final-ruling-unheeded` — a tracked row received a `final: true` relay ≥ N
  minutes ago and still shows no movement (no new commit on its branch, no new
  ledger comment on its epic, pane still `blocked:human` or still). The
  EXEMPTION list is mechanical and closed — item 4's "hard system / infra /
  quota / credential error": the ledger item reads `blocked_reason:
  infra-external`; the dispatcher journal's latest outcome for the item is a
  credential-exhaustion refusal (`CLAUDE_CODE_OAUTH_TOKEN ... exhausted`, HTTP
  429); or the daemon's own CAAM/quota surface reports the account window
  exhausted. Nothing else exempts.
- `foreman-picker-under-full-autonomy` — the `<repo-slug>-foreman` row has
  `picker_open: true` while `full_autonomy` is `true`. The daemon does NOT
  answer it (the loop plan owns the remedy, and the daemon choosing for a human
  is the design this repo rejected on 2026-08-21); it makes the violation
  visible to the next tick and to the table.

Both appear in the status snapshot and in `foreman-runtime`'s JSON alongside
`loop_lapsed`, which is what the foreman-table's column 4 renders from. Under
`full_autonomy`, the foreman's tick treats `final-ruling-unheeded` as a
DISPATCH TARGET: the already-shipped `work_item_session_start` /
`qualifying_session_resume` action ids give it a replacement-worker path that
needs no new actuator surface, and the cardinal rule still governs any restart.

**D10 — The orders are rendered by the runtime, not retyped.** When
`full_autonomy` is `true`, `foreman-runtime` prints the standing-orders block
verbatim in its tick output and checks the seat anchor epic for a comment
beginning `STANDING ORDERS` — if none exists, the foreman's first tick under
full autonomy appends one via the existing `work_item_comment` action. That
satisfies "record them in your seat's anchor as the pass-along" mechanically,
and a successor inherits them from the runtime rather than from a comment it
might not read. The prose cites the runtime's rendering; the text lives in one
place.

**D11 — The terminating condition is a key flip by the maintainer, reported
not automated.** "Until ALL active plans are complete and archived" — when
the live-plan count reaches zero, `foreman-runtime` reports
`full_autonomy_terminating_condition_reached: true`. It never edits
`.livespec.jsonc` (constraints.md: the foreman MUST NOT set its own
disposition). Flipping the key off is the maintainer's act.

## Proposed children (filed on the anchor after the scope event)

Dependency order; each names its tier. doubled-left-brace template tokens are deliberately
absent from every title, body and acceptance — the delimiter trap reaches
ledger comments and is terminal there.

1. **C1 — spec (this repo, propose-change → revise).** Ratify: the
   `full_autonomy` key and its fail-closed rule; the `decision_rule` lever with
   `unanimous` default; the `majority` outcome (which also closes #1476's
   drift); D3's veto table; D4's `security_dissent`; D6's surviving floors and
   the local/foreign split; D11's non-self-setting rule restated. Spec-change
   tier, in-session.
2. **C2 — resolver + CLI (py, factory).** D1 + D2. Beside-tests: absent, empty,
   wrong-typed, `false`, `true`; conflict reporting.
3. **C3 — decision rule in the evaluator and actuator (py, factory; depends on
   #1476 merged and C2).** D3 + D4. Control set = 5stpf2's (a)–(d) PLUS (e) a
   2-1 split under `unanimous` still escalates, (f) `security_dissent` under
   `majority` escalates, (g) one `insufficient-information` plus two agreeing
   under `majority` authorizes, (h) 1-1-1 escalates, (i) a typed-ruling
   majority authorizes; all built from the recorded production fixture or a
   fresh capture, never hand-built in the actuator's vocabulary (the
   `overseer-of2y63` lesson).
4. **C4 — conformance gate (py + justfile, factory).** D5, with the levers
   table as data and a positive control.
5. **C5 — actuator floors (py, factory; depends on C1).** D6.
6. **C6 — three-strikes relay + worker contract (py + prose, factory; depends
   on b6q2).** D8: actuator counter, `final: true`, fixed wording, `OBJECTION`
   line shape; worker-side text in plan prose, `supervise-plan` emission into
   `.ai/supervisor-protocol.md`, and the generated charter.
7. **C7 — daemon conditions + runtime surface (py, factory; acceptance includes
   a daemon bounce and a live control per CLAUDE.md).** D9 + D10 + D11 + the
   `LIVESPEC_PLAN_UNATTENDED` export on daemon-triggered restarts.
8. **C8 — foreman prose (this repo).** A §"Full autonomy" section: what
   changes, what survives, where the orders are rendered from.
9. **C9 — dogfood (config, host).** Set `full_autonomy: true` and
   `drift_acceptance_mode: consensus` in this repo's `.livespec.jsonc`; run the
   gate; observe one real majority verdict and one `final-ruling-unheeded`
   raise under the running daemon; record the evidence on the item.
10. **C10 / C11 — cross-repo filings (host, ledger-edit).** D7's two items,
    text drafted here, filed into the orchestrator and livespec tenants by a
    host session; their ids recorded back on this anchor, and their
    ratification flips C5's foreign-floor constant.

## Route

- C1 in-session via `/livespec:propose-change`; the maintainer authorized
  autonomous revise for this repo on 2026-08-20 and the governance keys are
  armed for it.
- C2–C8 factory (`impl:<id>`) once master CI is green, each dispatch-safety
  checked first (no brace tokens, no anchor-as-dependency, status `ready`).
- C9–C11 host.

## Out of scope (explicit deferrals, reconsidered where named)

- Changing the cardinal restart rule in `overseer/marker-protocol.md` —
  never; the orders keep it.
- The daemon answering any picker — rejected by design on 2026-08-21
  (foreman-picker-mutes-its-own-loop research); this plan only surfaces.
- Making the foreman's own loop survive its picker — owned by
  `plan/foreman-picker-mutes-its-own-loop`.
- Rendering the per-plan status table — owned by the upcoming `foreman-table`
  plan; this plan ships the data it reads.
- Auto-flipping `full_autonomy` off at the terminating condition — D11 reports
  only; reconsider if the maintainer wants a self-expiring key.
- Implementing the orchestrator and livespec spec amendments — their repos,
  via the items C10/C11 file; this plan tracks only the filing and the
  foreign-floor flip.
- Phase E peer-foreman federation — `overseer-l7c6`, unchanged.
- Widening the panel beyond three pinned identities or changing the
  one-non-Anthropic rule — not needed for majority; reconsider only if a
  2-1 split proves vendor-correlated in dogfood.

## Method notes

- The grooming seat's AUTO plan budget for this repo is 8 live threads; it was
  at 9 before this thread (track-record-type-safety is finished but unarchivable
  until 5stpf2 lands — see its 2026-08-21 19:20 comment). This thread makes 10
  and foreman-table will make 11. Nothing in `just check` refuses creation; the
  budget is advisory to the grooming pass. Recorded so a reader of the count
  does not conclude over-commitment: two of the overflow are one finished
  thread plus this plan, whose whole purpose is to retire the class of stall
  that holds the finished one open.
- Read `overseer-5stpf2` and PR #1476 BEFORE touching
  `foreman_consensus_decision.py`; C3 is a narrowing-and-widening of that
  landed diff, not a rewrite.
