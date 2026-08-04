# Foreman — brainstorm & architecture proposal (v1, 2026-08-02)

Companion to `seed-prompt.md` beside this file (the verbatim maintainer seed).
This document grounds the seed's sketch against what actually exists in the
repo and fleet today, proposes an architecture, and records the maintainer
decisions taken the same session (§3). The thread's ledger epic anchor is
**`overseer-z5fo4y`** (status is READ from the ledger; never from this file).

Grounding evidence was gathered 2026-08-02 from: `overseer/` (all 26
`_supervisor_*` collaborators enumerated), `.claude-plugin/prose/overseer.md`,
`.claude-plugin/prose/supervise-plan.md`, `overseer/marker-protocol.md`,
`SPECIFICATION/`, the orchestrator plugin
(`livespec-orchestrator-beads-fabro`), `livespec-runtime`'s work-item types,
and the dev-tooling fleet contract.

---

## 1. What exists today (the load-bearing facts)

### The daemon has NO machine-readable state export
The daemon's world-view lives in-memory on the `Supervisor` dataclass and is
rendered as a terminal paint (`_supervisor_render.render_table`) plus
edge-triggered `daemon.log` alert lines (history, not state). The closest
public "view of the world" is the frozen `RowView` dataclass
(`_supervisor_view.py:133-159`): `topic, repo, tmux, ctx, status, note,
runtime, progress_now, human_wait, round_open, acked`. The read-only path
`Supervisor.tick(act=False) → list[RowView]` performs no mutation and takes no
locks.

### Status vocabulary (17 statuses; 8 are attention)
`ATTENTION_STATUSES = blocked:human, codex-unindexed, ctx-stale, danger,
ready-uncertifiable, session-gone, shell-prolonged, winddown-starved` plus
note-matched `BAD state file` / `resume-pending`. `unassigned` is deliberately
NOT attention ("startable is not stuck"). `RowView.human_wait` is precomputed:
`gate || claude_status=="waiting" || blocked-declaration`.

### Discovery is directory-based; supervisor pairs are second rows
`discover_plans` enumerates `plan/*/` dirs only (never opens files), skips
`archive/` and `*-supervisor` topics. A plan with `handoff.md` but no
`supervisor-handoff.md` is tracked normally — the daemon `.exists()`-checks
`supervisor-handoff.md` only to decide whether to evaluate a **pair row**
(`<topic>-supervisor` session, `_supervisor_pair.py` stall ladder). So the
seed's item 2.2 ("plans without supervisor") is already *observed* by the
daemon; what nobody does today is *act* on the observation semantically.

### Session naming (ratified)
Bare plan topic; `<repo-slug>-<topic>` (single dash) only on genuine cross-repo
collision. Supervisor session = worker session + `-supervisor`. Work-item ids
(`overseer-x29`) are tmux-name-safe.

### The daemon's invariants that shape the foreman (but do NOT bind it)
- **Invariant 3 (surface-only):** the *daemon* never auto-spawns a session for
  an unassigned plan; "launching a plan is a deliberate act (`start`,
  user-initiated)". The `supervisor.py start` CLI already does everything the
  foreman needs for launches (create session, launch claude, paste resume
  line, map it). The foreman becomes the *deliberate operator* this invariant
  reserves the right for — the invariant's wording ("user-initiated") will
  need a ratified update to "operator-initiated (human or foreman)".
- **Cardinal rule:** only a session-written `ready` restarts anything. The
  foreman must NEVER write `ready`/`blocked`/`winding-down` into a track's
  `.overseer-state` — that forges a declaration. (The state file is
  authorship-unguarded; discipline, not mechanism, protects it.)
- **Notify-never-block** binds the *overseer bottom pane*. The foreman is a
  new actor and CAN drive gated panes — that is precisely its new capability
  (seed item 5e). No dismiss-a-prompt precedent exists anywhere in the daemon
  (the only key it ever sends is Enter); this is greenfield mechanics, though
  `tmuxio`'s bracketed-paste + verified-submit + exact-match targeting +
  `is_structured_gate` detection are all reusable as a library.

### Work-item side (orchestrator plugin)
- 7 statuses: `backlog, pending-approval, ready, active, acceptance, blocked,
  done`. Lanes derived by `lane_of` (stored `blocked` reason `needs-human` |
  `infra-external`; derived `dependency`).
- **There is no `needs-regroom` status** — non-convergence bounces to
  `backlog`. Four factory-ejection shapes matter to the foreman:
  1. bounce → `backlog` (regroom needed; `stalled-no-progress` outcome)
  2. in-loop human gate → `blocked` + `needs-human` + admission forced `manual`
  3. acceptance-rework cap exceeded → `blocked` + `needs-human`
  4. AI-acceptance fail under cap → `active` (auto-rework; no action needed)
  Plus two report-only strandings: host-only items (`factory_safety` set) and
  stranded merged dispatches. All escalations are journaled to
  `<repo>/tmp/fabro-dispatch-journal.jsonl` — readable without the ledger.
- Automation valves (`.livespec.jsonc` → `dispatcher.*`): `auto_approve_ready`
  (admission), `acceptance_mode` (ai-only fleet-wide now), `wip_cap`,
  `host_dispatch_cap`, per-item label overrides. Human-valve availability is a
  predicate: `approve` (pending-approval + effective-manual), `accept`/`reject`
  (acceptance), `resolve-blocked:<id>:ready|backlog` (blocked + needs-human).
- `needs_attention.py --json` already composes the per-repo attention list
  (human valves, impl next, spec next, plan threads, hygiene, host-only,
  stranded, untriaged) into a validated `AttentionItem` schema with
  copy-pasteable handoff commands. **The foreman should consume this, not
  reimplement it.**
- `drive.py --action <action-id>` is the complete acting surface (approve /
  accept / reject / resolve-blocked / move / set-* / impl:<id>).

### Fleet membership: D5 forbids reading the fleet manifest
A shipped overseer must not read `.livespec-fleet-manifest.jsonc` (decision
D5, recorded in `_registry_discovery.py` / `_registry_core.py`). The
sanctioned membership signals are: the watch-set
(`~/.livespec-overseer-repos.json`) + the target repo's own `.livespec.jsonc`
(absence ⇒ ungoverned — the `_PACK_POLICY_UNGOVERNED` evidence-based
precedent). The seed's "membership in fleet config file" gate must be
implemented as **"pwd has `.livespec.jsonc` AND pwd is in the watch-set"**,
not as a manifest read.

### Governance rules that constrain the foreman (ratified, elsewhere)
1. **"Every needs-human escalation still reaches a human"**
   (orchestrator contracts.md §1843-1856): no policy setting may auto-dispose
   a `blocked_reason: needs-human` item. A consensus panel auto-resolving
   ledger needs-human items **conflicts with this as ratified** — needs either
   a spec amendment (opt-in consensus quorum tier) or a foreman scoped to
   recommend-only on ledger items.
2. **"FILE cross-repo freely; never ADMIT or PRIORITISE in another repo's
   queue"** (supervisor-protocol §668-698): cross-repo foreman coordination
   must be delegation-by-filing (or mailbox), never driving another repo's
   valves. This aligns exactly with the seed's 1-1 foreman-repo ownership.
3. **"No required cross-repo loop driver"** (livespec core spec §397): the
   foreman must stay optional per-repo. Fine — it is.
4. **Never REMOVE/WEAKEN/SKIP an existing check** (decision-vetting rubric):
   inherit as a hard bound on consensus-authorized unblock actions.
5. **stdlib-only** is load-bearing for the overseer package (uv `--no-project`
   shebang). gRPC/IPC frameworks are structurally excluded; a JSON snapshot
   file is the stdlib-native answer.

### Loop precedent
No component named "foreman" exists (greenfield). Precedents: the token-free
daemon loop; the budget-bounded dispatcher loop; supervise-plan's "armed
re-entry" doctrine (pane watcher primary, `ScheduleWakeup` backstop, "an
intention is not a mechanism"); a systemd user timer running a dispatcher
subcommand every 5 min; the harness `/loop` skill (installed, unused by the
fleet). The overseer's founding history warns: an LLM pane on a timer is the
context-blowup + frozen-snapshot failure — mitigations below.

---

## 2. Proposed architecture

### Components

```
┌────────────────────────────────────────────────────────────────────┐
│ overseerd (unchanged role, ONE new feature)                        │
│   + per-tick atomic snapshot: ~/.livespec-overseer-status.json     │
│     {schema: 1, at: <iso>, tick_seq: N, rows: [RowView…]}          │
└────────────────────────────────────────────────────────────────────┘
                 ▲ reads (mtime = staleness signal)
┌────────────────────────────────────────────────────────────────────┐
│ foreman (NEW: LLM session, one per repo, hourly /loop)             │
│   tmux session: <repo-slug>-foreman                                │
│   scratch/state: <repo>/tmp/overseer/foreman/                               │
│   per tick:                                                        │
│     1. read daemon snapshot (filter to own repo)                   │
│     2. read needs_attention.py --json (own repo)                   │
│     3. read tmp/fabro-dispatch-journal.jsonl tail                  │
│     4. diff against tmp/overseer/foreman/fingerprint.json                   │
│     5. ACT: start missing sessions / run consensus / drive valves  │
│     6. write tmp/overseer/foreman/status.md + NEEDS YOU section, stamped    │
│     7. re-arm (loop) or exit-with-resume-question (2h unchanged)   │
└────────────────────────────────────────────────────────────────────┘
                 │ spawns per blocked item
┌────────────────────────────────────────────────────────────────────┐
│ consensus panel (per blocked question, cached by fingerprint)      │
│   Fable subagent · Opus subagent · GPT-5.x via codex plugin        │
│   verdict schema → agreement matrix → act / minority-override /    │
│   escalate-with-summaries                                          │
└────────────────────────────────────────────────────────────────────┘
```

### State exposure (seed 2.1): daemon-written JSON snapshot
One atomic write per tick (same `atomic_write` + `file_lock` machinery the
stamp sidecar uses), versioned schema, `$HOME`-anchored like the other three
stores. Strongly typed on both ends (serialize `RowView`; foreman-side reader
validates schema version). Staleness is detectable (`at` + file mtime); a
stale/absent snapshot means "daemon not running" and the foreman falls back to
the one-shot read-only CLI (`supervisor.py list --json` — a second small
addition) or surfaces "daemon down" as its own NEEDS-YOU item. Rejected:
gRPC/IPC (violates stdlib-only, overengineered); parsing the rendered table
(fragile); foreman importing the package and running its own `tick(act=False)`
as the *primary* path (version-skew with the running daemon, duplicate pane
captures; fine as fallback).

### Plans without supervisors (seed 2.2)
Already observed by the daemon. Foreman policy per plan: if
`supervisor-handoff.md` exists but the supervisor session is dead → recreate
it (session + kick with the binder). If no `supervisor-handoff.md` → the
foreman monitors the worker directly (the snapshot's `human_wait` /
`progress_now` / attention statuses); generating a missing supervisor handoff
stays a deliberate human choice (it is a reviewed PR artifact via
supervise-plan — too heavy to auto-create).

### Non-plan work items (seed 3)
Consume `needs_attention.py --json` + the dispatch journal. The foreman drives
the mechanical moves the config already authorizes (`drive.py` valves under
the repo's own `credential_wrapper`). Sessions named exactly after the
work-item id are created ONLY for items that need interactive human-facing
work (ejection shapes 1-3, host-only, stranded) — not for every ready item
(the factory owns those; `wip_cap`/`host_dispatch_cap` stay the factory's
levers). Note: these work-item sessions are invisible to overseerd (discovery
is plan-dir-based), so v1 leaves their context-lifecycle unmanaged; extending
overseerd with a second, foreman-declared discovery source is future work.

### Missing-session creation (seed 4)
- plan with `handoff.md`, no session → `supervisor.py start --repo <abs>
  --topic <t>` (exists today; foreman is the deliberate actor).
- `supervisor-handoff.md`, no supervisor session → new foreman mechanic
  (create `<worker>-supervisor` session, kick with binder boot).
- qualifying work item, no session → new foreman mechanic (create session
  named `<work-item-id>`, seed prompt = item + journal evidence + valid
  valves).
Idempotency: exact-membership session-existence check (reuse
`tmuxio.session_exists` discipline, never `has-session` prefix-match).

### The consensus panel (seed 5)
Reviewers: Fable (Agent tool, default model), Opus (Agent tool, `model:
opus`), GPT (codex plugin subagent). Each gets the same dossier: the blocked
question verbatim (pane capture / journal record), the plan handoff or
work-item record, repo context, and the escalation taxonomy (non-two-way-door,
architecture, significant-tech-debt-for-expedience, tradeoffs, high-impact UX
⇒ needs-human). Each returns a structured verdict:

```json
{"verdict": "unblock" | "needs-human",
 "action": "<one imperative sentence, or null>",
 "rationale": "<short>"}
```

Decision matrix (as seeded):
- 3× unblock, equivalent actions → act automatically.
- 1× needs-human + 2× equivalent unblock → minority-report round: show the
  dissent to the two; if both hold → act; else → escalate.
- anything else → escalate: re-present in the owning pane with per-reviewer
  summaries + an updated AskUserQuestion (Codex: see the native-picker note
  below — the prose-choice fallback narrows to the cases the native tool
  cannot cover).

> **UPDATE (2026-08-02, maintainer; seed Addendum 2 — Codex native question
> picker):** Codex supports a NATIVE structured question tool,
> `request_user_input` (header/id/question/options with label+description),
> gated behind the `default_mode_request_user_input` feature, which the
> maintainer is enabling system/user-wide in `~/.codex/config.toml`. A
> SKILL.md's Markdown instructions are enough to make the model emit the
> native call. So a Codex worker CAN re-present an escalation as a real
> picker, and the seed's "if Codex doesn't support AskUserQuestion" hedge is
> RESOLVED for interactive Default-mode sessions. Precise scope, which Phase
> C/D design must respect: (a) interactive CLI only — NOT `codex exec`, so
> factory/exec contexts keep the prose fallback; (b) the feature is named
> for DEFAULT mode, while the fleet's tracked Codex sessions run YOLO
> (`--dangerously-bypass-approvals-and-sandbox`) — whether the tool is
> exposed there is UNMEASURED, so the shipped marker-protocol claim ("Codex
> in YOLO mode cannot raise a structured question") stands until a live
> measurement says otherwise. That measurement is a named Phase D
> experiment; if YOLO sessions do get the tool, the daemon's existing gate
> detection already covers the rendered picker (`is_structured_gate` matches
> the `› N.` cursor), so blocked:human classification needs no change.

Design details the plan must pin down:
- **Action equivalence** is judged by the foreman (it's an LLM; a fourth
  judge model is overkill), against normalized action sentences.
- **Caching/budget:** verdicts recorded in
  `tmp/overseer/foreman/consensus/<key>.json`, keyed by a fingerprint of the question
  text + item state, so an unchanged blocked state is never re-billed. Cap
  consensus rounds per item per day.
- **Hard bounds on auto-actions:** never weaken/skip a check, never
  `--no-verify`, never touch another session's worktree/branch, never write a
  track's `.overseer-state`, never mutate another repo's queue. Allowed:
  answer the question in the owning pane, drive.py valves in own repo, file
  work items (any repo), start sessions, adjust own-repo deps/labels.
- **Ledger needs-human items:** see Open Question 2 — contract conflict.

### Gate-driving mechanics (seed 5e — new foreman capability)
For case (e) re-presentation: dismiss the pending picker (Escape), verify the
pane returned to idle input, then bracketed-paste an instruction telling the
session to re-present with reviewer summaries incorporated. For a
consensus-authorized unblock of a session-owned question, prefer answering the
EXISTING prompt (select an option / type into "Other") over
dismiss-and-reask. All of this reuses tmuxio mechanics but needs live
experimentation (how Claude Code TUI reacts to Esc on an AskUserQuestion; what
the session sees as the interrupt). Interaction with the daemon: a gated pane
is `blocked:human` in the daemon's view; foreman action makes it transition
briefly and possibly re-enter — harmless to daemon *acts* (it never acts on
gates), but the two attention surfaces (daemon NEEDS-YOU vs foreman
NEEDS-YOU) must be reconciled — see Open Question 3.

### The foreman NEEDS-YOU surface (seed 6)
Foreman writes `tmp/overseer/foreman/status.md` every tick: a stamped table of
monitored entities + a `NEEDS YOU:` section naming the tmux session holding
each unresolved prompt, with reviewer-summary one-liners and jump commands.
Being LLM-printed, the transcript copy ages (the frozen-snapshot lesson) — so
the transcript always carries the timestamp and points at the file/pane as
the live copy. Optionally a dumb `watch -n 30 cat tmp/overseer/foreman/status.md` pane
gives a genuinely live render for free (token-free, like the daemon's table).

### The loop (seed 7)
`/loop` (harness skill) with 1h interval; each tick is one full pass. Exit
rule: if the fingerprint (all monitored blocked states + question texts +
attention set) is IDENTICAL for 2 consecutive ticks AND every monitored
session is blocked → exit the loop and raise a resume AskUserQuestion.
Fingerprint persisted to `tmp/overseer/foreman/fingerprint.json` so a foreman restart
doesn't reset the clock.

> **CORRECTION (review, O14/C5/O13/C6):** the flock singleton as originally
> written here is not implementable by an LLM session — a Bash call's lock
> dies when the call exits. v2: the mandated tmux session name IS the mutex,
> backed by a pid + `/proc`-start-time lockfile (PID-reuse-safe), with a
> small deterministic wrapper owning lock, tick scheduling, and LLM rotation
> from a durable handoff. The exit rule is also rewritten: structured-field
> fingerprints only, "no state change AND no foreman action for N ticks with
> a non-empty monitored set", a hard tick budget, and exiting stops only the
> LLM loop while a token-free watcher stays armed. See `review-findings.md`.

Entry refuses if pwd lacks `.livespec.jsonc` or isn't in the watch-set
(D5-compliant gate).

**Required tmux session name (seed item 8): `<repo-slug>-foreman`, exactly.**
The skill REFUSES to run outside a tmux session with exactly that name (check
via `$TMUX_PANE` → session name, the overseer-start precedent — never
improvise tmux detection). The name is a CONTRACT, not a convention: it is
what makes every foreman discoverable and addressable by every other foreman
(and by the human) with zero registry.

> **CORRECTION (2026-08-02 external review, findings O1/O2 — the sentence
> this replaces claimed foreman sessions are "invisible to overseerd plan
> discovery by construction". That was FALSE in two ways.)** (1) Adoption
> keys on the Claude REGISTRY name matched against discovered topics, not
> the tmux session name — and `plan/foreman/` is itself a discovered topic
> in a watched repo as of PR #489, so a session registry-named `foreman`
> here would be adopted as the plan-thread worker, wrapped up, nudged, and
> respawn-able into the plan handoff. The foreman's RUNTIME registry name
> (`claude ... -n <repo-slug>-foreman`) is therefore part of the contract,
> and adoption must refuse `-foreman`-suffixed registry names, pinned by a
> beside-test. (2) The reservation belongs on the DERIVED session name
> inside `tmux_id`, as a REFUSAL — the spec already mandates refusal, but
> the shipped check only warns on the topic and never re-checks the derived
> form, so topic `foreman` on a cross-repo collision derives exactly
> `livespec-overseer-foreman`. That `-supervisor` gap exists today,
> independent of the foreman, and is filed as its own work item. A reserved
> plan DIRECTORY is refused-and-surfaced by name, never silently skipped.
> See `review-findings.md`.

### Cross-repo coordination (seed's HOWEVER + item 8)
Discovery is two-layered, both zero-registry:
- **Liveness/addressing:** the mandatory `<repo-slug>-foreman` session name.
  `tmux list-sessions` filtered to `*-foreman` IS the live-foreman roster.
  **CORRECTION (review, O17):** the doorbell paste originally proposed here
  is dropped — supervisor-protocol C21 measured that a pasted block renders
  as `[Pasted text #N +M lines]`, so paste-confirmation false-negatives
  every time; the tick polls the inbox instead. If latency ever justifies a
  wake signal, confirm by placeholder/non-empty prompt line, never by
  pasted text.
- **Durable state/requests:** each foreman publishes
  `<repo>/tmp/overseer/foreman/status.json` (schema-versioned) and reads
  `<repo>/tmp/overseer/foreman/inbox/<from>-<ts>.json` requests on each tick. The
  paste channel carries no payload semantics — the inbox file is the message;
  the paste is only the doorbell. (A paste into a mid-turn LLM is lossy;
  files are not.)
Seed item 8 allows "an API as well" — that can start as exactly these two
primitives wrapped in a small stdlib helper (`foreman_comms.py`: `roster()`,
`send(repo, request)`, `publish_status(...)`), leaving room for a richer
transport later without changing the contract.

Delegation follows the ratified rule: file into the peer repo's queue
(capture-work-item) or drop an inbox request — never drive a peer's valves,
never admit or prioritize in a peer's queue. Cross-repo dependency blockers
become: foreman A files/annotates in repo B + records the obligation
(supervisor-protocol's obligation-record schema is reusable) + reports in its
own NEEDS-YOU if stalled.

---

## 3. Maintainer decisions (2026-08-02, same session)

The four forks below were put to the maintainer as clickable questions; the
answers are DECIDED and the "Open questions" section is retained only for the
rationale each option carried.

1. **Ledger needs-human vs consensus → AMEND THE CONTRACT NOW.** Propose an
   opt-in `consensus` policy tier in the orchestrator spec (route (a)), so
   repo config can delegate specific valves (e.g. resolve-blocked,
   acceptance) to a unanimous panel. This puts a cross-repo spec-lifecycle
   item (a `/livespec:propose-change` filed in
   livespec-orchestrator-beads-fabro) on the plan — but NOT on the v1
   critical path, since consensus is Phase C and v1 is A+B. Until it
   ratifies, needs-human ledger items stay human-clicked.
2. **Transport → DAEMON JSON SNAPSHOT.** overseerd atomically writes the
   versioned status snapshot each tick; read-only CLI fallback when the
   daemon is down.
3. **Attention surfaces → BOTH, with the daemon's UNCHANGED.** Maintainer's
   words: keep overseer/daemon logic unchanged, INCLUDING its NEEDS-YOU
   reporting; the daemon's attention output is a SUBSET of the new foreman
   attention-managing logic and surface. So the foreman never modifies,
   suppresses, or supersedes the daemon's rendering — it ingests those rows
   (via the snapshot) and builds the richer decision-annotated surface on
   top. (Read consistently with decision 2: the snapshot export is an
   additive daemon feature; the attention/evaluate logic itself is
   untouched.)
4. **v1 scope → PHASES A+B.** v1 = snapshot export + report-only foreman
   loop, then mechanical acts (missing-session creation, config-authorized
   drive.py valves). Consensus (C), gate-driving (D), federation (E) follow.

## 3a. Open questions as originally posed (rationale record)

1. **Snapshot transport.** Daemon-written JSON snapshot per tick (recommended)
   vs foreman-side read-only tick as primary. (Affects: an overseerd change +
   spec amendment vs none.)
2. **Ledger needs-human vs consensus.** The ratified orchestrator contract
   says every needs-human escalation reaches a human. Options: (a) amend it —
   add an opt-in policy value (e.g. `consensus` tier for
   admission/acceptance/blocked-resolution) so config can delegate specific
   valves to the panel; (b) keep the contract — the panel only *prepares* a
   recommendation on ledger items and the human still clicks; consensus
   auto-acts only on session-owned blocked questions (which that contract does
   not govern). (b) is shippable without cross-repo spec work; (a) is the
   fuller realization of goal 2.
3. **One attention surface or two.** Daemon NEEDS-YOU (session liveness) and
   foreman NEEDS-YOU (semantic decisions) will overlap on blocked:human rows.
   Options: foreman's surface supersedes (it annotates every daemon row it is
   handling, and the human reads the foreman's); or strict split (daemon =
   mechanical liveness, foreman = decisions) with cross-references.
4. **Foreman session longevity.** An hourly LLM loop accumulates context over
   days. Options: self-managed wind-down (foreman writes its own
   `tmp/overseer/foreman/handoff.md` and restarts itself between ticks when low);
   accept manual restarts; or (later) make overseerd able to track
   foreman-declared sessions.
5. **v1 scope cut.** Suggested phasing below — is consensus in or out of v1?

## 4. Proposed plan phasing (v2, post-review — supersedes the v1 cut)

- **Phase A — observe, entirely deterministic (NO LLM loop).** overseerd
  snapshot export (atomic per tick; failure-contained so export I/O can
  never kill the daemon; carries schema version, daemon-instance id,
  completed-tick generation, per-row session-identity token; `note` elided
  at serialization) + `list --json` (table render suppressed; observation-
  only fallback) + a `foreman-gather` CLI composing snapshot ⋈
  `needs_attention.py --json` ⋈ dispatch-journal tail into one validated
  JSON document + the foreman heartbeat surfaced by overseerd in
  `NEEDS YOU` (the daemon watches the LLM, never the reverse) + a
  token-free live render. All beside-test-pinned. Also: the `tmux_id`
  derived-name refusal (with `-foreman` reserved) and the adoption refusal
  of `-foreman` registry names.
- **Phase B — the LLM foreman, acting narrowly.** Entry gate + tmux-name
  mutex + deterministic wrapper (lock, tick scheduling, LLM rotation from
  a durable handoff). Acts ONLY through a whitelisted `foreman-act`
  executable: session lifecycle (behind the deterministic never-started /
  crashed-resume / ambiguous-report classifier; absolute repo paths;
  work-item sessions as bounded one-shots with journaled claims), filing,
  and journal triage. Human valves are REPORT-ONLY (they are ratified
  human acts; C1). Act-time re-verification against a fresh snapshot read.
- **Phase C — consensus:** the three-model panel per the recorded design
  constraints (cross-vendor pinned identities, closed action vocabulary →
  unanimity is string equality, asymmetric non-overridable dissent,
  `insufficient-information` verdict, dossier-only no-tool reviewers,
  structured cache key + TTL + hard budgets).
- **Phase D — gate driving:** answer-existing-prompt first; dismiss-and-
  re-present only after live TUI experimentation, a daemon-honored
  per-pane interlock, gate-state persistence with provable restoration,
  verbatim-options preservation, and a marker-protocol amendment.
- **Phase E — federation:** peer status files + typed atomic inbox spool
  (allowlist, dedupe, acks, retention, sender-held obligations),
  watch-set-identity peer resolution with collision refusal, cross-repo
  delegation-by-filing. No doorbell paste.

Spec-side, enumerated (review O7/O12): livespec-overseer SPECIFICATION
amendments for the snapshot export (§Durable stores' closed three-file
enumeration), the attention-ownership sentence ("the daemon owns 'what
needs attention now'" — decision 3's superset surface needs the clause
amended, not just the daemon left unchanged), BOTH §Surface-only startup
sentences (first launch AND dead-session recovery become "operator (human
or foreman)" acts), the §Non-interference fork (an unattended foreman
reading handoffs sits between the unattended-daemon prohibition and the
ATTENDED supervise-plan carve-out), the scope-statement fork (whether the
foreman is spec-governed at all), and the session-name derivation refusal.
Orchestrator-side (decision 1, off the v1 critical path): the consensus
tier is honestly a three-repo amendment — spec + journaled auto-
dispositions + API-settability + console completeness check — anchored by
a recorded maintainer design decision.

## 5. External review record (2026-08-02)

The full plan was adversarially reviewed by an Opus subagent (22 findings)
and a GPT/Codex run (11 findings); every load-bearing claim was
independently re-verified against the shipped code and contracts before
adoption. Both verdicts accepted; the v1 Phase A/B cut was rewritten as
above. The complete per-finding record — verification evidence,
dispositions (adopted / recorded-for-phase / filed), and the narrowed
items — is `review-findings.md` beside this file. Notable: the two
reviewers converged independently on five majors and each caught real
defects the other missed — the plan's own cross-vendor panel premise,
previewed.
