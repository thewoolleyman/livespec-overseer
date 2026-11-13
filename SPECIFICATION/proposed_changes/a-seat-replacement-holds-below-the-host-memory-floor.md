---
topic: a-seat-replacement-holds-below-the-host-memory-floor
author: herdr-overseer
created_at: 2026-11-13T16:58:00Z
---

## Proposal: A seat replacement holds while the host is below its committed memory floor

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Before the daemon starts any seat replacement it reads the host's memory reading (MemAvailable from /proc/meminfo and the memory PSI `some avg10` from /proc/pressure/memory) and compares it with the host's committed load floor, read from the one rendered host file every fleet consumer reads. Below the floor the replacement is HELD, not cancelled: the ready declaration is preserved, the round stays open, and one journaled event names the track and the reading. The floor values are never literals in the daemon's code.

### Motivation

On 2026-11-13 the release host vmi3006760 was rebooted at about 15:53Z after memory exhaustion: about 450 MB free, committed memory at 105%, up to 126 blocked tasks. The coordinator's standing rule since then is that no seat is replaced while MemAvailable is below 24G or memory PSI some avg10 is at or above 5. That rule lives only in /var/tmp/vps-load-guard.sh and in messages between operator sessions. overseerd is the only seat-replacement path on the host, and it reads neither: measured on the running daemon at 16:5xZ (v5.55.8, pid 155681), nothing under overseer/ reads /proc/meminfo or /proc/pressure/memory, so a replacement would proceed at any memory level. A rule the acting component never reads is enforced only while an operator happens to be watching. Filed as overseer-uzvcbn.23.

### Proposed Changes

In SPECIFICATION/spec.md §"The restart", insert after the paragraph that ends "…the event changes no gate and authorizes nothing." a new paragraph:

> **The host memory floor.** A seat replacement adds a whole new session to a host before its predecessor's memory is released, so the daemon MUST NOT start one while the host is short of memory. Immediately before every seat replacement the daemon starts — the herdr guarded replacement transaction and the tmux native replacement alike, and any replacement path added later — it MUST take one fresh reading of the host's available memory (`MemAvailable` in `/proc/meminfo`) and memory pressure (the `some avg10` value in `/proc/pressure/memory`) and compare it with the host's memory floor. The floor is a minimum available memory and a maximum pressure, and the replacement proceeds only when the available memory is at or above the minimum AND the pressure is below the maximum. The floor values MUST be read from the host load-floor file, `/etc/livespec/host-load-floor.json`, and MUST NOT be literals in the daemon: each host's file is rendered from THAT HOST's own committed load-floor entry in the fleet gitops inventory (the same inventory that renders `/etc/livespec/fabro-factories.json`), because hosts differ in memory and swap and need different floors; on each host that one rendered file is the single floor source that the daemon, the dispatcher's ticket helper and the operator load guard all read, so none of them can drift from the others. Below the floor the replacement is HELD, not failed: the daemon MUST NOT terminate, respawn, keystroke or re-brief the session, MUST preserve the `ready` declaration and the open round, and MUST re-take the reading on a later tick, proceeding once a reading clears the floor. Holding never weakens the restart interlock: a held seat is still replaced only on a certifiable `ready`, and a cleared floor authorizes nothing the interlock does not. A hold MUST be visible: the track's row names the memory-floor hold and the reading that caused it, and the daemon MUST journal one `restart-held-by-memory-floor` event naming the track, the reading (available memory and pressure) and the floor it failed, on entry to the hold, and one on release, never one per tick (per §"Notify, never block"). The floor gates seat replacement only; it does not gate observation, wrap-up injection, submission retries into an already-running session, or alerts. When the host load-floor file is absent, the daemon applies no floor and MUST surface that once, edge-triggered, as an unconfigured-floor notice, so a host without a floor is visible rather than silently unguarded. When the file exists but cannot be read or parsed, or a memory reading cannot be taken, the daemon MUST treat the reading as below the floor (hold) and surface the failure once, edge-triggered: an unknown reading never authorizes a replacement. Taking the reading MUST be bounded and MUST NOT delay other tracks' observation.

In SPECIFICATION/scenarios.md, add after the scenario "A Codex successor launch disables Codex's startup update check":

> ## Scenario: A ready seat is held, not replaced, while the host is below its memory floor
>
> Given a host whose own `/etc/livespec/host-load-floor.json`, rendered from that host's committed load-floor entry, sets a minimum available memory of 24 GiB and a maximum memory pressure `some avg10` of 5
> And a supervised track whose session has declared a certifiable `ready`
> When the daemon's reading immediately before the replacement shows 20 GiB available
> Then the daemon does not terminate, respawn or keystroke the session
> And the `ready` declaration and the open round are preserved
> And the daemon journals one `restart-held-by-memory-floor` event naming the track, the 20 GiB reading and the 24 GiB floor
> And the track's row names the memory-floor hold
> And no further hold event is journaled while the reading stays below the floor
> When a later reading shows 30 GiB available and pressure 0.4
> Then the daemon journals the release and performs the replacement through the ordinary restart interlock

The ratified change owes one impl follow-up: overseer-uzvcbn.23 (restate its Definition of Done to this text before dispatch; its current text names a guard executable rather than the floor file). It also owes a cross-repo follow-up in livespec-dev-tooling: a committed load-floor entry per host in the inventory and its rendering to each host's /etc/livespec/host-load-floor.json, with /var/tmp/vps-load-guard.sh and the dispatcher's ticket helper re-pointed to read it. That file's schema is owned there: this change requires only a minimum available memory in GiB and a maximum memory-pressure some-avg10, and the daemon ignores any other key the guard uses (procs_running, /tmp usage).
