# Claude/Codex parity audit findings

Audit date: 2026-09-10.

## Method and baseline

The review traced the runtime-specific branches for discovery/adoption, context and
status parsing, input readiness, wrap-up and nudge delivery, state certification,
restart/resume, launch-profile preservation, liveness, recovery, status snapshots,
the bootstrap executable, and the packaged Codex skill binding. It compared the
implementation with `SPECIFICATION/spec.md`, `overseer/marker-protocol.md`,
`overseer/AGENTS.md`, and `.claude-plugin/prose/overseer.md`.

The focused Codex/runtime/recovery/model test selection completed green (one
environment-gated test skipped). The installed 5.4.3 Codex binding resolves both its
binding and shared prose from the plugin cache. Current live snapshot rows also show
Codex discovery, runtime identity, status parsing, and normal supervision operating.

## Confirmed bugs

### Operator `start` and dormant recovery do not preserve proven Codex identity

The deliberate `start` surface reaches
`_supervisor_start_cli.launch_attempt_message`, which unconditionally calls the
Claude-only `Supervisor.do_launch_result`. It ignores a mapped track's durable
`observed_session_identity`, even when that value is an exact `codex:<uuid>`.

A deterministic execution with a dead mapped track carrying
`codex:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` returned
`LaunchResult(launched=True)` and issued a `claude --model ... -n <topic>` respawn.
Claude therefore works on this path, while a previously observed Codex track is
recreated under the wrong runtime. This contradicts `SPECIFICATION/spec.md`
§"Surface-only startup" and §"Supervised runtimes", which require a crashed track
with established runtime identity to resume as that runtime and require ambiguous or
topic-only identity to be surfaced without launch.

The dormant `recover_missing_sessions` path carries the related second half of the
same evidence-chain defect. It classifies a dead track as Codex solely from the newest
same-topic entry in the global Codex index, despite the specification's explicit
stale-namesake rule and the measured warning in `overseer/AGENTS.md`. Its Codex launch
then returns success after only seeing a Codex pane command. A deterministic execution
returned `True` with an empty `live_codex` map, so it did not prove the resumed UUID,
repository cwd, or submitted resume kick. The shipped daemon currently passes
`recover=False`; this second entry point is latent, but it remains callable code and
must not retain semantics that violate the same recovery contract.

Disposition: `overseer-trocaf` is the code-only conformance bug covering the end-to-end dead-track
runtime classifier and verified launcher used by every deliberate recovery entry
point. Keeping the two manifestations together avoids implementing competing
classifiers in the `start` and recovery paths.

### Restart-model status compares Codex rows with Claude configuration

`_supervisor_restart_model_snapshot._current_default_model` always reads
`~/.claude/settings.json`, and `restart_model_payload` calls it for every row without
checking `row.runtime`. The statusline resolver likewise searches recorded profiles
without a harness constraint.

The current daemon snapshot proves the production symptom on two live Codex rows.
Each row rendered `gpt-5.6-sol xhigh`, but its restart-model payload reported Claude's
`opus[1m]` as `current_default`, resolved that to `Opus 5 (1M context)`, and emitted
`verdict=would-change`. That is not evidence about what a profile-less `codex resume`
would select.

Disposition: `overseer-kmgxk4` is the code-only observability bug requiring runtime-specific default
sources and harness-scoped statusline resolution, with the existing Claude behavior
retained.

### Codex mid-session model changes are not preserved

The existing backlog item `overseer-v55x` accurately carries this known parity gap.
Claude may capture a permitted top-level transcript model token after `/model`, while
the Codex rollout-body prohibition leaves Codex with only its launch model. This audit
found no permitted-source implementation that closes the gap and no reason to
duplicate the existing item.

Disposition: adopt `overseer-v55x` into this plan. It remains mixed spec+code and must
be groomed into separate spec-side and implementation-side slices before dispatch.

## Investigated and not filed

- Fresh Codex sessions before their first turn can be absent from rollout-fd
  discovery. The exact shape was already investigated and dispositioned by closed
  item `overseer-mir`; post-turn mapped unindexed adoption is covered by closed item
  `overseer-6eo` and current tests.
- Codex pair nudges remain intentionally stricter than ordinary Codex low-context
  delivery because the specification requires a positively empty composer for the
  pair nudge. This is a deliberate safety asymmetry, not a bug.
- Reading a Codex rollout body to learn the runtime model is expressly forbidden.
  The missing model-preservation mechanism is real, but the Claude transcript reader
  is not an implementation template for Codex.
- The installed Codex skill binding and bootstrap/runtime-ancestry tests pass; no
  separate plugin-root or bootstrap defect was reproduced.
- Current Codex structural busy/idle/gate parsing, wrap-up delivery, ready
  certification, exact-UUID ordinary restart, post-respawn process verification,
  and node-fronted process identity are covered by focused green tests. No duplicate
  work item was filed for those paths.
