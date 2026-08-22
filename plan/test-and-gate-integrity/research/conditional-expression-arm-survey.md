# Conditional-expression arms are invisible to the branch-coverage bar — the survey

**Ledger anchor: `overseer-hgq4wi`.** Owning item: **`overseer-hgq4wi.34`** (P1).
Sibling, and **not** a duplicate: **`overseer-awec`** — see *Discriminator* below.

Measured 2026-08-22 against `origin/master` at `71dfa27`.

## The defect, in one line

This repo enforces **100% statement and branch coverage**, and a conditional
expression — a one-line ternary — **contributes no branch to that bar**. Its
untaken arm is not a partial branch, is not listed under `Missing`, and does not
move the percentage. Written as `if`/`else` the same logic *is* caught. The
gate's verdict therefore depends on which of two equivalent spellings the author
chose, and the more compact spelling is the one it cannot see.

## What was already fixed before this survey ran

The item's named live instance — `overseer/caam_profile_state.py:84`,
`return {} if body is None else body` — **already has its success-path test**.
It landed in `762768a`, *"test(caam): cover load_state's success path, which had
no test at all"*, at **2026-08-21T23:13:40Z**.

That is an **update, not a correction**: the item was filed earlier the same day
and was accurate when written. The gap was closed in the hours between. Recorded
in those terms deliberately — a retraction here would put a false admission of
error into the record and undermine a finding that was sound.

**The existing test was verified discriminating** rather than taken on trust,
which is the criterion that matters most on an item about checks that cannot
fail:

| tree | `load_state` tests |
|---|---|
| unmodified | **2 passed** |
| success arm forced to return the empty mapping | **`test_load_state_returns_the_parsed_mapping_for_a_well_formed_object` FAILED** |

The mirror `.claude-plugin/overseer/caam_profile_state.py` was confirmed
byte-identical to the source module at the same commit.

## The instrument

Coverage cannot answer this question, so the arms were measured directly. Each
conditional expression in `overseer/*.py` was rewritten into a probe call that
records which arm ran:

```python
# a if C else b   ->
_ARMPROBE('123', (C), (lambda: (a)), (lambda: (b)))
```

`record` evaluates only the selected thunk, so **laziness is preserved** and
instrumented code evaluates exactly what the original did. Three properties were
deliberate:

- **Surgical splice, not an `ast.unparse` round trip.** Only each `IfExp`'s exact
  source span is replaced; every other byte of every file is preserved. This repo
  has tests that read, checksum and mirror module source, and a reformatting
  rewrite would fail them for reasons having nothing to do with the survey.
- **Byte offsets, not character offsets.** CPython's `col_offset` is a UTF-8
  **byte** offset. Several of these modules carry em dashes in prose strings, and
  treating the column as a character index silently over-runs the node's end and
  swallows the following newline. That is how the instrument first failed, and it
  failed loudly — a `SyntaxError` — which is the good case.
- **A per-module injected import, not a `conftest` builtin.** A builtin reaches
  only the pytest process, and this repo drives real coverage through
  **subprocesses**. Those raised `NameError` on the probe call, which both lost
  their data and manufactured ~1,140 test failures that looked like findings.

### The instrument was controlled before its output was believed

A detector that cannot return a negative is the same defect wearing a new hat, so
the instrument was run **both ways** against the one site whose history is known:

| tests used | `caam_profile_state.py:84` arms | suite |
|---|---|---|
| current (with the success-path test) | `[1, 1]` — both arms | 10 passed |
| the test file as of `762768a~1` | **`[1, 0]` — success arm never taken** | **9 passed, green** |

The second row is the defect itself, reproduced: a green suite at 100% coverage
with one arm of a live conditional never executed. The instrument flags exactly
that and stops flagging it the moment the test exists.

## Population and findings

**Population scanned, stated so the survey is not a bare "zero found":**

| | count |
|---|---|
| `overseer/*.py` files | 293 (223 product, 70 beside-test) |
| conditional expressions in product modules | **320** |
| instrumented | 312 |
| not instrumented (see *Bounds*) | 8, in 3 files |
| **both arms exercised** | **210** |
| **exactly one arm exercised** | **98** |
| neither arm recorded | 4 (**artifact — see *Bounds***) |

**98 single-arm conditional expressions across 53 of 115 files.** Every one is a
path the coverage bar reports as fully covered while one of its two outcomes has
never been executed by the suite.

By file, the heaviest first:

| `foreman_gather_release_lane.py` | 6 |
| `_supervisor_pair_stall.py` | 5 |
| `caam_sessions.py` | 5 |
| `caam_usage.py` | 5 |
| `foreman_blocked_answer.py` | 5 |
| `_registry_stamps.py` | 4 |
| `caam_warm.py` | 3 |
| `foreman_act_consensus.py` | 3 |
| `foreman_work_item_sessions.py` | 3 |
| `grooming_plan_budget.py` | 3 |
| `_registry_discovery.py` | 2 |
| `_registry_store_rows.py` | 2 |
| `_supervisor_threshold.py` | 2 |
| `caam_decision.py` | 2 |
| `codex_sessions.py` | 2 |
| `foreman_act.py` | 2 |
| `foreman_act_filing.py` | 2 |
| `foreman_gather_sources.py` | 2 |
| `foreman_plan_roster_work.py` | 2 |
| `foreman_runtime_policy.py` | 2 |

*(remaining 33 files carry one each; the full per-site list is below.)*

## Bounds — read these before using the number

**98 is an UPPER bound, not a measurement of truth.** Two gaps, both stated
rather than smoothed over.

**1. Subprocess capture is incomplete, and the survey proves it against itself.**
Four sites recorded *neither* arm. That is impossible if the data were complete:
a line that never executes is a **statement** miss, and this repo's 100%
statement bar would already be red. So those four execute somewhere the probe
did not observe — in a subprocess that exits without running `atexit`, or under
a scrubbed environment that lost `ARMPROBE_DIR`. Only 3 process files were
collected from a suite that spawns far more.

The four are worth naming anyway, because two of them are the **exact shape** of
the incident this item was filed about:

```
foreman_act_consensus.py:194  reason if isinstance(reason, str) and reason != "" else "not_unanimous"
foreman_act_filing.py:189     None if jsonio.is_parse_failure(result=parsed_result) else parsed_result.unwrap()
foreman_act_ledger.py:232     match.group(1) if match is not None else None
foreman_act_ledger.py:117     None if jsonio.is_parse_failure(result=parsed_result) else parsed_result.unwrap()
```

`None if is_parse_failure(...) else ....unwrap()` is the same `unwrap`-behind-a-
ternary construction that went to master returning a `Result` instead of the
mapping inside it and cost roughly three hours of red master. It appears twice
more, and the coverage bar is blind to both.

The same gap means **some of the 98 may be false positives** — an arm exercised
only in an uncaptured subprocess reads here as never exercised. The 100%-coverage
argument does not rescue those, because coverage never sees arms at all; that is
the whole defect.

**2. Eight conditional expressions were not instrumented at all**, in
`_registry_track_row_parse.py` (1 of 4), `foreman_runtime.py` (6) and
`tmuxio.py` (1). The instrument refuses any ternary containing `await`, `yield`
or a walrus, and any in a class body, because a `lambda` there would change
scoping or evaluation semantics. Refusing is correct; **it is also a blind spot
in a blind-spot detector**, and `foreman_runtime.py` is entirely unmeasured.

## Decision on a mechanical detector

**Not adopted as a gate, deliberately, and this is the recorded reason.**

- **It would be armed red on arrival.** 98 findings, 53 files. Landing it as a
  member of `just check` blocks every push in the repository until all 98 are
  remediated. This repo has an established, better-behaved pattern for exactly
  this situation — `overseer-jct` carries 88 violations against a check that is
  deliberately unarmed pending its blocker.
- **Its false-positive rate is unknown and is not yet bounded.** Arming a gate
  whose negative cases have not been characterised is the failure this plan
  exists to stop. The two-way control above proves the instrument *can* return a
  negative for the one site whose history is known; that is not the same as
  knowing its rate across 312.
- **Not every single-arm ternary is a defect.** Some arms are unreachable by
  construction. A gate needs a sanctioned way to say so, and designing that
  escape hatch is its own piece of work — one this repo already knows how to get
  wrong, since `overseer-hgq4wi.8` and `.12` are both live bugs about escape
  hatches whose declarations nothing verifies.
- **What replaces it, and it is not nothing:** the population is now *known*
  rather than guessed, the instrument is reproducible from this note, and the
  live instance the incident named is tested and proven discriminating. That is
  the stopping point criterion 6 allows, taken with its reason.

Arming, and the remediation of the 98, are follow-on work rather than a silent
omission.

## Discriminator against `overseer-awec` — neither sweep finds the other

| | mechanism | what is hidden | the probe |
|---|---|---|---|
| **`overseer-awec`** | a multi-clause predicate | the branch **is** counted and exercised both ways; which **disjunct** decided it is not recorded, so unexercised clauses hide inside a covered branch | delete each clause and re-run |
| **this item** | a conditional expression | **there is no branch at all** — nothing to hide inside | force each arm and observe the number does not move |

`overseer-awec`'s survey looked for predicates with three or more clauses. A
ternary has none and would never appear in it. **This survey's 98 findings and
`awec`'s 15 multi-clause predicates are disjoint populations**, and a reader
arriving at either should follow the cross-reference to the other.

## Reproducing this

The instrument is two files and one run: a recorder placed in `overseer/`, and a
rewriter that walks `overseer/*.py`, replaces each `IfExp` span with a probe call
and injects the recorder's import after the `__future__` line. Run the suite with
`ARMPROBE_DIR` set, merge the per-process JSON, and report any site whose two
counts are not both non-zero. Do it in a **detached probe worktree** — and not
under `/tmp`, which the coverage config omits, so a probe placed there fails
`test_coverage_still_traces_first_party_product_paths` for reasons unrelated to
what it is measuring.

Expect four residual test failures from the mirror alone: instrumenting
`overseer/` and not `.claude-plugin/overseer/` breaks the byte-identity pair on
purpose.

## Full per-site list

`true` means the condition-true arm never executed; `false` means the else arm
never executed.

| site | arm never taken | source |
|---|---|---|
| `_registry_discovery.py:164` | true | `len(text) if end == -1 else end` |
| `_registry_discovery.py:174` | true | `len(text) if end == -1 else end + 2` |
| `_registry_epic.py:68` | false | `wrapper if wrapper is not None else []` |
| `_registry_rounds.py:185` | false | `dict(existing) if existing is not None else {}` |
| `_registry_stamps.py:159` | true | `{} if legacy is None else {"at": legacy}` |
| `_registry_stamps.py:205` | false | `baseline if isinstance(baseline, str) else None` |
| `_registry_stamps.py:221` | true | `dict(entry) if entry is not None else {}` |
| `_registry_stamps.py:262` | false | `dict(entry) if entry is not None else {}` |
| `_registry_store_rows.py:56` | false | `repo if isinstance(repo, str) else ""` |
| `_registry_store_rows.py:57` | false | `topic if isinstance(topic, str) else ""` |
| `_supervisor_attention.py:159` | false | `surface_shell_prolonged_alert(request=shell) if request.act else {"shell-prolonged"}` |
| `_supervisor_busy.py:93` | true | `note if request.malformed else None` |
| `_supervisor_config.py:223` | false | `match.group(1) if match is not None else completed.stdout.strip() or None` |
| `_supervisor_discovery_adoption.py:63` | true | `None if repo is None or topic is None else registry.read_launch_statusline_baseline( rep` |
| `_supervisor_final_ruling_sources.py:93` | false | `relay.latest_plan_comment_at if relay.latest_plan_comment_at is not None else relay.at` |
| `_supervisor_lifecycle.py:42` | false | `Path(sup.store_path) if sup.store_path is not None else registry.DEFAULT_STORE_PATH` |
| `_supervisor_pair.py:50` | true | `session if sup.tmux.session_exists(session=session) else None` |
| `_supervisor_pair_stall.py:146` | false | `sup.tmux.pane_id(session=worker_view.tmux) if worker_view.tmux else None` |
| `_supervisor_pair_stall.py:160` | false | `target if target is not None and _supervisor_observe.pane_is_managed( sup=sup, target=ta` |
| `_supervisor_pair_stall.py:201` | false | `sup.tmux.pane_id(session=supervisor_view.tmux) if supervisor_view.tmux else None` |
| `_supervisor_pair_stall.py:205` | false | `sup.tmux.pane_id(session=supervisor_view.tmux) if supervisor_view.tmux else None` |
| `_supervisor_pair_stall.py:207` | false | `sup.tmux.pane_id(session=worker_view.tmux) if worker_view.tmux else None` |
| `_supervisor_threshold.py:59` | false | `obs.eff_ctx if obs.eff_ctx is not None else request.threshold` |
| `_supervisor_threshold.py:70` | false | `obs.eff_ctx if obs.eff_ctx is not None else eff_ctx` |
| `_supervisor_working_low_context.py:93` | false | `extra if request.note is None else f"{request.note}; {extra}"` |
| `caam_decision.py:119` | false | `0.01 if force else min_headroom_gain()` |
| `caam_decision.py:157` | true | `None if profile.usage is None else profile.usage.seven_day_resets_at` |
| `caam_profile_state.py:103` | true | `time.time() if now is None else now` |
| `caam_profiles.py:119` | true | `None if body is None else body.get("tools")` |
| `caam_sessions.py:128` | true | `time.time() if now is None else now` |
| `caam_sessions.py:175` | true | `None if found is None else _mapped_model(model=found)` |
| `caam_sessions.py:192` | true | `None if body is None else body.get("message")` |
| `caam_sessions.py:193` | true | `None if message is None else message.get("model")` |
| `caam_sessions.py:194` | false | `model if isinstance(model, str) else None` |
| `caam_usage.py:66` | false | `token_value if isinstance(token_value, str) else None` |
| `caam_usage.py:68` | true | `None if expires_at is None else expires_at / 1000.0` |
| `caam_usage.py:169` | true | `None if body is None else body.get("error")` |
| `caam_usage.py:170` | true | `None if detail is None else detail.get("message")` |
| `caam_usage.py:171` | false | `message if isinstance(message, str) else f"HTTP {error.code}"` |
| `caam_warm.py:98` | true | `time.time() if now is None else now` |
| `caam_warm.py:131` | true | `time.time() if now is None else now` |
| `caam_warm.py:206` | false | `lines[0][:120] if lines else ""` |
| `codex_sessions.py:193` | false | `Path(codex_home) if codex_home is not None else default_codex_home()` |
| `codex_sessions.py:210` | false | `Path(codex_home) if codex_home is not None else default_codex_home()` |
| `foreman_act.py:181` | true | `None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()` |
| `foreman_act.py:198` | true | `_refused(action_id=None, reason="malformed_proposal") # pragma: no cover if proposal is ` |
| `foreman_act_consensus.py:70` | false | `value if isinstance(value, str) and value in ACTION_IDS else None` |
| `foreman_act_consensus.py:74` | false | `cast(DecisionRule, value) if value in {MAJORITY, UNANIMOUS} else None` |
| `foreman_act_consensus.py:204` | true | `None if ruling is None else ruling.get("kind")` |
| `foreman_act_filing.py:40` | false | `value if value is None or isinstance(value, str) else ""` |
| `foreman_act_filing.py:169` | false | `[*entries, inherited] if inherited else entries` |
| `foreman_act_journal.py:15` | false | `value if isinstance(value, str) and value != "" else None` |
| `foreman_act_ledger.py:214` | false | `value if isinstance(value, str) and value != "" else None` |
| `foreman_act_revalidate.py:48` | false | `raw_action if isinstance(raw_action, str) else None` |
| `foreman_blocked_answer.py:44` | true | `None if snapshot is None else snapshot.get("rows")` |
| `foreman_blocked_answer.py:62` | false | `value if isinstance(value, str) and value.strip() else None` |
| `foreman_blocked_answer.py:67` | false | `value if isinstance(value, str) and value.strip() else None` |
| `foreman_blocked_answer.py:73` | false | `"pane_human_gate_unverified" if "picker_open" not in row else "pane_not_human_gated"` |
| `foreman_blocked_answer.py:91` | true | `None if topic is None else _matching_row(document=document, repo=repo, topic=topic)` |
| `foreman_consensus_cache.py:57` | true | `0 if payload is None else int_field(payload=payload, key="panels")` |
| `foreman_consensus_matrix.py:86` | true | `"needs_human" if len(votes.needs_human) > len(votes.actions) else "typed_action_disagree` |
| `foreman_consensus_prompt.py:87` | false | `ACTION_ID_SET if action_ids is None else action_ids` |
| `foreman_gather.py:54` | false | `None if args.no_list_json_fallback else default_list_json_command()` |
| `foreman_gather_release_lane.py:64` | false | `"provided-history" if "release_lane_runs" in options else "forge-query"` |
| `foreman_gather_release_lane.py:101` | true | `configured if isinstance(configured, str) and configured else default` |
| `foreman_gather_release_lane.py:113` | true | `configured if isinstance(configured, str) and configured else _DEFAULT_CACHE` |
| `foreman_gather_release_lane.py:151` | false | `dict(attention) if attention is not None else {}` |
| `foreman_gather_release_lane.py:190` | false | `payload.get("measured_at") if payload is not None else None` |
| `foreman_gather_release_lane.py:191` | false | `measured_at if isinstance(measured_at, str) and measured_at else None` |
| `foreman_gather_render.py:76` | false | `"yes" if row.get("picker_open") is True else "no"` |
| `foreman_gather_sources.py:66` | true | `None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()` |
| `foreman_gather_sources.py:95` | false | `"/".join(parts[-_REPO_SLUG_PARTS:]) if len(parts) >= _REPO_SLUG_PARTS else None` |
| `foreman_pane_claim.py:80` | true | `None if payload is None else _claim_from_payload(payload=payload)` |
| `foreman_panel.py:102` | false | `Path(args.dossier_dir) if args.dossier_dir else None` |
| `foreman_panel_io.py:20` | false | `value if isinstance(value, str) else ""` |
| `foreman_panel_refusal.py:25` | false | `value if isinstance(value, str) else ""` |
| `foreman_panel_response.py:30` | true | `None if jsonio.is_parse_failure(result=fenced_result) else fenced_result.unwrap()` |
| `foreman_panel_reviewers.py:27` | false | `value if isinstance(value, str) else ""` |
| `foreman_plan_roster.py:272` | true | `Path(args.journal_path) if args.journal_path is not None else None` |
| `foreman_plan_roster_work.py:60` | false | `at if isinstance(at, str) else ""` |
| `foreman_plan_roster_work.py:71` | false | `work_item_id if isinstance(work_item_id, str) else None` |
| `foreman_runtime_policy.py:23` | false | `1 if scheduled_tick else 0` |
| `foreman_runtime_policy.py:45` | false | `value if isinstance(value, int) and not isinstance(value, bool) else 0` |
| `foreman_session_lifecycle.py:47` | false | `session_id if session_id else None` |
| `foreman_work_item_session_evidence.py:92` | false | `match.group(1) if match is not None else "overseer"` |
| `foreman_work_item_session_evidence.py:101` | false | `value if isinstance(value, str) and value != "" else None` |
| `foreman_work_item_session_store.py:30` | true | `None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()` |
| `foreman_work_item_sessions.py:58` | false | `value if isinstance(value, str) and value != "" else None` |
| `foreman_work_item_sessions.py:84` | false | `status if status in _TERMINAL_STATUSES else None` |
| `foreman_work_item_sessions.py:124` | false | `value + 1 if isinstance(value, int) else 1` |
| `grooming_conformance_values.py:140` | false | `value.lower() if isinstance(value, str) else ""` |
| `grooming_conformance_values.py:145` | false | `value if isinstance(value, str) else ""` |
| `grooming_plan_budget.py:111` | false | `spec_root if isinstance(spec_root, str) and spec_root else "SPECIFICATION"` |
| `grooming_plan_budget.py:173` | false | `value if isinstance(value, str) and value != "" else None` |
| `grooming_plan_budget.py:238` | false | `value if value != "" else None` |
| `runtime_prefix.py:27` | true | `Path.home() if home is None else home` |
| `start.py:231` | false | `io if io is not None else tmuxio.TmuxIO()` |
| `start.py:275` | false | `build_supervisor if build_supervisor is not None else supervisor.build_supervisor` |
