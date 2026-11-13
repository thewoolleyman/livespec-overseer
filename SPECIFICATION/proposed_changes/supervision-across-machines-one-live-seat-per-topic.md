---
topic: supervision-across-machines-one-live-seat-per-topic
author: herdr-overseer
created_at: 2026-11-13T21:16:59Z
---

## Proposal: Supervision across machines: a daemon per machine and one live seat per plan topic

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md
- SPECIFICATION/constraints.md

### Summary

Supervised seats now run on more than one Linux machine. Each such machine runs its own daemon, which supervises only its own panes, so every input the restart interlock trusts stays host-local. A LIVE-SEAT RECORD on the plan's ledger epic ensures each plan topic has at most one live supervised seat across machines. The record is written only by an atomic conditional write and names the holding machine by its `/etc/machine-id`. Binding a session (by the daemon), replacing a seat (by the daemon), and launching a session through the sanctioned relaunch entrypoint or any other session-starting surface each require holding it. The record never expires with time, and a record that cannot be verified holds the act, so the guarantee fails toward NOT opening a second seat.

### Motivation

The Hetzner migration (plan bootstrap-credentials-and-onboarding, epic hxi-vxsmdv) began moving interactive seats from vmi3006760 to hetzner-xubuntu on 2026-11-13, starting with wave 1 (stale-base-merge-options), under a maintainer rule of one live seat per plan: the old seat exits before the new one opens. Measured the same day: overseerd (v5.55.8) supervises only the panes of its own host, and `herdr --machine hetzner-xubuntu agent list` returns 0 agents, so moved seats get no wrap-up, no ready-gated replacement and no resume, and legacy-coordinator-agent restarts them by hand. Today's specification defines supervision of the daemon's own host only and names no cross-machine guard. Filed as overseer-5y7ebe. Design (b), a daemon per machine plus a shared live-topic record, was accepted by the coordinator over design (a), one daemon reaching remote machines over SSH, because every input the interlock trusts (process identity and start time, session and rollout files, the state file, the v102 memory floor) is host-local. The record is not called a 'lease', so it cannot be confused with the credential manager's time-expiring run-scoped account lease (scenarios.md 'Lease expiry restores account eligibility'): this record never expires with time.

### Proposed Changes

In SPECIFICATION/spec.md, insert a new section immediately before "## Session-name derivation":

> ## Supervision across machines
>
> Supervised seats MAY run on more than one machine. Each machine that hosts supervised seats and meets the runtime requirements (constraints.md §"Runtime requirements": Linux, with tmux or herdr) runs its OWN daemon, and a daemon supervises only the panes of the machine it runs on. A SUPERVISED MACHINE is any machine running a daemon. That set is independent of the credential-rotation role holder and its listed hosts under §"Account rotation and quota supervision": listing a host there neither makes it a supervised machine nor is required to make it one. Every input a daemon's decision depends on is read on the machine that runs the seat, never fetched from another machine: process identity and start time, the agent's session and rollout files, the track's state file, and the host memory floor of §"The restart". Each machine keeps its own mapping store. Because the same repositories are checked out on several machines, daemons on different machines discover the same tracks. Discovery is unchanged, and a track with no live seat on a daemon's own machine receives no act from that daemon.
>
> **One live seat per plan topic.** At most one live supervised seat may exist for a plan topic across all supervised machines. The record that enforces this is the topic's LIVE-SEAT RECORD. It is held on the plan's ledger epic, the epic id the mapping store already records for the track, because that is the one record every machine's daemon can reach. A live-seat record names: the holding machine by its `/etc/machine-id`, which is what every comparison uses; that machine's hostname, which is display only; the holding seat's session identity; and the time it was last written. It is NOT plan state. It is never a handoff entry, the daemon still never reads the epic's handoff entries, and the record on its own authorizes no restart. A live-seat record is written ONLY by an atomic conditional write that succeeds only when the record is absent or already names the writer's own machine, so two machines can never both hold it. It is written at exactly three moments: when a seat is bound to the topic (taken, naming that seat's session identity); after a successful replacement (rewritten to name the successor's session identity, on the same machine); and when the holder releases it. It is read by a daemon before binding and before replacing, by every session-starting surface before it launches, and by the duplicate-seat condition below, to name the holder. It is never renewed and never expires with time.
>
> The DAEMON MUST hold the topic's live-seat record, read fresh for that act, before it binds a discovered session to the track and before it starts a seat replacement. The replacement passes through the restart interlock unchanged; the record is an additional precondition, never a substitute for it. The sanctioned out-of-band relaunch is not a daemon act (§"The sanctioned out-of-band relaunch"). Its operator entrypoint, and every other surface that starts a session for a supervised plan topic, MUST take or verify the topic's live-seat record for its own machine before it launches, MUST NOT launch when the record names another machine, and re-binds the track's mapping row only while holding it. When a daemon finds a live local session for a topic whose record names ANOTHER machine, it MUST NOT bind, replace, keystroke or terminate that session, and MUST journal one `live-seat-held-elsewhere` event, edge-triggered (§"Notify, never block"), naming the topic, the record's holding machine and its own. A daemon releases a record it holds only when it observes that its own seat for the topic is gone: the session has exited and is not being replaced.
>
> **An unverifiable record fails toward one seat.** A record is NEVER taken over because time passed. A record held by a machine that has stopped, or that no other machine can reach, stays held until that machine's daemon releases it, or until an operator releases it with an explicit, attributed release naming the topic and the machine. A daemon does not probe other machines and makes no claim about their reachability. While the ledger cannot be read or written, and for any track that carries no recorded epic id (and so has no record to verify), a daemon MUST treat the record as NOT held by itself. It MUST hold each act that requires the record the way it holds a replacement below the memory floor: the ready declaration and the round are preserved, the act is retried on a later tick, and one `live-seat-unverifiable` event naming the topic and the reason is journaled, edge-triggered. Observation, context reading, wrap-up injection, submission retries into an already-running session, and alerts are not gated by the record, so a seat that is already live keeps being supervised on its own machine.
>
> **Where the guarantee does not reach.** The guarantee holds only among daemons, and session-starting surfaces, that run a build implementing this section. During a rollout, a machine still running an earlier daemon neither reads nor writes the record, so the guarantee holds only once every supervised machine runs a build that does. A seat on a machine that cannot run a daemon, such as a macOS host (outside constraints.md §"Runtime requirements"), is unsupervised and holds no live-seat record, so no daemon can see it. The operator MUST NOT run a seat for a supervised plan topic on such a machine while that topic is live on a supervised machine, and MUST NOT start one on a supervised machine while it runs on such a machine.

In SPECIFICATION/spec.md, amend the sentence in the section on filesystem boundaries that reads "The overseer's daemon writes its runtime state to exactly two places: its home-directory stores and a per-track temporary directory inside each watched repository's gitignored scratch area." to read: "The overseer's daemon writes its runtime state to exactly three places: its home-directory stores, a per-track temporary directory inside each watched repository's gitignored scratch area, and, for the live-seat record of §\"Supervision across machines\" only, the plan's ledger epic."

In SPECIFICATION/constraints.md §"Filesystem boundaries", amend "The overseer's daemon writes its runtime state to exactly two places: its operator-home stores and the per-track scratch directory `<repo>/tmp/overseer/<topic>/` inside each watched repository." to read: "The overseer's daemon writes its runtime state to exactly three places: its operator-home stores, the per-track scratch directory `<repo>/tmp/overseer/<topic>/` inside each watched repository, and, for the live-seat record of spec.md §\"Supervision across machines\" only, the plan's ledger epic."

In SPECIFICATION/scenarios.md, add after "## Scenario: A ready seat is held, not replaced, while the host is below its memory floor":

> ## Scenario: A topic live on one machine is not bound on another
>
> Given plan topic T's live-seat record names machine M1 and a seat there
>
> And the daemon on machine M2 discovers a live local session for topic T
>
> When the daemon on M2 observes the track
>
> Then it does not bind, replace, keystroke or terminate the M2 session
>
> And it journals one `live-seat-held-elsewhere` event naming T, M1 and M2
>
> And the record still names M1
>
> ## Scenario: A stopped machine's live-seat record is not taken over by time
>
> Given plan topic T's live-seat record names machine M1
>
> And machine M1's daemon has stopped for longer than any supervision interval
>
> And a session for topic T is started on machine M2
>
> When the daemon on M2 observes the track
>
> Then it does not bind the M2 session
>
> And the record still names M1
>
> When an operator releases T's record with an attributed release naming T and M1
>
> Then the daemon on M2 takes the record and binds the M2 session
>
> ## Scenario: A ready seat is held while its live-seat record cannot be verified
>
> Given a supervised seat on machine M1 holds plan topic T's live-seat record and has declared a certifiable `ready`
>
> And the ledger cannot be reached from M1
>
> When the daemon on M1 would start the replacement
>
> Then it does not terminate, respawn or keystroke the session
>
> And the `ready` declaration and the open round are preserved
>
> And it journals one `live-seat-unverifiable` event naming T
>
> And the seat's context reading continues to be observed
>
> When the ledger is reachable again and the record still names M1
>
> Then the replacement proceeds through the ordinary restart interlock
>
> ## Scenario: A seat moved between machines is bound only after the old seat releases
>
> Given plan topic T's live-seat record names machine M1 and its live seat there
>
> When the M1 seat exits and is not being replaced
>
> Then the daemon on M1 releases T's record
>
> When a session for T is then started on machine M2
>
> Then the daemon on M2 takes the record and binds the M2 session

Coverage and follow-ups. The ratified change adds five `## ` headings that need rows in tests/heading-coverage.json and its debt register: the new spec section and the four scenarios. They are owned by overseer-5y7ebe, which stays OPEN as their work_item owner until the implementation follow-ups exist. Those follow-ups are filed as separate factory children of plan overseer-uzvcbn after ratification: (1) the live-seat record on the ledger epic, with its atomic conditional write and the attributed operator release; (2) the record gate on daemon binding and replacement, with the `live-seat-held-elsewhere` and `live-seat-unverifiable` holds and events; (3) the record gate on the sanctioned relaunch entrypoint and the other session-starting surfaces; (4) running a daemon on a second machine (hetzner-xubuntu), with its host-captured proof of a seat moved between machines. Only after they exist are the coverage rows re-pointed to them and 5y7ebe closed. The record's ledger encoding, and the exact conditional-write primitive the ledger offers, are implementation choices bounded by the atomicity requirement above.
