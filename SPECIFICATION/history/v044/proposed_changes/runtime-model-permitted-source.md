---
topic: runtime-model-permitted-source
author: claude-opus-4-8
created_at: 2026-09-02T16:25:24Z
---

## Proposal: The Claude transcript's runtime model token is a permitted source

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Amend spec.md §"The launch profile" so that, for a Claude-harness track, the model token on the latest top-level (non-sidechain) assistant message in the session's conversation transcript is a PERMITTED SOURCE for the launch profile's model, expressing a mid-session model change and preferred over argv/environ ONLY when its base model token differs from the launched model; where it names the same base model, the launch source's token is retained so a context-window or other launch-token variant is never silently dropped. The transcript source is fail-soft and Claude-only. Add two Given/When/Then scenarios to scenarios.md (mid-session change captured; same-base variant retained), each linked from tests/heading-coverage.json.

### Motivation

The daemon records a track's model from launch identity only — argv --model, else ANTHROPIC_MODEL in the environ. A mid-session /model switch updates neither, so on a ready-restart the track reverts to its LAUNCH model, silently undoing the runtime switch. Verified live 2026-09-02: track ci-runner-pod-lifecycle-reliability was switched to Fable 5.1 at runtime but its recorded model was claude-opus-4-8[1m] (from argv), so the daemon would restart it as Opus 4.8. The spec already reverts to the launch model "where a session's current model is expressed in no permitted source" and already contemplates honoring a mid-session change "where a permitted source expresses it" — so admitting a new permitted source is the spec's own mechanism, not a workaround. The Claude conversation transcript records message.model as a real launch TOKEN (e.g. claude-fable-5-1), not a rendered display name, so it satisfies the existing prohibition on a display-name-to-launch-token lookup table. A naive "prefer transcript over argv" would regress, however: the transcript strips the launch token's bracketed context-window variant (it records claude-opus-4-8 where argv carries claude-opus-4-8[1m]), so an unconditional preference would silently drop the 1M-context variant on every opus-4-8[1m] track that never switched — exactly the silent-model-downgrade class this subsystem exists to prevent. The base-model comparison rule closes that gap. Codex is out of scope: the Codex session reader must never read rollout bodies (a hard maintenance invariant), so Codex runtime-model capture is deferred to its own design.

### Proposed Changes

Amend `SPECIFICATION/spec.md` §"The launch profile" to admit a new permitted source for the profile's `model`, and add the covering scenarios to `SPECIFICATION/scenarios.md` with their `tests/heading-coverage.json` links (co-edited atomically per spec.md §"Self-application").

Normative clauses to add to §"The launch profile":

1. For a Claude-harness track, the daemon MUST additionally read a candidate model token from the session's own conversation transcript: specifically the `model` token carried on the LATEST TOP-LEVEL assistant message, where a top-level message is one that is NOT a sidechain / sub-agent message. This transcript token is a PERMITTED SOURCE for the launch profile's `model`, alongside argv and `/proc/<pid>/environ`.

2. The transcript token records a REAL launch model token, not a rendered display name. Admitting it therefore MUST NOT be read as weakening the existing prohibition: the statusline's rendered model name remains verification-only and MUST NOT be turned into a launch token through a display-name-to-launch-token lookup table. The transcript source is a distinct, token-valued source and needs no such table.

3. The transcript token expresses a mid-session model change — and the daemon MUST prefer it over argv/environ — ONLY when its BASE model token differs from the base model token named by the launch source (argv, else environ). The BASE model token is the model token with any trailing bracketed context-window or variant suffix (for example `[1m]`) removed. Where the transcript names the SAME base model as the launch source, the daemon MUST retain the launch source's token, so a context-window or other launch-token variant recorded at launch is never silently dropped by a source that does not carry it.

4. Where the transcript expresses a differing base model, the daemon MUST record that transcript token as the profile's `model`, so a restart preserves the model the track is actually running rather than reverting to the launched model.

5. The transcript source MUST be fail-soft. An absent, unreadable, or unparseable transcript, or a transcript exposing no usable top-level assistant model token — a synthetic or otherwise non-token `model` value is not usable — MUST NOT be treated as a mismatch and MUST fall back to the launch source (argv, else environ), exactly as today. Sidechain / sub-agent assistant messages MUST be excluded when selecting the latest top-level model, because a session mixes models across its main thread and its sub-agents.

6. This transcript source applies to the CLAUDE harness ONLY. The daemon MUST NOT read a Codex session's rollout body to derive a runtime model; a Codex track continues to record its launched model. Codex runtime-model capture is deferred to a separate design.

Every other guarantee of §"The launch profile" is preserved unchanged: the set-or-scrub rule for the controlled Claude environment variables on every relaunch, the surfacing of divergence, the stale/corrupt-profile skip, the fail-soft launch COMMAND for a row with no recorded profile, and the wrapper handling. No `SPECIFICATION/contracts.md` change is required: the `model_profile` object's shape (`{harness, model, wrapper, statusline_model?}`) is unchanged — the transcript is a SOURCE for `model`, not a new stored field.

Scenarios to add to `SPECIFICATION/scenarios.md` (Given/When/Then), each linked from `tests/heading-coverage.json` to the clauses above:

```
## Scenario: The launch profile captures a mid-session model change from the transcript

Given a live Claude track launched with model `claude-opus-4-8` recorded in its argv
And its conversation transcript's latest top-level assistant message names model `claude-fable-5-1`
When the daemon captures the track's launch profile
Then the profile's model MUST be `claude-fable-5-1`
So that a restart preserves the model the track is actually running rather than its launched model
```

```
## Scenario: A same-base transcript model retains the launch token's context-window variant

Given a live Claude track launched with model `claude-opus-4-8[1m]` recorded in its argv
And its conversation transcript's latest top-level assistant message names model `claude-opus-4-8`
When the daemon captures the track's launch profile
Then the profile's model MUST remain `claude-opus-4-8[1m]`
So that the `[1m]` context-window variant is not silently dropped by a source that does not carry it
```

Each new scenario heading MUST be added to `tests/heading-coverage.json` with a `spec_root` of `SPECIFICATION`, a `spec_file` of `scenarios.md`, and a `test` naming the hermetic capture test that pins it, per the project's scenario-to-test linking discipline.
