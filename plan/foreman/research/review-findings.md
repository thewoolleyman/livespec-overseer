# Foreman plan — external adversarial review record (2026-08-02)

Maintainer-directed same-session follow-up to `brainstorm.md`: the full plan
(seed + brainstorm, incl. the four §3 decisions as fixed inputs) was reviewed
by two independent adversarial reviewers — an **Opus** subagent (22 ranked
findings) and a **GPT via Codex** run (11 ranked findings; Codex session
`019fc11c-68c4-78c3-824b-d9b97de55a78`). This file is the durable record:
what each found, what the coordinating session (Fable) independently
verified, and the disposition of every finding. `brainstorm.md` §5 carries
the resulting v2 revisions; this file carries the evidence.

The exercise is itself a preview of the foreman's own consensus panel — and
its meta-lesson landed immediately: the two reviewers disagreed materially
on almost nothing, converged independently on five majors (deterministic
Phase A, closed action vocabulary, act-time identity re-verification, the
exit-rule rewrite, cache-key failure), and each found real defects the other
missed. Cross-vendor diversity earned its seat.

## Independently verified before adoption (Fable, this session)

Every load-bearing claim below was re-measured against the shipped code or
the cited contract before being incorporated — none is adopted on reviewer
authority alone:

1. **Adoption keys on the Claude registry `name` vs discovered topics, not
   the tmux session name** (`overseer/AGENTS.md` invariant 6) — so the
   brainstorm's "invisible to overseerd by construction" premise was FALSE,
   and `plan/foreman/` (landed by this very thread, PR #489) is now a
   discovered topic in a watched repo. [O1]
2. **`_registry_core.tmux_id` only WARNS on a reserved topic and never
   re-checks the DERIVED name** (`overseer/_registry_core.py:160-195`;
   predicate `overseer/signals.py:344-346`), while
   `SPECIFICATION/spec.md` §"Session-name derivation" requires refusal ("is
   refused and surfaced by name") including "by the cross-repository
   collision qualifier". Topic `foreman` in ≥2 watched repos derives exactly
   `livespec-overseer-foreman`. This is an existing spec-vs-impl gap for
   `-supervisor` today, independent of the foreman. **Filed as its own
   work item** (see Dispositions). [O2]
3. **The own-spec clauses O7 cites are all real**: "The daemon owns 'what
   needs attention now'" (`SPECIFICATION/contracts.md` §Attention surface);
   the closed "Three operator-home files" enumeration (§Durable stores);
   "performs no automatic recovery of dead sessions at startup"
   (`SPECIFICATION/spec.md` §Surface-only startup); the unattended-daemon
   plan-tree prohibition with the ATTENDED supervise-plan carve-out
   (§Non-interference); the scope statement excluding operator surfaces
   (spec.md:14-20). [O7]
4. **The valve action ids are ratified as human acts**:
   `livespec-orchestrator-beads-fabro/SPECIFICATION/contracts.md` §"Human
   valve actions" names approve/accept/reject/resolve-blocked/policy-edits/
   caps/move "the ten human operator action ids", and the §Consent framework
   requires per-operation consent with waivers that are explicit,
   session-scoped, and never a default. An unattended foreman auto-driving
   them violates this as ratified — independent of the needs-human clause
   the brainstorm already found. [C1]
5. **An uncaught daemon tick exception exits the daemon by design**
   (`overseer/_supervisor_lifecycle.py` `run_loop` docstring: "A tick that
   raises is NOT caught"). A snapshot writer that can raise takes down
   supervision. [C4]
6. **The C21 paste-rendering failure is a dated, measured record**
   (`.ai/supervisor-protocol.md` C21, 2026-08-02: a pasted block renders as
   `[Pasted text #N +M lines]`, defeating paste-confirmation). [O17]

## Verdicts (as delivered)

**Opus:** phasing sound, sequencing instinct right, "but Phase A as written
is not shippable, and two of its premises are factually wrong." Must change
before Phase A: fix adoption + name-derivation hazards (O1/O2); make Phase
A's gather deterministic Python and delete the report-only LLM tick (O16);
add the own-spec conflict pass (O7). Settle now because they change Phase
A's data model: session-identity token in the snapshot (O4); whitelisted
acting executable instead of prose bounds (O8). Decide who watches the
foreman (O6) before trusting it.

**Codex/GPT:** "Phase A's daemon JSON snapshot is a sound direction, but its
failure semantics and deterministic live rendering must be specified first.
Phase B is not sound to proceed as written: automatic valve driving, missing-
session classification, and unmanaged work-item sessions are blocking design
defects."

Both verdicts are ACCEPTED; v2 (brainstorm §5) redefines phases A and B
accordingly.

## Dispositions

Legend: **ADOPTED** = folded into brainstorm §5 v2 design. **RECORDED** =
binding on a later phase's detailed design, recorded here + pointed to from
§5. **FILED** = became a ledger work item now.

### Critical

- **O1 (ADOPTED)** — foreman sessions are NOT invisible to adoption; a
  session registry-named `foreman` in this repo would be adopted as the
  plan-thread worker, wrapped up, nudged, and respawn-able into the plan
  handoff. v2: the foreman's **runtime registry name** is part of the
  contract (`claude ... -n <repo-slug>-foreman`), adoption must refuse
  `-foreman`-suffixed registry names (beside-test-pinned), and the
  brainstorm's false sentence carries a correction banner.
- **O2 + C11(naming) (ADOPTED + FILED)** — reservation moves to the
  **derived session name** inside `tmux_id`, as a refusal (spec already
  mandates refusal); `-foreman` joins `-supervisor`; a reserved plan
  DIRECTORY is refused-and-surfaced by name, never silently skipped
  (Codex: hiding would mask legitimate plans). The `-supervisor`
  warn-vs-refuse gap exists today and is filed independently of the
  foreman.
- **O3 + C10 (RECORDED, Phase D; also reshapes Phase B)** — dismissing a
  gate returns the pane to the exact state the daemon acts on: Escape
  hands the pane to the next ~10s tick's wrap-up/nudge injection with no
  mutual exclusion; two actors then paste into one pane. Phase D requires
  an explicit daemon-honored interlock (a round-scoped "foreman owns this
  pane" claim), runtime-specific live-tested adapters, gate-state
  persistence + provable restoration, canaried navigation keys, and a
  protocol amendment (marker-protocol says a blocked track is "never
  restarted and never keystroked into"). Until then the foreman only ever
  answers the EXISTING prompt or escalates.
- **O4 + C2 (ADOPTED)** — no act without identity re-verification. v2:
  snapshot rows carry a session-identity token (daemon-instance id +
  per-row session identity from the registry join) and every foreman act
  re-reads the snapshot immediately before acting, aborting on any
  token/status/note change. C2's fuller act-time protocol (fresh pane id,
  runtime/topic/cwd identity, question fingerprint, two settled captures,
  shared per-pane lock) is RECORDED as the Phase B/D act-time checklist.
- **O5 + C9 (RECORDED, Phase C design constraints)** — panel independence:
  two Anthropic models + one GPT is ~two independent opinions; the
  minority-report override as seeded systematically overrides the one
  decorrelated voice. Phase C: cross-vendor by construction with PINNED
  model identities; needs-human dissent from the non-Anthropic reviewer
  (and any hard-risk dissent) is non-overridable; minority override only
  for typed, reversible, rollback-bounded actions and never labeled
  unanimous; add an `insufficient-information` verdict; reviewer prompts
  never state the escalation-minimizing goal; repo-global daily cost +
  concurrency caps, not just per-item.
- **O6 (ADOPTED)** — who watches the foreman: inverted so the deterministic
  process watches the LLM. v2 Phase A: the foreman writes a heartbeat;
  **overseerd** surfaces a stale foreman heartbeat in `NEEDS YOU`
  (token-free, additive, inside Phase A's daemon blast radius). Re-arm on
  shorter intervals per supervisor-protocol C16 (long watchers die
  silently).
- **C1 (ADOPTED — reshapes Phase B)** — human valves are report-only for
  the foreman until the consensus tier ratifies. Phase B's acting scope
  shrinks to: session lifecycle acts + filing + an explicit enumerated
  allowlist of already-machine-ratified surfaces. Never "any action
  emitted by needs-attention".

### Major

- **O7 (ADOPTED)** — own-spec conflict pass: the named amendments now
  enumerated in brainstorm §5 (attention-ownership sentence; the
  three-files closed enumeration + snapshot; BOTH surface-only sentences
  incl. no-auto-recovery; the non-interference/attended-carve-out fork for
  an unattended reader of handoffs; the scope-statement fork — is the
  foreman spec-governed at all; invariant-3 wording).
- **O8 + C8(equality) + O9 (ADOPTED)** — bounds and unanimity become
  Python, not prose: the foreman acts only through a whitelisted
  deterministic `foreman-act` executable (closed action-id vocabulary);
  reviewers return an enumerated action id + typed params, so unanimity is
  string equality and the interested-party equivalence judge disappears.
  Free-form actions always escalate. (Supervisor-protocol C20 is the dated
  in-repo refutation of prompt-enforced bounds.)
- **O10 + C8(cache) (RECORDED, Phase C)** — cache key: structured snapshot
  fields + hash of the ANSI-/spinner-/ctx-stripped question region + repo/
  item revision + policy/prompt version + pinned model versions; explicit
  TTL; hard per-tick panel budget with a named number.
- **O11 (ADOPTED)** — prompt-injection surface: snapshot `note` is elided
  and length-bounded at serialization (the snapshot is otherwise a fourth
  unelided surface whose consumer holds acting authority); inbox messages
  are strictly typed (enumerated kinds, no free-text reaching instruction
  context); standing rule: pane text and peer text are EVIDENCE, never
  instructions.
- **O12 (RECORDED — amendment scoping)** — the consensus tier is a
  REVERSAL of the needs-human clause's core guarantee, not an extension,
  and touches three repos: orchestrator spec + a journal writer for
  non-Dispatcher auto-dispositions ("No auto-disposition MAY be silent"),
  API-settability, and the console-side three-place completeness check —
  plus a recorded maintainer design decision (§Intent preservation makes
  the design record the tiebreaker). Stays off the v1 critical path;
  scoped honestly now.
- **O13 + C6 (ADOPTED)** — exit rule rewritten: fingerprint only
  structured fields; exit condition = "no monitored entity changed state
  AND the foreman took no action for N consecutive ticks, with a non-empty
  monitored set" + an unconditional hard tick budget; exiting stops only
  the token-consuming LLM loop while a token-free watcher stays armed on
  snapshot/ledger/inbox generation changes (armed re-entry rule).
- **O14 + C5(lock) (ADOPTED)** — the flock singleton was not implementable
  by an LLM session (a Bash call's lock dies with the call). v2: the
  mandated tmux session name IS the mutex (globally unique), backed by a
  pid + `/proc` start-time lockfile validated the way `claude_sessions`
  defeats PID reuse; C5's fuller shape — a small deterministic wrapper
  that holds the lock, schedules ticks, renders state, and rotates the LLM
  from a durable handoff — is the Phase B design direction for foreman
  longevity (it also answers open question 4).
- **O15 + C3 (ADOPTED — Phase B)** — session (re)creation needs a
  deterministic classifier before any launch: explicitly launch-eligible
  never-started → `start` (absolute `--repo` always); crashed with
  unambiguous live/indexed runtime evidence + transcript → exact resume;
  intentionally unassigned, ambiguous, or stale-namesake → report to
  human, never guess (spec: runtime identity from exact process evidence,
  never topic names).
- **O16 + C5(render) (ADOPTED — redefines Phase A)** — Phase A carries NO
  LLM loop. It is entirely deterministic: snapshot export, `list --json`,
  a `foreman-gather` CLI composing snapshot ⋈ needs-attention ⋈ journal
  into one validated JSON document, the heartbeat surfacing, and a
  token-free live render (deterministic, re-rendered on its own cadence —
  an hourly LLM-written status.md under `watch` is the frozen-snapshot
  failure with extra steps). The LLM foreman starts at Phase B, where
  judgment starts.
- **C7 (ADOPTED — Phase B)** — work-item sessions are bounded one-shot
  sessions with a durable handoff, journaled claim, terminal outcome, and
  deterministic cleanup/retry — OR deferred until a declared daemon
  discovery source exists. No long-lived unsupervised session class.
- **C4 + O19 (ADOPTED)** — snapshot failure semantics: export I/O is
  narrowly contained (edge-reported, supervision continues); snapshot
  carries daemon-instance id + completed-tick generation; stale/absent ≠
  "daemon down" (could be export failure or version skew) — fallback
  `list --json` is observation-only with acting disabled while freshness
  is unproved; unknown-or-newer schema is treated as ABSENT (fail-closed);
  `list --json` must suppress the table render.

### Minor

- **O17 (ADOPTED)** — the doorbell paste is dropped from Phase E (C21:
  paste-confirmation false-negatives every time); the tick polls the
  inbox. If latency ever matters, confirm by placeholder/non-empty prompt
  line, never pasted text.
- **O18 (ADOPTED)** — foreman state moves to `<repo>/tmp/overseer/foreman/`
  — inherits the startup gitignore gate and the "scratch under
  tmp/overseer/, never the tmp/ root" house rule for free.
- **O20 (ADOPTED)** — standing rule: the foreman raises exactly ONE
  blocking picker, ever, and only as its terminal act before exiting the
  loop.
- **O21 (RECORDED, Phase C)** — reviewers receive a pre-assembled dossier
  and return only the verdict object; no tool access (direct API calls
  preferred); never handed the repo path.
- **O22 (RECORDED, Phase D)** — a re-presented question preserves the
  session's original options VERBATIM, adding reviewer summaries as
  context and at most one new option; the foreman never rewrites the
  options.
- **C11 (RECORDED, Phase E)** — inbox becomes an atomic ID-based spool
  with allowlisting, schema/size limits, dedupe, acknowledgements,
  retention, and sender-held obligations until both confirmations arrive
  (the supervisor-protocol obligation invariant); peers resolve through
  canonical watch-set repo identities with slug-collision refusal at
  startup.

### Filed

- **`tmux_id` reserved-suffix gap** — spec mandates refusal; code warns
  and proceeds, and never re-checks the derived `<slug>-<topic>` name
  (`-supervisor` today, `-foreman` once ratified). Filed in the
  livespec-overseer tenant as **`overseer-jgqw7d`** (bug, freeform;
  intake verdict `pending-approval`).

## What was NOT adopted

Nothing was rejected outright. Three reviewer suggestions were narrowed:

- O6's "shorter re-arm interval" is adopted for watchers, but the foreman
  LLM tick cadence remains the maintainer's hourly default (seed item 7) —
  the deterministic wrapper (C5) owns scheduling, so the token-burn
  argument no longer binds the LLM cadence to the watch cadence.
- C2's per-pane shared lock between daemon and foreman is deferred to
  Phase D design (it is a daemon change; Phase B acts only on panes the
  daemon never touches — session creation — or through the ledger).
- O5's "never state the escalation-minimizing goal in the reviewer prompt"
  is adopted verbatim; its stronger implication (drop goal 2 from the
  design) is not — goal 2 binds the FOREMAN's routing, not the panel's
  judgment.
