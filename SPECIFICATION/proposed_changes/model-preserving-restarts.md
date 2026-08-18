---
topic: model-preserving-restarts
author: claude-sonnet-5
created_at: 2026-08-18T21:54:27Z
---

## Proposal: launch-profile-record-and-reassert

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Today neither the Claude nor the Codex restart command carries the track's model, so a bare relaunch takes whatever default the runtime's own config currently holds — a silent downgrade for hand-picked models, and for a local-llm track a silent conversion from the local router back to the cloud API. This proposal makes the daemon record a per-track launch profile {harness, model, wrapper|null}, read from the live session and never guessed, and re-assert it on every restart so a restart never changes WHAT a track runs, only that it runs fresh.

### Motivation

Verified on current master 2026-08-13: a Claude restart runs `claude --dangerously-skip-permissions -n <topic>` with no model flag, so a restarted session takes `~/.claude/settings.json`'s default model (subject to change over time) regardless of what model the operator originally launched with; a Codex restart resumes by UUID but does not re-assert a non-default provider/model. Worse, local-llm tracks (repo local-llm) launch through env wrappers that export ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN/ANTHROPIC_MODEL and unset cloud credentials — a bare relaunch of such a track silently converts it back onto the cloud API with different credentials and context limits. The cardinal rule already guarantees WHEN a restart happens; nothing today guarantees WHAT gets relaunched matches what was there before.

### Proposed Changes

In spec.md §"The restart", add a clause: the daemon MUST record a per-track launch profile — `{harness, model, wrapper|null}` — read from the live supervised session, and MUST re-assert that profile on every restart of that track, so a restart never silently changes the runtime, model, or wrapper a track runs under. The daemon MUST read the profile from `/proc/<pid>/environ` and argv/parent-chain as the primary source, and MAY use the statusline's rendered model name only as a mismatch-detection verification signal, never as the primary source or as a display-name-to-launch-token lookup table. The daemon MUST capture the profile at adoption (first join) and MUST re-check it at wrap-up time, so a mid-session `/model` switch is honored in the next restart's re-assertion. The `harness` value MUST be treated as an open string in storage (so an unrecognized future harness like `pi` can be recorded without a schema change), but the daemon MUST dispatch a relaunch only for a harness it recognizes; an unrecognized or unadoptable harness's profile MUST be surfaced report-only and MUST NOT be used to construct or guess a relaunch command. A track's mapping row that carries no launch profile MUST continue to relaunch exactly as it does today (fail-soft; no migration is required of existing rows). A launch profile MUST NOT record any secret or token value (auth tokens, API keys); it MUST only record the harness, the model token, and the wrapper's path, since the wrapper itself owns its own secrets. On every relaunch, the daemon MUST explicitly set or unset `ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, and the `CLAUDE_CODE_*` context-limit override environment variables rather than passively inheriting them — set to the recorded profile's values for a wrapper/local track, and unset for a cloud track with no wrapper recorded — because a wrapper's own `:-`-deference default means a leaked inherited value would silently win over the wrapper's intended default. A stale or corrupt profile (a recorded wrapper path that is missing or not executable, a recorded model token the runtime rejects, or a harness/wrapper mismatch) MUST be surfaced and MUST cause the daemon to skip that restart rather than silently falling back to a default-model or default-wrapper launch, which would reproduce the exact silent-downgrade defect this clause exists to close.

In contracts.md §"Durable stores", extend the mapping store's (`~/.livespec-overseer.jsonl`) durable-keys list with an optional `model_profile` object, `{harness: string, model: string, wrapper: string|null}`, one row per track. A row without `model_profile` MUST behave exactly as a row does today. `model_profile` MUST NOT carry any key other than `harness`, `model`, and `wrapper`; in particular it MUST NOT carry an environment-variable blob, which would let secret-shaped values leak into a plaintext store and would rot independently of the wrapper it is meant to describe. Readers MUST treat a `model_profile` whose `wrapper` path does not exist and is not executable, or whose `harness` is unrecognized for the track's detected runtime, as stale: the daemon MUST surface this and MUST skip the restart for that tick rather than launching with a guessed or default profile.

In scenarios.md, add Given/When/Then scenarios covering: (1) a cloud-launched track with an explicit non-default model records that model at adoption and a subsequent restart relaunches with the same explicit model, never the runtime's own default; (2) a local-llm track's recorded wrapper and model are re-asserted at restart by prefixing `ANTHROPIC_MODEL=<recorded>` onto the wrapper invocation and passing the wrapper through with the required autonomy flags, and the daemon does not leak its own cloud credentials into that relaunch; (3) a track whose recorded `model_profile` names a wrapper path that no longer exists on disk is surfaced and skipped rather than restarted with a default launch; (4) a track with no recorded `model_profile` at all restarts exactly as it does today, unaffected by this change.
