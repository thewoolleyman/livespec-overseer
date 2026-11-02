---
topic: daemon-reports-codex-session-to-backend
author: claude-opus-5-5
created_at: 2026-11-02T08:32:13Z
---

## Proposal: The daemon reports a confirmed fresh Codex successor to the backend for the pane it launched it in

### Target specification files

- SPECIFICATION/spec.md

### Summary

Add a subsection to spec.md §"The restart" governing the daemon's own fresh-Codex-successor launch in a guarded replacement: once the Codex session index confirms a thread created by that launch named exactly the track's derived session name, the daemon MUST report that thread to the terminal backend as the agent session of the replacement record's pane only (for a backend that accepts such a report), never for a pane read from a process environment; it MUST accept the successor as proven without any rollout file open while keeping every other successor-proof condition; and an unconfirmed rename reports nothing and leaves the successor unproven with the ready declaration retained. The supervision-round sentence citing the rename's evidence is re-pointed at the new subsection, since that evidence is a thread, not a rollout.

### Motivation

Work item overseer-rthizs. Measured on the fleet host 2026-11-02 (herdr 0.9.5, codex-cli 0.166.0): every Codex session thread runs inside a shared `codex app-server --managed-daemon` whose environment holds an unrelated pane's HERDR_PANE_ID, so the backend's own SessionStart hook either reports nothing or reports for the wrong pane, and `herdr agent list` shows no agent_session for any Codex pane. The TUI in the carrier's pane holds no rollout file open and logs no thread id. So §"Supervised runtimes" (identification from a backend-reported session) has no input for managed Codex carriers, and the daemon's herdr Codex successor proof, which in practice requires a rollout fd, can never succeed for a managed successor (the 2026-11-02 00:32Z live-exercise failure on plan herdr-overseer). The launcher is the only party that knows which pane it launched into, and it already confirms `/rename` against the index. v083 imposed the same report on the sanctioned out-of-band relaunch entrypoint only; nothing requires the daemon's own restart path to make it. herdr exposes `herdr pane report-agent-session`, but the text stays backend-neutral as v083 does. The dispatcher's spec-change-tier screen refuses rthizs until this behaviour is stated.

### Proposed Changes

In SPECIFICATION/spec.md §"The supervision round", in the sentence about a daemon-authored payload that asks the runtime for no turn, replace "(for a Codex rename, the durable session-index record binding the successor's rollout to the topic)" with "(for a Codex rename, the durable session-index record of §"The fresh Codex successor's proof and backend report")".

In SPECIFICATION/spec.md §"The restart", immediately before the "### The launch profile" subsection, add:

### The fresh Codex successor's proof and backend report

This subsection governs the daemon's own replacement of a Codex track through the guarded replacement of contracts.md §"The restart interlock", once it has launched a fresh Codex successor into the retained shell. After the launch, the daemon submits `/rename <name>` to the successor, where `<name>` is the track's derived session name under §"Session-name derivation". The daemon MUST treat the rename as confirmed only when, within the replacement's bounded wait, the Codex session index records a thread created by this launch, absent from the index when the launch attempt was recorded, whose name equals EXACTLY `<name>` and whose identifier differs from the predecessor's session identity.

Once the rename is confirmed, the daemon MUST report that thread's identifier to the terminal backend as the agent session of the replacement record's pane on its recorded backend instance, and of no other pane, for a backend that accepts such a report. The daemon MUST report a Codex agent session only for a pane in which it launched that carrier itself, as named by its own durable replacement record. It MUST NOT report one for a pane read from any process's environment: a Codex session thread hosted by a shared runtime server runs in a process whose environment can name an unrelated pane. A report the backend rejects MUST be surfaced. A rejected report MUST NOT by itself void a proof that otherwise holds.

The daemon MUST accept the successor as proven when all of the following hold: the predecessor process is gone; the successor is a process started by this launch in the same retained shell, pane and backend instance; the rename is confirmed as above; and the identifier reported to the backend is the one the index named for `<name>`. It MUST accept that proof even when the successor holds no rollout file open, because a successor whose thread is hosted by a shared runtime server holds none. The proof MUST NOT rest on a rollout file's write time or recency, and MUST NOT open, read, parse or hash any rollout body. Every other condition of contracts.md §"The restart interlock" still applies: the ready declaration is consumed only after the proven successor's verified continuation, and no recovery path applies the predecessor's authorization to the successor.

When the rename is not confirmed within the bound, the daemon MUST report no agent session to the backend for any pane, and the successor MUST stay unproven. The replacement then keeps the ready declaration, surfaces the unnamed successor and delivers no resume line, exactly as §"The supervision round" requires, and that declaration authorizes no further termination or launch.

## Proposal: Scenarios for the daemon's fresh Codex successor report and proof

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Add two scenarios after the existing Codex herdr unconfirmable-rename scenario: a confirmed successor is reported for its launch pane only and proven without a rollout file, and an unconfirmed rename reports nothing and leaves the successor unproven with the declaration retained.

### Motivation

Every MUST of the new subsection is load-bearing behaviour and needs a Given/When/Then scenario. They are modelled on v083's sanctioned-relaunch Codex scenario and its unconfirmed-rename sibling, and sit beside the existing herdr Codex replacement scenarios they extend.

### Proposed Changes

In SPECIFICATION/scenarios.md, immediately after "## Scenario: A Codex herdr replacement delivers the resume line after an unconfirmable rename", add:

## Scenario: A confirmed fresh Codex successor is reported for its launch pane and proven without a rollout file

Given a Codex track on a terminal backend that accepts agent-session reports, whose fresh ready declaration authorized a guarded replacement

And the daemon has proven the predecessor gone and launched a fresh Codex successor in the retained shell of the recorded pane, then submitted /rename <name> with the track's derived session name

And the successor holds no rollout file open, and the environment of the process hosting its thread names a different pane

When the Codex session index records a thread created by this launch, named exactly <name>, whose identifier differs from the predecessor's session identity

Then the daemon reports that thread identifier to the terminal backend as the agent session of the recorded pane and of no other pane

And no agent session is reported for the pane named by the hosting process's environment

And the daemon accepts the successor as proven without any rollout file, rollout write time or rollout body

And the ready declaration is consumed only after the proven successor's verified continuation

## Scenario: An unconfirmed rename leaves a fresh Codex successor unreported and unproven

Given the daemon has launched a fresh Codex successor in the retained shell of a Codex track's recorded pane and submitted /rename <name> with the track's derived session name

When the Codex session index records no thread created by this launch named exactly <name> within the replacement's bounded wait

Then no agent session is reported to the terminal backend for any pane

And the successor is not accepted as proven, and the unnamed successor is surfaced

And no resume line is delivered, and the ready declaration is retained and authorizes no further termination or launch

Each of these scenarios MUST be reached by a test, or carried by a heading-coverage row naming its owning work item.
