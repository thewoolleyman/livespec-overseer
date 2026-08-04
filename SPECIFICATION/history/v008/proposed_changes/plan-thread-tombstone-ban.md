---
topic: plan-thread-tombstone-ban
author: claude-opus-5
created_at: 2026-08-04T13:26:29Z
---

## Proposal: An archived plan thread MUST leave nothing at its live path

### Target specification files

- SPECIFICATION/spec.md

### Summary

Closes the hole two live tombstones went through. §"Track discovery and the mapping store" already says archived plans are excluded from discovery and that rows whose plan has been archived are garbage-collected; it does not say that an archived plan MUST NOT be kept alive by residue at the live path. Because the archived-or-deleted test keys on the DIRECTORY, anything that keeps `plan/<topic>/` in existence makes an archived thread read as ACTIVE, so its mapping row survives every garbage-collection pass and the finished thread stays nudgeable, wrap-up-injectable and RESTARTABLE. The clause states the prohibition as a STATE invariant, states the mechanism that makes it load-bearing, names the two sanctioned dispositions, and settles what the ACTIVE-plan-wins precedence beside it does and does not authorize.

### Motivation

This is not hypothetical. Measured from `tmp/overseer/daemon.log` on 2026-08-04: `daemon-liveness-truth` was RESTARTED 1h02m after its archive merged (archive `66adcc0` at 03:05:59Z, restart at 04:07:46Z), and `fleet-charter-remediation` was RESTARTED 4h19m after its archive merged (archive `b0f748e` at 05:28:28Z, restart at 09:47:18Z) and nudged again at 19:38:44Z, 14h10m after it was finished. In both cases the archive had landed and the operator had every reason to believe the track was gone.

The stub convention arose as a workaround for a real defect — an archive relocates a thread while the mapping store's stored `handoff`/`resume` row still points at the old path (`overseer-y26`) — and it is the wrong shape of fix, because it disarms the mechanism that would have made the workaround unnecessary. The garbage collector drops a row exactly when the plan reads archived; residue at the live path guarantees it never does. The workaround converts a transient window into a permanent one.

Nor does a stub stay inert. `plan/fleet-charter-remediation/` accumulated live routing instructions, a discharged-loose-end section that two sessions independently re-did, and a self-correcting count — a tombstone doing plan work, which is what a live plan thread or a work-item is for.

Writing the rule down here, rather than leaving it to convention, is what makes it survivable: livespec core's Planning Lane guidance already holds that `plan/<topic>/` is active if and only if its epic is open, and both live tombstones pointed at DONE epics.

**Why the clause states a STATE invariant and not only a rule about the archival event.** The mechanical backstop that now ships for this ban (`plan_thread_no_tombstone` in `livespec-dev-tooling`) fails on any topic present at BOTH `plan/<topic>/` and `plan/archive/<topic>/`, unconditionally: it is a set intersection of directory names, fail-closed, with no opt-in lever and no content read. It therefore cannot distinguish a tombstone from a NEW thread that reuses a retired topic's slug while the old archive remains. A specification that sanctioned slug reuse would put every governed repo permanently red in `just check` with no sanctioned green path — the only escapes being deleting archived history or renaming the new thread, neither of which any clause authorizes. The prose is the side that must move: the structural detector was chosen deliberately over content sniffing, which is evadable by rewording and false-positives on any document that quotes the banned phrase, and slug reuse is independently broken by the layout anyway, since the reused slug's own next archival collides with the occupied archive slot. So the clause bans the STATE and says plainly that a retired slug is not reused while its archive remains.

That in turn settles what the ACTIVE-plan-wins precedence beside it is for. It is daemon ROBUSTNESS — the daemon reads a working tree, which can transiently hold a both-present pair (a lagging primary checkout, a mid-operation tree, an adopter with no gate wired), and in that state an active plan must not be garbage-collected out from under itself. It is not a licence to create the pair deliberately. Adversarial-review blocker B6 remains satisfied on that reading.

Two alternatives were considered and rejected, and the clause is shaped to avoid both. Making the archived-or-deleted test file-level rather than directory-level was rejected: its directory-first precedence is exactly the robustness just described. Relaxing the non-interference invariant so the daemon may stat inside `plan/` was rejected: that invariant is correct, and the fix belongs on the archival side.

### Proposed Changes

In `spec.md` §"Track discovery and the mapping store", insert the following after the paragraph describing garbage collection. The blockquoted text below is the clause verbatim (quote markers stripped when landed); nothing else in this proposal is to be landed.

> Whoever archives a plan thread MUST leave NOTHING at its live path
> `plan/<topic>/`. A stub, a terminal marker, a forwarding note, or any other
> residue there is FORBIDDEN, and the directory itself MUST NOT remain, even
> empty. Archival MUST relocate the directory whole, leaving nothing behind.
>
> Stated as a state invariant rather than only as a rule about the archival
> event: in no committed tree, from this clause's ratification forward, may the
> same topic exist at BOTH `plan/<topic>/` and `plan/archive/<topic>/`. A
> retired topic's slug is therefore NOT reused for a new thread while its
> archive remains — choose a new slug; or, if the new work genuinely continues
> the old thread, REOPEN ITS EPIC, which unarchives the thread by moving it
> back. Moving an archived thread back WITHOUT reopening its epic is
> forbidden: it produces a live directory whose epic is closed, which is the
> tombstone condition wearing a different name.
>
> This prohibition is load-bearing because of how discovery works. The
> archived-or-deleted test keys on the DIRECTORY alone, and discovery
> enumerates directories (the one bounded existence probe stated above
> notwithstanding). The live directory's continued existence — including via a
> symlink to a directory — makes an archived thread read as ACTIVE, so its
> mapping row is never garbage-collected and the finished thread remains
> eligible for nudges, for wrap-up injection, and for RESTART.
>
> The daemon reads each watched checkout's WORKING TREE, not a commit, so
> untracked residue under `plan/<topic>/` keeps the directory alive even after
> a clean archive has merged. Removing the tracked files is not sufficient;
> the directory must be gone from the tree the daemon actually reads.
>
> When a plan thread would close with anything unresolved, exactly ONE of two
> dispositions is sanctioned. Either the thread is LEFT UN-ARCHIVED — its epic
> staying OPEN — until its blockers are resolved; or ALL of its blockers are
> TRANSFERRED to a different or new NON-ARCHIVED plan thread and/or work-item,
> after which the thread is archived whole. Archiving it and leaving a note
> saying what is left is not a third option.
>
> The precedence by which an ACTIVE plan wins over a same-named archived copy
> is daemon ROBUSTNESS — it keeps a live thread from being garbage-collected
> in a working tree that transiently holds both, such as a lagging checkout or
> a mid-operation tree — and NOT a sanction of the both-present pair as a
> durable state. The protection against mistaking a transiently-unreachable
> repository root for a deleted plan is likewise unaffected.

The clause adds no new `## ` heading and renames none, so `tests/heading-coverage.json` is unaffected.
