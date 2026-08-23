# Completeness-review brief — epic `overseer-y3xhlh`

**For the reviewer commissioned under archive gate leg 2.** This file exists
because the epic's ledger record is roughly **305 KB across 69 append-only
comments**, and the handoff entries in it supersede one another — a linear read
is the enemy of a careful review, and most of what a linear read costs you is
retired state. This is a starting point, not a summary you should trust:
everything below was written by the OWNING thread and is **input to your review,
never evidence within it**.

Written 2026-08-22 by the owning plan session. Tally at writing: **17 of 17
children closed.** Gate 1 is satisfied on the count. The thread is **NOT ready
for archive** — see "What is not done".

## What you are certifying

The epic's acceptance names four legs and they govern; nothing here supersedes
them. Leg 2 is yours. The thread's SUBJECT, against which completeness is
judged, is its title: model the overseer track record as a **tagged union** so
that **an epic-less foreman seat is unrepresentable**.

Four axes are the right cut for a completeness question:

1. **The supported writer, and the sequencing that must not be inverted.**
   Before this thread, the only way to set a reserved seat's epic was an
   unsupported hand-edit of the JSONL store. The writer had to land BEFORE the
   schema tightened, or the sole existing write path would have become illegal
   with no replacement.
2. **The parse boundary.** A Valid-or-Invalid sum at the read side, so one
   malformed row cannot take down supervision fleet-wide, while the loader stays
   fail-soft.
3. **The variants and their call sites.** Four variants with a discriminator in
   the record, dispatched at the call sites, so the illegal state is
   unconstructible rather than merely unlikely.
4. **Durability and live verification.** Whether an epic written through the
   supported writer SURVIVES, and whether a real seat completes a
   ready-to-respawn cycle with no hand-edit.

## Where the substance lives, so you need not read the timeline

- **The scope-event comment of 2026-08-19** carries the cut, the requirement
  carriers (R1→.1, R2→.2, R3/R4→.3, R5→.4, R6→.5, R7→.6, no orphans), and the
  sequencing premise.
- **`overseer-hj7zp2`** is the root-cause carrier and holds the eight original
  acceptance criteria plus corrections to figures quoted in early handoffs. Read
  it before the children.
- **`plan/track-record-type-safety/research/measured-baseline.md`** is the
  pre-design measurement. Note its own §6 already warns that §§1–2 describe the
  PRE-MERGE tree.
- **`overseer-y3xhlh.6`'s closure comment** is the gating live verification —
  three real respawn cycles, a live daemon tick over 31 rows, epic survival
  across a full lifecycle. Its `close_reason` FIELD is empty; the evidence is in
  the comment. Do not read the empty field as an absent closure. Two sibling
  children are the same way.
- **`overseer-y3xhlh.8`** is the biggest finding after the cut and it changed
  what "done" means: `register_foreman_track` did an unconditional
  delete-and-recreate on every foreman step, destroying `epic`,
  `observed_session_identity` and `model_profile`. A supported writer alone does
  not make an epic durable if the next tick deletes it.
- **The latest handoff entry only.** Each supersedes the one before and says so
  in its first line. Older ones tell you what was believed at the time, which is
  occasionally interesting and never authoritative.

## Retired state a linear read will trip you on

Three separate handoffs flag "ONE ITEM NEEDS A HUMAN" — an unlanded `CLAUDE.md`
entry about item creation landing rows in `BACKLOG` outside the dispatcher's
ready set. **It landed.** It is the `CLAUDE.md` section headed "A `not in the
ready set` refusal with NO dependency edge at all — check the STATUS first". The
flag is resolved; the repetition is an artifact of append-only handoffs, not
three open items.

Early handoffs also quote a store of 25–26 rows, and one quotes "roughly 67".
Both are corrected within the record: 67 came from the daemon STATUS SNAPSHOT, a
joined view, not from the mapping store. The store held **45 rows** on
2026-08-22.

## What the owning thread did — and why it is not your evidence

This thread verified its own dispatched work rather than accepting green
verdicts. **The method is the part worth auditing, because if the method is weak
then so is everything it certified.** What it used, and what it learned not to
trust:

- **Exercise the predicate; do not read the diff.** Every fix this thread
  certified on 2026-08-22 was verified by importing the module from a detached
  worktree of `origin/master` and calling the function against constructed
  inputs, including a **discriminating control** proving a healthy input is NOT
  reported. A guard that flags everything is as useless as one that flags none.
- **Artifact, not ancestry.** An `is-ancestor` check returns TRUE for REVERTED
  work, because a revert adds a commit rather than removing history. This thread
  used ancestry in one earlier review and has recorded the correction; the
  discriminating read is whether the artifact the change created exists in the
  tree.
- **Forge queries need a window, not just a state filter.** Querying all states
  but with a row LIMIT reported a merged pull request as absent twice here, once
  missing it by two numbers.
- **Mergeability must be read per pull request.** The forge's list endpoint
  returns a CACHE for merge state; on an open request, "unknown" means
  uncomputed, never clean. This thread proposed a list-based sweep and had to
  withdraw it — the same query returned "zero conflicted" and then "two
  conflicted" minutes apart with no branch touched.
- **A ledger row read earlier is not the row now.** This thread published a
  four-row claims table measured at 12:24Z and acted on it at 13:36Z, after
  every row had changed, and had to retract a recommendation made to a peer.

Those five are one defect wearing different hats: an instrument answering about
a MOMENT or a SCOPE other than the one being acted in. If you find this thread's
certifications weak, that is the seam to press.

## What is not done

- **`overseer-nu7r` is at `acceptance`, not closed**, and the owning thread
  recorded a **4-of-5** AI pass against it. Criterion 5 required an explicit
  statement of whether a mechanical guard was added or deliberately declined;
  the docs-only change says neither. The owning thread declined to self-pass it.
- **Five live mapping rows are surfaced but NOT repaired** —
  `16-fleet-provisioning-usb`, `fleet-ci-runner-pool`,
  `livespec-dev-tooling-foreman`, `livespec-foreman`, and
  `rop-railway-enforcement`. Surfacing them was this thread's deliverable;
  repairing them is operator-tier and belongs to the seats owning those repos,
  who were notified directly. `fleet-ci-runner-pool` carries a `model_profile`
  that a remove-then-add repair would silently destroy.
- **`overseer-ow7c.5` is ARMED BUT NOT LIVE** — the guard treats IS-A-STRING as
  IS-VALID while both reader gates require a specific ISO shape, so a malformed
  string would be uncertifiable AND unrepairable. Zero live rows hold one today.
  Easy to conflate with the null and key-absent cases above; its live status
  differs.
- **This thread's live P1 sits under a DIFFERENT epic.** `overseer-v2vs` is
  parented to `overseer-ow7c`, so the 17-of-17 count does **not** cover it. Its
  surfacing half was reverted and re-landed on 2026-08-22; both halves are on
  master now.

## A caution about the count

17-of-17 is a property of the RECORD. This thread found three genuine defects in
its own merged work **after** the last child closed — `overseer-vg8m`,
`overseer-3w5w`, and the `overseer-nu7r` criterion-5 gap — and two of them were
P1. A completeness review that reads the tally and stops will miss exactly the
class of thing this thread kept finding in itself.
