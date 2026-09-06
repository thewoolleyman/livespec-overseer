---
topic: retire-foreman-grooming-and-supervisor-seats
author: claude-fable-5-1 (retire-overseer plan session)
created_at: 2026-09-06T10:00:33Z
spec_commitments:
  impl_followups:
    - id_hint: remove-foreman-seat-code
      description: |
        Already filed as overseer-5ugiuj.1 (blocked on this revision): delete the foreman skill, prose, entry points and the 73 foreman-exclusive modules; keep _foreman_vendor_path, foreman_gather_sources and caam_foreman_override; surgically drop the foreman half of ten daemon modules; delete the foreman tests whose heading-coverage entries this revision removes.
    - id_hint: remove-grooming-seat-code
      description: |
        Already filed as overseer-5ugiuj.2 (blocked on this revision): delete the grooming skill, prose, grooming_conformance* modules and _supervisor_grooming.
    - id_hint: remove-supervise-plan-skill-code
      description: |
        Already filed as overseer-5ugiuj.3 (blocked on this revision): delete the supervise-plan skill, prose, and only the binder/handoff/Driver-gate code the skill alone consumed; the daemon's supervisor pair-member support stays as bucket-1 residue.
    - id_hint: trim-manifests-to-overseer-and-caam
      description: |
        Already filed as overseer-5ugiuj.4: plugin.json, .codex-plugin, .pi-plugin, marketplace.json, AGENTS.md and docs describe exactly overseer + caam-anthropic-loop; breaking version bump.
---

## Proposal: Remove the foreman charter and the foreman-only clauses from spec.md

### Target specification files

- SPECIFICATION/spec.md

### Summary

Delete the foreman charter that occupies the body under the document's top heading (the paragraph beginning 'The FOREMAN — the per-repository autonomous operator surface' through the detection-staleness routing paragraph immediately before '## The cardinal rule', including the sub-sections 'Full autonomy and the decision rule', 'The convene obligation' and 'Relay and escalation discipline'), and drop the foreman mentions that daemon sections carry only because the foreman existed. The account-rotation section (bucket 1, caam) is deliberately left verbatim.

### Motivation

Maintainer ruling 2026-09-06 (recorded as a scope event on the console plan epic livespec-console-beads-fabro-pzbdbo, decision D5 refined into two buckets): overseerd and the caam-anthropic-loop are production and stay, maintainer-owned; the foreman, grooming and supervise-plan seats are unused and are deprecated and removed now, reducing livespec-overseer to overseer + caam loop. The removal is spec-first by necessity, not preference: factory run 01M1V1E2YSXWKCPYMR95G21Y6B for overseer-5ugiuj.1 measured the cut and refused, because scripts/check-no-factory-spec-edits.sh forbids sandbox edits under SPECIFICATION/ and check-heading-coverage binds heading-coverage entries to the foreman tests, so no code-only deletion can land green. Once this revision is on master, overseer-5ugiuj.1/.2/.3 are pure code cuts (research: plan/deprecate-unused-seats-simplify-to-overseerd-and-caam/research/001-bucket-inventory.md and 002-measured-cut.md). BOUNDARY, applied throughout: clauses go when their ONLY subject is a seat; a daemon clause that merely mentions a seat is reworded to drop the mention; bucket-1 clauses (overseerd's own protocol, the caam account-rotation section) are not edited even where they still name a seat, and each such residue is listed explicitly so the maintainer can retire it when bucket 1 is stable.

### Proposed Changes

1. DELETE the whole foreman charter: from the paragraph beginning `The FOREMAN — the per-repository autonomous operator surface — is governed by this specification in its CONTRACT surface` (spec.md ~L22) through the paragraph ending `an unattended surface can neither give that consent nor hold that dialogue.` (~L521), which is everything between the pane-cockpit paragraph of the introduction and `## The cardinal rule`. This removes the sub-sections `### Full autonomy and the decision rule`, `### The convene obligation` and `### Relay and escalation discipline`, the valve-disposition and consensus-panel policy, the delegation floor, the wait-premise obligations, the unrouted-plan condition, the capacity-statement rule, the ledger-published wait states and the detection-staleness routing rule. The consensus-panel capability and the starvation (unrouted-plan / ready-aging) rule are transferred BY NAME to the orchestrator: panel → workflow variant under bd-ib-yqpdrt (b4) with the valve-policy enum on attention items; starvation → dispatcher loop cadence (b5-NOW). Neither is re-specified here.

2. `## Out-of-band state declaration`: delete the sentence `The foreman MUST NOT write any value into any track's state file.`

3. `## The stalled-picker charter reminder`: in the first predicate bullet replace `BOTH the `-supervisor` and the `-foreman` suffix` with `the `-supervisor` suffix`; in the derived-status bullet delete `or a foreman pane claim`; delete the two sentences `It does not separate it from the foreman's own valve acts, which do submit and which are governed by the foreman sections and the v020 delivery-routing floor rather than by this enumeration.` The act itself stays, because the daemon's supervisor pair member (bucket-1 residue, see below) remains a reserved entity.

4. `## Track discovery and the mapping store`: delete the sentence `Where that surface is the authorized unattended foreman, §"Non-interference with tracked work" grants it this purpose expressly, alongside its own decision-routing.`

5. `## Session-name derivation`: in the reserved-suffix paragraph delete `and the `-foreman` suffix is RESERVED for the per-repository foreman surface`, change `Both are compared case-insensitively` to `It is compared case-insensitively`, and change `so a foreman or supervisor session can never be captured` to `so a supervisor session can never be captured`.

6. `## Non-interference with tracked work`: delete the paragraph beginning `An authorized UNATTENDED operator surface — the foreman — MAY READ files under a watched repository's plan tree` through `The DAEMON's own posture is unchanged by this carve-out.`; in the following paragraph change `When such a surface STARTS a tracked session` to `When any operator surface STARTS a tracked session` (the start-intent obligation is kept: it is consumed by the maintainer's live plan session-start-and-registry-integrity, overseer-zidpiu); in the last paragraph delete the sentence `An authorized operator surface's runtime state MUST live under that same per-repository gitignored scratch area, in its own `tmp/overseer/foreman/` subdirectory; it MUST NOT create any new scratch root.`

7. NOT CHANGED (bucket 1, caam, maintainer-owned — listed so the residue is explicit): `## Account rotation and quota supervision` keeps `Sessions whose name carries the foreman suffix MUST be pointed at the scoped model`, `the global foreman pin`, and `overrides the foreman precedence rules`. With no foreman sessions the exact-suffix match simply matches nothing and the operator pin keeps working; retiring that wording is the maintainer's call when caam is stable.

8. NOT CHANGED (bucket-1 residue, daemon): the supervisor PAIR MEMBER protocol in `## Supervised runtimes` (all but its last paragraph, see the contracts finding), the `-supervisor` suffix reservation, and the restart interlock's resume-artifact certification for a SUPERVISOR topic. They are overseerd behaviour and are left for the maintainer; once the supervise-plan skill is gone nothing creates a pair member, so this residue is dead code to retire with bucket 1.

## Proposal: Remove the supervise-plan skill's Driver gate and the foreman-only contracts from contracts.md

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Delete `## Supervisor completion gate`, `## The wait-premise record` and `## The foreman valve disposition` whole, and strip the foreman heartbeat and foreman-escalation members from `## Attention surface`. The account-rotation operation's contract (bucket 1) is left verbatim.

### Motivation

Maintainer ruling 2026-09-06 (recorded as a scope event on the console plan epic livespec-console-beads-fabro-pzbdbo, decision D5 refined into two buckets): overseerd and the caam-anthropic-loop are production and stay, maintainer-owned; the foreman, grooming and supervise-plan seats are unused and are deprecated and removed now, reducing livespec-overseer to overseer + caam loop. The removal is spec-first by necessity, not preference: factory run 01M1V1E2YSXWKCPYMR95G21Y6B for overseer-5ugiuj.1 measured the cut and refused, because scripts/check-no-factory-spec-edits.sh forbids sandbox edits under SPECIFICATION/ and check-heading-coverage binds heading-coverage entries to the foreman tests, so no code-only deletion can land green. Once this revision is on master, overseer-5ugiuj.1/.2/.3 are pure code cuts (research: plan/deprecate-unused-seats-simplify-to-overseerd-and-caam/research/001-bucket-inventory.md and 002-measured-cut.md). BOUNDARY, applied throughout: clauses go when their ONLY subject is a seat; a daemon clause that merely mentions a seat is reworded to drop the mention; bucket-1 clauses (overseerd's own protocol, the caam account-rotation section) are not edited even where they still name a seat, and each such residue is listed explicitly so the maintainer can retire it when bucket 1 is stable.

### Proposed Changes

1. DELETE `## Supervisor completion gate` whole (the attended supervisor's `.supervisor-state` marker and the Driver-owned Stop/completion gate exist only for the supervise-plan skill). Correspondingly, in spec.md `## Supervised runtimes` delete the LAST paragraph, beginning `The attended supervisor's completion control is a separate structured marker` and ending `owns cold re-entry with fresh ledger/forge evidence.`, and in `## Non-interference with tracked work` delete the sentences from `An ATTENDED Control-Plane operator skill (supervise-plan) authors the same two layers it always has, on two different media.` through `continue to bind the daemon's runtime state verbatim.` (the `.ai/supervisor-protocol.md` shared layer and the binder are the skill's artifacts).

2. DELETE `## The wait-premise record` whole (its only writers are the foreman and a foreman-directed session; the kind vocabulary and the `wait-premises/` directories go with it).

3. DELETE `## The foreman valve disposition` whole (report-only / consensus / full_autonomy resolution; the capability transfers by name to the orchestrator's valve-policy enum on attention items, b5-NOW, and the panel workflow variant, b4).

4. `## Attention surface`: delete the paragraph `A foreman MUST write a heartbeat file at `<repo>/tmp/overseer/foreman/heartbeat.json` ... subject to a floor of thirty minutes.`; delete the sentences `A PRESENT-but-STALE foreman heartbeat MUST be surfaced with coordinates, edge-triggered like every other member. An ABSENT heartbeat MUST NOT be attention — no foreman adopted means nothing is wrong, mirroring the unassigned-is-not-attention rule. This member is report-only and MUST NOT authorize any act.`; delete the paragraph `Membership also includes a track the foreman has escalated because the foreman itself needs a human decision it cannot make ... never a substitute for or a relaxation of any other membership condition in this section.` Every other member, including `a supervisor pair member that disappeared while its round was open`, is daemon behaviour and stays.

5. NOT CHANGED (bucket 1): `## The account-rotation operation` keeps `peer to the foreman and grooming operations` in its Surfaces clause; the maintainer may drop the phrase when caam is next revised. `## The restart interlock` and `## The state file` keep their supervisor pair-member clauses (daemon residue, see the spec.md finding).

## Proposal: Remove the seat scenarios from scenarios.md and their heading-coverage entries

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Delete every scenario whose only actor is the foreman, the supervise-plan supervisor's Driver gate, or a foreman wait-premise; reword the two reserved-suffix scenarios to the surviving `-supervisor` suffix; delete the 62 tests/heading-coverage.json entries keyed on the deleted headings in the same revision PR.

### Motivation

Maintainer ruling 2026-09-06 (recorded as a scope event on the console plan epic livespec-console-beads-fabro-pzbdbo, decision D5 refined into two buckets): overseerd and the caam-anthropic-loop are production and stay, maintainer-owned; the foreman, grooming and supervise-plan seats are unused and are deprecated and removed now, reducing livespec-overseer to overseer + caam loop. The removal is spec-first by necessity, not preference: factory run 01M1V1E2YSXWKCPYMR95G21Y6B for overseer-5ugiuj.1 measured the cut and refused, because scripts/check-no-factory-spec-edits.sh forbids sandbox edits under SPECIFICATION/ and check-heading-coverage binds heading-coverage entries to the foreman tests, so no code-only deletion can land green. Once this revision is on master, overseer-5ugiuj.1/.2/.3 are pure code cuts (research: plan/deprecate-unused-seats-simplify-to-overseerd-and-caam/research/001-bucket-inventory.md and 002-measured-cut.md). BOUNDARY, applied throughout: clauses go when their ONLY subject is a seat; a daemon clause that merely mentions a seat is reworded to drop the mention; bucket-1 clauses (overseerd's own protocol, the caam account-rotation section) are not edited even where they still name a seat, and each such residue is listed explicitly so the maintainer can retire it when bucket 1 is stable.

### Proposed Changes

1. DELETE these scenarios whole (headings verbatim):
   - supervise-plan Driver gate: `A missing supervisor role layer halts the binder with a remedy`, `An open supervisor obligation or malformed marker refuses completion`, `A stale producer or prose-only wake claim refuses completion`, `An explicit plan-complete disposition may end an active supervisor turn`, `Exactly one genuine maintainer block may end an active supervisor turn`, `A verified wake producer cold-opens from fresh state`, `User messages are additive during active supervision`.
   - foreman: every scenario from `A foreman reads evidence without becoming a state-file or blocked-pane writer` through `A foreman tick that ends with its own blocking prompt outstanding is a reportable violation` (heartbeat, canonical name, relay, escalation quoting, corroboration, STILL alerts, bounce-invalidated watch, own unresolved decision); every scenario from `A unanimous panel verdict under the consensus disposition acts and is journaled first` through `A floor category owned by another contract stays escalated under full autonomy`; every scenario from `A tree declaring no valve disposition acts on nothing` through `The effective valve disposition is readable without invoking the foreman`; `An unreadable snapshot holds decision-relevant context rather than delivering it`, `A long-lived question states where late-arriving context is routed`, `Decision-relevant context is not delivered to a picker-parked session`; every scenario from `The foreman seeks a panel verdict for a decision the convene obligation applies to` through `A floor-barred human valve does not trigger the convene obligation`; the three wait-premise record scenarios (`A malformed wait-premise record is skipped rather than failing its siblings`, `An expired wait premise is not presented as current evidence`, `Two distinct targets do not collide onto one wait-premise file`); every scenario from `The foreman identifies a recorded premise in a wait option` through `The delegation floor holds against a unanimous panel`; every scenario from `An unrouted plan yields the enumerated remedy as the foreman's own action` through `A detection-staleness item is routed to an attended surface, never run`.

2. REWORD, keeping the daemon rule: `A collision-derived worker name ending in foreman is refused` → `A collision-derived worker name ending in supervisor is refused`, with `the topic foreman` → `the topic supervisor`; `A reserved-name live session is not adopted as a worker` keeps its heading and its Given becomes `a live session registry-named repo-slug-supervisor`. The reserved-suffix rule survives for the `-supervisor` suffix (daemon residue).

3. KEEP untouched (daemon): `A status snapshot writer failure does not stop supervision`, `A consumer fails closed on an unknown status snapshot schema`, `A dead track with conflicting runtime evidence is not launched`, `A structurally impossible act is never rendered as in progress`, and every scenario about the supervisor PAIR MEMBER (state file, rounds, restart).

4. In the SAME revision pull request delete these 62 `tests/heading-coverage.json` entries (spec file | heading | test); the integration tests they name stay in the tree until overseer-5ugiuj.1/.2/.3 delete them, which check-heading-coverage permits (a test without an entry is not a finding; an entry without a heading is):
- `scenarios.md` | `## Scenario: A missing supervisor role layer halts the binder with a remedy` | `tests.integration.test_dhkjxf_registry_snapshot_and_binder.test_scenario_missing_supervisor_role_layer_halts_binder_with_remedy`
- `contracts.md` | `## Supervisor completion gate` | `tests.integration.test_supervisor_completion_contract.test_supervisor_completion_gate_contract_is_realized_in_generated_output`
- `scenarios.md` | `## Scenario: An open supervisor obligation or malformed marker refuses completion` | `tests.integration.test_supervisor_completion_contract.test_completion_gate_contract_rejects_fail_closed_inputs`
- `scenarios.md` | `## Scenario: A stale producer or prose-only wake claim refuses completion` | `tests.integration.test_supervisor_completion_contract.test_completion_gate_contract_rejects_unverifiable_wake_producers`
- `scenarios.md` | `## Scenario: An explicit plan-complete disposition may end an active supervisor turn` | `tests.integration.test_supervisor_completion_contract.test_completion_gate_contract_accepts_only_terminal_dispositions`
- `scenarios.md` | `## Scenario: Exactly one genuine maintainer block may end an active supervisor turn` | `tests.integration.test_supervisor_completion_contract.test_completion_gate_contract_accepts_only_terminal_dispositions`
- `scenarios.md` | `## Scenario: A verified wake producer cold-opens from fresh state` | `tests.integration.test_supervisor_completion_contract.test_completion_gate_contract_requires_external_cold_reentry`
- `scenarios.md` | `## Scenario: User messages are additive during active supervision` | `tests.integration.test_supervisor_completion_contract.test_completion_gate_contract_keeps_user_messages_additive`
- `scenarios.md` | `## Scenario: A foreman reads evidence without becoming a state-file or blocked-pane writer` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_foreman_reads_evidence_without_writing_session_state`
- `scenarios.md` | `## Scenario: A stale foreman heartbeat is surfaced as attention` | `tests.integration.test_dhkjxf_discovery_attention_and_gates.test_scenario_stale_foreman_heartbeat_is_surfaced_as_attention`
- `scenarios.md` | `## Scenario: An absent foreman heartbeat is silent` | `tests.integration.test_dhkjxf_discovery_attention_and_gates.test_scenario_absent_foreman_heartbeat_is_silent`
- `scenarios.md` | `## Scenario: A foreman uses the canonical name on both identity surfaces` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_foreman_uses_canonical_name_on_both_identity_surfaces`
- `contracts.md` | `## The foreman valve disposition` | `tests.integration.test_foreman_valve_disposition.test_effective_valve_disposition_is_readable_and_fails_closed`
- `scenarios.md` | `## Scenario: A unanimous panel verdict under the consensus disposition acts and is journaled first` | `tests.integration.test_foreman_valve_disposition.test_consensus_disposition_journals_before_acting`
- `scenarios.md` | `## Scenario: A decision human-gated by design stays escalated even under a unanimous panel` | `tests.integration.test_foreman_valve_disposition.test_consensus_floors_and_missing_evidence_escalate_without_mutation`
- `scenarios.md` | `## Scenario: Unavailable or disagreeing consensus evidence escalates and mutates nothing` | `tests.integration.test_foreman_valve_disposition.test_consensus_floors_and_missing_evidence_escalate_without_mutation`
- `scenarios.md` | `## Scenario: A tree declaring no valve disposition acts on nothing` | `tests.integration.test_foreman_valve_disposition.test_absent_config_keeps_human_valves_report_only_byte_identical`
- `scenarios.md` | `## Scenario: An absent valve-disposition key resolves to the safe default` | `tests.integration.test_foreman_valve_disposition.test_effective_valve_disposition_is_readable_and_fails_closed`
- `scenarios.md` | `## Scenario: An unrecognized valve-disposition value fails closed and is surfaced` | `tests.integration.test_foreman_valve_disposition.test_effective_valve_disposition_is_readable_and_fails_closed`
- `scenarios.md` | `## Scenario: The effective valve disposition is readable without invoking the foreman` | `tests.integration.test_foreman_valve_disposition.test_effective_valve_disposition_is_readable_and_fails_closed`
- `scenarios.md` | `## Scenario: A foreman relay embeds the full panel record on first delivery` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_foreman_relay_embeds_full_panel_record_on_first_delivery`
- `scenarios.md` | `## Scenario: An escalation quotes the session's exact words rather than paraphrasing them` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_escalation_quotes_session_exact_words`
- `scenarios.md` | `## Scenario: A worker's corroboration request is not escalated as an authority challenge` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_corroboration_request_is_not_escalated_as_authority_challenge`
- `scenarios.md` | `## Scenario: Two consecutive STILL alerts force a fresh pane re-read` | `tests.integration.test_dhkjxf_restart_liveness_and_recovery.test_scenario_two_consecutive_still_alerts_force_fresh_pane_reread`
- `scenarios.md` | `## Scenario: A daemon-bounce-invalidated watch is not treated as armed` | `tests.integration.test_dhkjxf_restart_liveness_and_recovery.test_scenario_daemon_bounce_invalidated_watch_is_not_armed`
- `scenarios.md` | `## Scenario: A foreman's own unresolved decision escalates without blocking` | `tests.integration.test_foreman_escalation_attention.test_scenario_foreman_escalation_is_report_only_attention`
- `scenarios.md` | `## Scenario: A foreman tick that ends with its own blocking prompt outstanding is a reportable violation` | `tests.integration.test_foreman_escalation_attention.test_scenario_foreman_blocking_prompt_tick_is_reportable_violation`
- `scenarios.md` | `## Scenario: An unreadable snapshot holds decision-relevant context rather than delivering it` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_unreadable_snapshot_holds_decision_context`
- `scenarios.md` | `## Scenario: A long-lived question states where late-arriving context is routed` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_long_lived_question_states_late_context_routing`
- `scenarios.md` | `## Scenario: Decision-relevant context is not delivered to a picker-parked session` | `tests.integration.test_dhkjxf_foreman_evidence_routing.test_scenario_decision_context_is_not_delivered_to_picker_parked_session`
- `contracts.md` | `## The wait-premise record` | `tests.test_wait_premises.test_wait_premise_helper_writes_typed_record_atomically`
- `scenarios.md` | `## Scenario: A failed premise is surfaced rather than the option being altered` | `tests.test_wait_premise_question_lint.test_due_premise_is_reverified_against_its_recorded_source`
- `scenarios.md` | `## Scenario: A floor-barred human valve does not trigger the convene obligation` | `tests.test_supervisor_consensus_overdue.test_consensus_overdue_suppresses_for_non_panel_or_floor_barred_decisions`
- `scenarios.md` | `## Scenario: A foreman that declines to convene records the escalation condition, however long it has applied` | `tests.test_foreman_convene_obligations.test_convene_obligation_writer_supports_discharge_and_escalation_roots`
- `scenarios.md` | `## Scenario: A malformed wait-premise record is skipped rather than failing its siblings` | `tests.test_wait_premises_edges.test_reader_skips_malformed_record_without_dropping_valid_sibling`
- `scenarios.md` | `## Scenario: A panel that cannot be constituted discharges the obligation and escalates` | `tests.test_supervisor_consensus_overdue.test_consensus_overdue_suppresses_for_escalation_or_discharge_artifact`
- `scenarios.md` | `## Scenario: A recorded premise is re-verified by its recheck instant` | `tests.test_wait_premise_question_lint.test_due_premise_is_reverified_against_its_recorded_source`
- `scenarios.md` | `## Scenario: An expired wait premise is not presented as current evidence` | `tests.test_wait_premise_question_lint.test_due_premise_without_checker_is_surfaced_as_untestable`
- `scenarios.md` | `## Scenario: An inexpressible wait kind does not suppress the question` | `tests.test_wait_premise_question_lint.test_inexpressible_wait_kind_is_surfaced_but_not_refused`
- `scenarios.md` | `## Scenario: An unmet convene obligation is surfaced rather than passing silently` | `tests.test_supervisor_consensus_overdue.test_consensus_overdue_raises_after_convene_bound_without_satisfying_artifact`
- `scenarios.md` | `## Scenario: The foreman identifies a recorded premise in a wait option` | `tests.test_wait_premises.test_foreman_gather_surfaces_recorded_wait_premises_per_row`
- `scenarios.md` | `## Scenario: The foreman seeks a panel verdict for a decision the convene obligation applies to` | `tests.test_supervisor_consensus_overdue.test_consensus_overdue_suppresses_when_matching_panel_record_exists`
- `scenarios.md` | `## Scenario: Two distinct targets do not collide onto one wait-premise file` | `tests.test_wait_premises.test_wait_premise_paths_disambiguate_colliding_target_stems`
- `scenarios.md` | `## Scenario: A strict majority authorizes an action under full autonomy` | `tests.integration.test_foreman_consensus_majority_rule.test_scenario_strict_majority_authorizes_action_under_full_autonomy`
- `scenarios.md` | `## Scenario: The same split escalates under the unanimous decision rule` | `tests.integration.test_foreman_consensus_majority_rule.test_scenario_same_split_escalates_under_unanimous_decision_rule`
- `scenarios.md` | `## Scenario: An insufficient-information verdict abstains rather than vetoes under the majority rule` | `tests.integration.test_foreman_consensus_majority_rule.test_scenario_insufficient_information_abstains_under_majority_rule`
- `scenarios.md` | `## Scenario: A needs-human dissent without a security risk kind is outvoted under the majority rule` | `tests.integration.test_foreman_consensus_majority_rule.test_scenario_other_hard_risk_dissent_is_outvoted_under_majority_rule`
- `scenarios.md` | `## Scenario: A security dissent escalates under the majority rule and no majority overrides it` | `tests.integration.test_foreman_consensus_majority_rule.test_scenario_security_dissent_escalates_under_majority_rule`
- `scenarios.md` | `## Scenario: A floor category owned by another contract stays escalated under full autonomy` | `TODO`
- `scenarios.md` | `## Scenario: A panel-authorized change is relayed to the worker rather than implemented by the foreman` | `tests.integration.test_foreman_valve_disposition.test_panel_authorized_change_is_relayed_to_worker_not_implemented_by_foreman`
- `scenarios.md` | `## Scenario: A track with no assigned worker resolves to an assignment rather than to foreman-authored work` | `tests.integration.test_foreman_valve_disposition.test_unassigned_track_gets_worker_assignment_instead_of_foreman_work`
- `scenarios.md` | `## Scenario: The delegation floor holds against a unanimous panel` | `tests.integration.test_foreman_valve_disposition.test_delegation_floor_refuses_unanimous_foreman_authored_deliverable`
- `scenarios.md` | `## Scenario: An unrouted plan yields the enumerated remedy as the foreman's own action` | `tests.integration.test_unrouted_plan_condition.test_an_unrouted_plan_yields_the_enumerated_remedy_as_the_foremans_own_action`
- `scenarios.md` | `## Scenario: A tick that actions a plan resets that plan's consecutive-unactioned count` | `tests.integration.test_unrouted_plan_bound.test_an_actioning_tick_resets_the_count_and_a_later_tick_is_not_past_bound`
- `scenarios.md` | `## Scenario: A missing required input yields undetermined, never absent-condition` | `tests.integration.test_unrouted_plan_bound.test_an_unconfigured_bound_resolves_undetermined_never_absent_condition`
- `scenarios.md` | `## Scenario: A missing required input yields undetermined, never absent-condition` | `tests.integration.test_unrouted_plan_condition.test_a_missing_attention_view_fact_yields_undetermined_never_absent_condition`
- `scenarios.md` | `## Scenario: An escalation proposing repair of an absent component is refused with the available remedy named` | `tests.integration.test_escalation_refusal.test_an_escalation_proposing_repair_of_an_absent_component_is_refused`
- `scenarios.md` | `## Scenario: A genuine report of missing infrastructure is still raised` | `tests.integration.test_escalation_refusal.test_a_genuine_report_of_missing_infrastructure_is_still_raised`
- `scenarios.md` | `## Scenario: Capacity is stated from the composed verdict, not from raw statuses` | `tests.integration.test_capacity_from_verdict.test_capacity_is_stated_from_the_composed_verdict_not_from_raw_statuses`
- `scenarios.md` | `## Scenario: Capacity with no available verdict is stated as unknown, never inferred` | `tests.integration.test_capacity_from_verdict.test_capacity_with_no_available_verdict_is_stated_as_unknown_never_inferred`
- `scenarios.md` | `## Scenario: A foreman wait is readable without opening its pane` | `tests.integration.test_foreman_wait_publication.test_a_foreman_wait_is_readable_without_opening_its_pane`
- `scenarios.md` | `## Scenario: A detection-staleness item is routed to an attended surface, never run` | `tests.integration.test_detection_staleness_routing.test_a_surfaced_detection_staleness_item_is_routed_to_an_attended_surface`

## Proposal: Remove the seat clauses from constraints.md

### Target specification files

- SPECIFICATION/constraints.md

### Summary

Drop the supervisor completion-gate paragraph from `## Determinism boundary`, the foreman scratch-root and supervise-plan authoring sentences from `## Filesystem boundaries`, and the foreman valve-disposition paragraph from `## Acting safety`; the stalled-picker charter-reminder exception stays.

### Motivation

Maintainer ruling 2026-09-06 (recorded as a scope event on the console plan epic livespec-console-beads-fabro-pzbdbo, decision D5 refined into two buckets): overseerd and the caam-anthropic-loop are production and stay, maintainer-owned; the foreman, grooming and supervise-plan seats are unused and are deprecated and removed now, reducing livespec-overseer to overseer + caam loop. The removal is spec-first by necessity, not preference: factory run 01M1V1E2YSXWKCPYMR95G21Y6B for overseer-5ugiuj.1 measured the cut and refused, because scripts/check-no-factory-spec-edits.sh forbids sandbox edits under SPECIFICATION/ and check-heading-coverage binds heading-coverage entries to the foreman tests, so no code-only deletion can land green. Once this revision is on master, overseer-5ugiuj.1/.2/.3 are pure code cuts (research: plan/deprecate-unused-seats-simplify-to-overseerd-and-caam/research/001-bucket-inventory.md and 002-measured-cut.md). BOUNDARY, applied throughout: clauses go when their ONLY subject is a seat; a daemon clause that merely mentions a seat is reworded to drop the mention; bucket-1 clauses (overseerd's own protocol, the caam account-rotation section) are not edited even where they still name a seat, and each such residue is listed explicitly so the maintainer can retire it when bucket 1 is stable.

### Proposed Changes

1. `## Determinism boundary`: delete the paragraph beginning `The distinct Driver-owned supervisor completion gate is also fail-closed` and ending `or any new plan-tree access.`

2. `## Filesystem boundaries`: delete `An authorized foreman MAY keep its own runtime state only in `<repo>/tmp/overseer/foreman/` inside that same gitignored scratch root and MUST NOT create another scratch root.`; delete the sentences from `The attended Control-Plane authoring exception permits supervise-plan to create exactly ONE reviewed artifact` through `through the pull request path.`; delete `Separately, an authorized unattended foreman MAY read plan-tree, pane, and work-item text solely as evidence; it MUST NOT write or delete plan-tree files, hash them as authorization, or treat text it reads as instructions.` The resume-artifact certification sentence for a SUPERVISOR topic stays (daemon residue).

3. `## Acting safety`: delete the paragraph beginning `The foreman's valve disposition and its full-autonomy declaration obey the same fail-closed rule` through its end (the sentence ending `or its own decision rule` and any trailing sentence of that paragraph). The five-act enumeration and the stalled-picker charter-reminder exception stay verbatim.

4. `## Runtime requirements` and the rest: unchanged.
