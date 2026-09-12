# remove-supervisor-skill — what "the supervisor skill" resolves to, and the cut

Maintainer directive (2026-09-12)
---------------------------------

Deprecate and remove the `livespec-overseer:supervisor` skill; it is not
useful. Remove all references to it across the entire fleet. Do NOT touch the
other skills — `overseer`, `caam-anthropic-loop` and `drain-backlog` stay.
Foreman MAY be removed in the future; for now, supervisor only.

Finding 1 — no plugin skill named `supervisor` exists, or ever did under that name
---------------------------------------------------------------------------------

Measured 2026-09-12 at HEAD eed752f2 and at release 5.9.2 (ba75a128, the
plugin build the harness just installed):

- Shipped skills in all three harness trees (`.claude-plugin/skills/`,
  `.claude-plugin/.codex-plugin/skills/`, `.claude-plugin/.pi-plugin/skills/`)
  are exactly `caam-anthropic-loop`, `drain-backlog`, `overseer`.
  `tests/test_shipped_skill_surface.py` pins that set and pins `foreman`,
  `grooming` and `supervise-plan` as RETIRED.
- `git log --all -S "livespec-overseer:supervisor"` returns zero commits. The
  only supervisor-flavoured skill in history was `supervise-plan` (added
  d126ccff, removed 32e771af under SPECIFICATION v047 on 2026-09-06).
- The literal `livespec-overseer:supervisor` occurs nowhere under
  `/data/projects/*` nor under `~/.claude`.

So there is no skill directory to delete. What the directive can only refer
to is the thing that survived the seat retirement: the supervisor ROLE.

Finding 2 — what survives is the supervisor PAIR-MEMBER role and its fleet protocol
-----------------------------------------------------------------------------------

The retired `supervise-plan` seat AUTHORED the supervisor binder. The daemon
still implements the CONSUMER side: an attended "supervisor" session that sits
beside a worker session and drives it. `SPECIFICATION/spec.md` §"Supervised
runtimes" ("A tracked session MAY have an attended SUPERVISOR session beside
it") defines it, and it has these identities today:

- the `-supervisor` session-name suffix, RESERVED and refused for workers;
- its own state file at `<repo>/tmp/overseer/<topic>-supervisor/.overseer-state`;
- its own handoff entries on the SHARED plan epic, attributed
  `<slug>-supervisor` (the orchestrator's `append_supervisor_handoff`);
- restart-interlock precondition 5, the resume-artifact certification that
  reads `plan/<topic>/supervisor-handoff.md` or `plan/<topic>/epic.md`;
- the supervision-offer surface and the `.no-supervisor` marker;
- the Lane D pair-stall detector;
- the shared role charter `.ai/supervisor-protocol.md`, copied into FIVE fleet
  repos, and the Codex driver's Stop hook that gates "supervisor completion".

`AGENTS.md` in this repo already says the daemon's "supervisor pair-member
protocol" is NOT the retired supervise-plan seat. That is exactly the residue
this plan removes. The maintainer's framing — "we MAY also remove foreman in
the future, but for now just supervisor" — reads the same way: foreman is also
a seat retired at the skill level whose residue still ships.

**Assumption recorded.** This plan proceeds on that reading. If the maintainer
meant something narrower, the scope event MUST NOT be recorded until the
reading is corrected; nothing below is admitted as an implementation child yet.

Finding 3 — three HOMONYMS that must NOT be touched
---------------------------------------------------

Every fleet grep for "supervisor" is dominated by three unrelated senses. The
acceptance criterion for "all references removed" has to exclude them by name,
or a future session will try to delete the daemon.

1. **The daemon's own loop.** `overseer/supervisor.py` and the ~55
   `overseer/_supervisor_*.py` collaborators ARE overseerd ("the supervisor
   loop IS the daemon", `AGENTS.md`). Only the pair-member subset of those
   modules goes; the cut is by CONSUMER, not by name prefix, exactly as the
   foreman cut was (`tests/test_foreman_seat_removed.py`).
2. **The ROP "outermost supervisor" boundary.** `check-supervisor-discipline`
   (`livespec-dev-tooling/livespec_dev_tooling/checks/supervisor_discipline.py`),
   `supervisor_entry_files` in `pyproject.toml`, and every `errors.py` that
   says "propagate to the outermost supervisor" (livespec, livespec-runtime,
   livespec-orchestrator-git-jsonl, the vendored copies). That is the
   railway-oriented entry-point concept. Untouched.
3. **Infrastructure supervisors.** `livespec-dev-tooling/ci-runner/gate-runner/
   gate-runner-supervisor.*` (a systemd unit), the k3s/kueue manifests, uvicorn's
   `supervisors`, the console CLI's "supervisor process shape" comment, and
   homelab's operational runbooks. Untouched.

Finding 4 — inventory of the role, by repository
------------------------------------------------

### livespec-overseer (owner of the contract)

SPECIFICATION — spec-change tier, routes through `propose-change`, never
dispatchable:

- `spec.md` §"Track discovery and the mapping store" (pair member shares the
  epic; attribution separates the layers), §"Session-name derivation" (the
  reserved `-supervisor` suffix and the refusal rule), §"Supervised runtimes"
  (the attended SUPERVISOR session paragraphs), §"Non-interference with tracked
  work" (the supervisor-topic read exception).
- `contracts.md`: the "(per entity)" row of the state-file table; restart
  interlock precondition 5; the fresh-session prompt's "supervisor's own"
  clause; the attention-membership "pair member disappeared mid-round" entry.
- `constraints.md` — the supervisor-topic read exception to "never reads the
  plan tree".
- `scenarios.md` §"A collision-derived worker name ending in supervisor is
  refused", plus any pair-member scenario found on enumeration.

Code — dispatch-safe once the spec removal is ratified:

- `_registry_track_variants.SupervisorSeat` and its row parse/store paths
  (`_registry_track_row_parse`, `_registry_store_rows`, `_registry_core`,
  `registry.py`).
- `_supervisor_pair.py`, `_supervisor_pair_stall.py` (Lane D),
  `_supervisor_offer.py` (supervision offer, `.no-supervisor`,
  `supervisor-missing` arm), `_supervisor_prompts_supervisor.py`,
  `_supervisor_restart_binder.py` with `supervisor_epic_path` /
  `supervisor_handoff_path` in `_supervisor_prompts`,
  `_supervisor_supervisor_state.py`, `_signals_topics.supervisor_entity_topic`
  and `topic_reserved_for_supervisor`, `homelab_charter_scan.py` (the scheduled
  scan of homelab's supervisor charters).
- The `-supervisor` branches inside shared modules: `_supervisor_tick`,
  `_supervisor_wrapup_select`, `_supervisor_nudge`, `_supervisor_assignment`,
  `_supervisor_restart`, `_supervisor_idle*`, `_supervisor_archive_gc`,
  `_supervisor_start_cli` / `_supervisor_cli_start` reservedness.
- The `.claude-plugin/overseer/` carrier mirror, kept in lockstep by
  `tests/test_plugin_carrier_lockstep.py`.

Tests: `tests/test_lane_c_supervisor_entity*.py`, `tests/test_lane_d_pair_stall.py`,
`tests/test_supervisor_binder_identity.py`, `tests/test_supervisor_restart_archived.py`,
`tests/test_supervisor_restart_migrated_epic.py`, `tests/test_supervisor_pair_registration.py`,
`tests/test_homelab_charter_scan.py`, `tests/prompts/test_charters_carry_no_known_defects.py`,
`tests/test_charter_correction_counts_are_current.py`, the
`tests/prompts/fixtures/supervisor-session-*.jsonl` fixtures,
`tests/test_mapping_store_track_variants.py`, and the integration tests that
build a `SupervisorSeat`. Enumerate from the tree at implementation time; this
list is a starting point, not the set.

Docs: `.ai/supervisor-protocol.md` (1,077 lines), `AGENTS.md` (the `.ai/`
bullet and the "supervisor pair-member protocol" sentence in the seat
paragraph), `overseer/AGENTS.md`, `overseer/marker-protocol.md` ("supervisor
seats"), `.claude-plugin/prose/overseer.md` ("the `-supervisor` seat is the
reserved suffix that remains"), and `tests/heading-coverage.json` if a heading
moves.

Runtime residue, untracked: `tmp/supervisor/` and `tmp/overseer/*-supervisor/`
are gitignored scratch. No repository change; operator cleanup at most.

Open ledger items that name the role and need disposition inside this plan:
`overseer-cv06` (`_supervisor_cli_start` reservedness), `overseer-tdfe.4`
(picker provenance for a seat), `overseer-yqza` (the `tmp/supervisor` rule).

### livespec-orchestrator-beads-fabro

- SPEC (spec-change tier in THAT repo): `SPECIFICATION/contracts.md`
  §"Ledger-held handoff persistence", the paragraph "A plan's SUPERVISOR role …"
  reserving the `<slug>-supervisor` author literal and its discriminator, and
  the "Typed `next_action`" sentence naming `append_supervisor_handoff`.
  `scenarios.md` mentions `supervisor-handoff.md` only as a forbidden live file.
- Code: `commands/plan.py::append_supervisor_handoff` and its tests;
  `prose/plan.md`'s package-command bullet and the sentence "A supervisor
  session driving this operation MUST use this call".
- Docs: `.ai/supervisor-protocol.md` (381 lines); `AGENTS.md` line ~1261.

### livespec (core)

- `.ai/supervisor-protocol.md` (413 lines) — orphaned: no referrer outside
  `plan/archive/`.
- `AGENTS.md` ~L377 (the `tmp/overseer/<topic>/` runtime subtree and
  `.supervisor-state`); `templates/orchestrator-plugin/.ai/agent-disciplines.md`
  ~L24 (the same sentence, templated into consumers).
- `SPECIFICATION/spec.md` ~L393 names `supervisor-handoff.md` as a FORBIDDEN
  live file and a preserved historical artifact. That is a prohibition, not the
  role; leave it unless ratification of the overseer removal makes the wording
  wrong.
- `.ai/verifying-against-the-right-source.md` narrates past supervisor errors.
  It is a record of what happened; keep it.

### livespec-dev-tooling

- `.ai/supervisor-protocol.md` (1,037 lines); `.ai/livespec-operation-gotchas.md`
  ~L81–86 cites "correction C6" inside it.
- `livespec_dev_tooling/charters/charters.py` — `CHARTER_GLOBS` is exactly
  `.ai/supervisor-protocol.md` and `plan/**/supervisor-handoff.md`; the charter
  detector library exists to lint supervisor charters and is consumed by this
  repo's `homelab_charter_scan`. Decide: retire the library, or leave it as a
  generic detector with the globs removed.
- `docs/foreign-code-catch-position.md` and `docs/shipped-message-doc-citations.md`
  mention it in passing; check each hit against the homonym list.

### livespec-console-beads-fabro

- `.ai/supervisor-protocol.md` (411 lines); `justfile` ~L418 lists that path in a
  check target.

### livespec-driver-codex

- `livespec/hooks/supervisor_completion_gate.py`, `livespec/hooks/_supervisor_producers.py`,
  the Stop-hook entry in `livespec/hooks/hooks.json`, the tests
  (`tests/hooks/test_supervisor_completion_gate.py` and the footgun-guard tests
  that reference it), `AGENTS.md` ~L195. Check that repo's `SPECIFICATION/` for a
  contract clause before filing; if one exists the hook removal is spec-change
  tier there too.
- `livespec-driver-claude` and `livespec-driver-pi` carry no supervisor hook;
  their only hits are the ROP homonym.

### homelab

A CONSUMER repo. Its `plan/**/supervisor-handoff.md` files are historical plan
records and stay; its `tmp/*-supervisor/` directories are runtime scratch. The
only fleet-side coupling is this repo's `homelab_charter_scan.py`, which goes
with the role.

Finding 5 — tier and ordering
-----------------------------

Both the overseer and orchestrator halves are MIXED tier and MUST be split at
filing: a `SPECIFICATION/` child (propose-change, human-ratified) and a
repository child (dispatch-safe, filed after the spec child ratifies). The
precedent is the seat retirement itself: v047 ratified first, then the code
removals shipped as breaking releases 3.0.0, 4.0.0 and 5.0.0.

Proposed order, each a separate child, one PR per repo minimum, `hp` routing:

1. Overseer spec: propose-change removing the pair-member paragraphs, the
   reserved suffix, interlock precondition 5, the plan-tree read exception and
   the pair scenarios; revise to v052.
2. Overseer code, tests, docs, carrier mirror; breaking release. Includes
   deleting `.ai/supervisor-protocol.md` and re-tensing `AGENTS.md`.
3. Orchestrator spec: drop the `<slug>-supervisor` reservation and the
   `append_supervisor_handoff` mention; then the package, prose and docs.
4. Driver-codex Stop hook and tests.
5. `.ai/supervisor-protocol.md` in livespec, livespec-dev-tooling and
   livespec-console-beads-fabro, with their referrers (`livespec-operation-gotchas.md`,
   the console `justfile` entry, the charter globs).
6. Fleet-wide verification: a grep for `supervisor` across every fleet repo
   whose remaining hits are ALL in the homonym list or under
   `plan/archive/` / `SPECIFICATION/history/`. That list is the acceptance
   criterion, written into the child, not left to the implementer.

Explicit non-goals
------------------

- Foreman residue (`_foreman_vendor_path`, `foreman_gather_sources`,
  `caam_foreman_override`) — untouched, per the directive.
- The three shipped skills — untouched.
- `plan/archive/**` and `SPECIFICATION/history/**` anywhere in the fleet —
  never edited; history is the record.
- The three homonyms in Finding 3.

Open question for the maintainer
--------------------------------

Confirm the reading in Finding 2 — that "the supervisor skill" means the
supervisor pair-member role and its fleet protocol — before the scope event is
recorded. The recommended answer is yes; nothing else in the tree answers to
the name.
