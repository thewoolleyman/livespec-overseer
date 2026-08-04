# Plan — kill-tombstones

**Owning repo:** `livespec-overseer`. **Ledger anchor:** epic **`overseer-7zhfdr`**
(this repo's beads tenant). Opened 2026-08-04 on a maintainer declaration that the
tombstone convention is broken and is retired fleet-wide.

**Status is not stored here.** Read it from the ledger. `bd` needs the fleet
credential wrapper in this tenant — a bare `bd` returns `Access denied`:

```bash
/data/projects/1password-env-wrapper/with-livespec-env.sh \
  bd -C /data/projects/livespec-overseer show overseer-7zhfdr --json
```

Pass **`--limit 0`** to any `bd list`: the default caps at 50 rows and hides the
rest behind a footer line, which already cost this thread one wrong "it did not
file" conclusion. Each sibling repo's items are in ITS OWN tenant — run `bd` with
`-C <that repo>`, or the id will not be found.

## Read first

1. `plan/kill-tombstones/research/mechanism.md` — what a tombstone is, the four
   things wrong with it, the measured daemon-log evidence, and the removal
   procedure with its trap.
2. `plan/kill-tombstones/research/enforcement-inventory.md` — the gates that
   already exist, why neither fired, the missing detector, and where the
   prohibition gets written down. **Both files predate the 2026-08-04 execution
   session recorded below; where they disagree with §"What is DONE", the ledger
   and this file win.**

Everything below is a claim with a timestamp, including this sentence. Re-measure.

## The rule this thread exists to install

A **tombstone** is a stub `handoff.md` left at the LIVE path
`plan/<topic>/handoff.md` after the real thread moved to `plan/archive/<topic>/`,
whose body says "STOP. THIS TRACK IS COMPLETE AND ARCHIVED".

**Maintainer-declared 2026-08-04: it is FORBIDDEN, permanently, in every fleet
member and every adopter.** When a plan thread would close with anything
unresolved, do exactly ONE of:

1. **LEAVE THE PLAN UN-ARCHIVED** — its epic staying OPEN — until its blockers
   are resolved; or
2. **TRANSFER ALL BLOCKERS** to a different or new NON-ARCHIVED plan thread
   and/or work-item, then archive with a clean whole-directory
   `git mv plan/<topic> plan/archive/<topic>` that leaves NOTHING behind.

**The rule is a STATE invariant, not only a rule about the archival event.** In no
committed tree may the same topic exist at both `plan/<topic>/` and
`plan/archive/<topic>/`. A retired slug is therefore NOT reused for a new thread
while its archive remains — choose a new slug, or reopen the old epic, which
unarchives the thread by moving it back. Moving a thread back WITHOUT reopening its
epic is forbidden: it produces a live directory whose epic is closed, which is the
tombstone condition wearing a different name. **That sharpening came from
adversarial review and is the most important correction of the session — see
§"What review caught".**

## Why, in one paragraph

A tombstone keeps a finished thread registered as a live overseer track, and it
DEFEATS the daemon's own cleanup: `registry.archived_or_gone` is DIRECTORY-level
and a live `plan/<topic>/` wins, so `_supervisor_discovery.archive_gc` can never
drop the row. The workaround disarms the mechanism that makes it unnecessary.
Measured cost, from `tmp/overseer/daemon.log`: `daemon-liveness-truth` was
**RESTARTED 1h02m after its archive merged**, and `fleet-charter-remediation` was
**RESTARTED 4h19m after**, then nudged again **14h10m after** it was finished.

## What is DONE — measured 2026-08-04, re-measure before relying on it

**The mechanical ban SHIPPED and is ENFORCED.**
`livespec_dev_tooling/checks/plan_thread_no_tombstone.py` fails any topic present at
both `plan/<topic>/` and `plan/archive/<topic>/`. Structural (a directory-name
intersection — it reads no handoff text), fail-closed, **no opt-in lever**. Released
in `livespec-dev-tooling` **v1.19.0**.

Enforced on master in **9 of the 10** pin-consuming fleet repos: `livespec-dev-tooling`,
`livespec-orchestrator-beads-fabro`, `livespec-orchestrator-git-jsonl`,
`livespec-driver-claude`, `livespec-driver-codex`, `livespec-runtime`,
`livespec-console-beads-fabro`, `dolt-server`, and **`livespec-overseer`** — the repo
that wrote both tombstones, where the check now runs and PASSES. Its freedom from
tombstones is confirmed BY THE GATE, not by inspection.

Four of those needed hand work, because the automated lane did not carry the check all
the way: `livespec-driver-codex` and `livespec-runtime` got the pin but not the wiring;
`livespec-console-beads-fabro` has no `check-aggregate-completeness` gate at all, so a
new canonical check never arrives on its own; `dolt-server` was dropped by the release
dispatch preflight AND has no gate, so it needed a pin bump and wiring together.

**Only `livespec` core is not yet enforcing**, blocked by 36 pre-existing
`check-shell-quality` violations in its own justfile recipes. That is
`livespec-akg7k5`'s work, not this thread's; the coupling and one cheap fix pattern are
recorded on that item.

**Closed children:** `overseer-5nuir3` (the purge — satisfied by another route; see the
trap below), `overseer-3i43qx` (the `overseer-y26` description repair, done host-side),
`livespec-dev-tooling-rowxc6` (the check), `livespec-dev-tooling-q6oob4` (the
epic-parity tenant-prefix bug, merged `e81cde7`).

**Three spec proposals are MERGED and REVIEWED, awaiting ratification only:**
`overseer-ihwyin`, `livespec-zp5mkd`, `bd-ib-xhcqbc`. Each sits at
`SPECIFICATION/proposed_changes/plan-thread-tombstone-ban.md` in its repo.

**`livespec-fvhvui` is GROOMED** into nine measured per-repo slices, each filed in its
OWN tenant. The index is in that epic's notes. One has landed
(`livespec-driver-codex-g5a`).

## Why nothing is ratified yet — a decision, not an oversight

`/livespec:revise` enumerates EVERY pending file in `proposed_changes/` and forces an
accept / modify / reject decision on each. **There is no defer.** All three target
repos also hold ANOTHER thread's in-flight proposal —
`codex-yolo-structured-question-protocol.md` here,
`drift-acceptance-consensus-carveout.md` in the orchestrator (whose owning thread had an
open PR mid-drafting at the time), and the drift-acceptance proposal in core.

Ratifying ours therefore means disposing of theirs: accepting spec text this thread did
not write and whose thread has not finished it, or rejecting live work.

Moving the sibling file aside, revising, and restoring it works mechanically and was
DECLINED ON PRINCIPLE. This is the thread whose whole subject is that a clever
workaround which disarms a mechanism is worse than the condition it papers over; doing
exactly that to its own ratification would be the same error in a mirror. **Do not
reach for it later either.** Ratify when a revise pass can legitimately dispose of
everything pending in that tree.

## What review caught — read before editing any of the three proposals

Each proposal was adversarially reviewed twice by an independently-spawned Fable-model
agent. The reviews were not a formality; the second round found defects in the fix for
the first.

**Round 1 — found INDEPENDENTLY by two reviewers on two different proposals.** The
drafts stated an ARCHIVAL-EVENT rule while the shipped check enforces a STATE
invariant. An event-only rule PERMITS a new thread reusing a retired slug while the old
archive remains — a directory created later is not something that "remains" — and the
check hard-fails that pair unconditionally, its remediation telling the adopter to
delete retained history. A repo doing what the spec sanctioned would have been
permanently CI-red with no sanctioned green path. Both reviewers ruled the PROSE wrong,
not the check.

**Round 2 — the fix's own escape hatch licensed the harm.** "…or unarchive the old
thread by moving it back", unqualified, sanctions a move-back with the epic still
CLOSED. The structural check passes live-only topics BY DESIGN, and
`plan_thread_epic_parity` is dark in 11 of 12 repos, so nothing catches it. Now bound to
reopening the epic.

**Round 2 also caught a CROSS-TREE CONTAMINATION — remember this as a general hazard.**
The orchestrator reviewer correctly said my enumeration of living homes THERE was
incomplete, because that tree's `contracts.md:1007` sanctions "a dedicated top-level
topic directory (precedent: `loop-reflection-gate/`)". I applied that correction to the
CORE document too, where it is sanctioned nowhere and where `nfr:186` explicitly forbids
the neighbourhood. **Applying one reviewer's correction to a sibling document is how a
widening gets smuggled in wearing a reviewer's authority.** Verified both trees
directly; retained in the orchestrator proposal, deleted from core's.

## The scope, with CURRENT status — re-read each item's own text

| id | repo | status | what |
|---|---|---|---|
| `overseer-5nuir3` | overseer | **closed** | purge the last tombstone + verify |
| `overseer-3i43qx` | overseer | **closed** | strike remedy 1 from `overseer-y26` |
| `livespec-dev-tooling-rowxc6` | dev-tooling | **closed** | the `plan_thread_no_tombstone` check |
| `livespec-dev-tooling-q6oob4` | dev-tooling | **closed** | `plan_thread_epic_parity` tenant prefix |
| `overseer-ihwyin` | overseer | proposed, awaiting revise | the ban into this repo's `spec.md` |
| `livespec-zp5mkd` | livespec | proposed, awaiting revise | the ban into core's Planning Lane guidance |
| `bd-ib-xhcqbc` | orchestrator | proposed, awaiting revise | the realization spec + `prose/plan.md` Step 5 |
| `overseer-e723tt` | overseer | **BLOCKED** on `overseer-jct` | re-derive the `_prefer_archived` tiebreak |
| `livespec-fvhvui` | livespec | groomed, 1 of 9 slices landed | fleet fan-out of `plan_lifecycle_anchor` |

Related, already filed, NOT duplicated: **`overseer-y26`** is the root-cause bug. Its
description was repaired by `overseer-3i43qx` and no longer recommends a stub anywhere.

## Defects this thread found and filed — none of them are its own work

Filing them was the deliverable; fixing them is not this thread's scope.

| id | repo | what |
|---|---|---|
| `overseer-jct` | overseer | **123 `check-public-api-result-typed` violations block EVERY `.py` push here.** Blocks `overseer-e723tt`. |
| `livespec-dev-tooling-ozuv` | dev-tooling | A release that WIDENS a check reaches consumers as a zero-`.py` pin bump, so the widened check never runs on the adopting PR. |
| `livespec-dev-tooling-739o` | dev-tooling | A canonical check does not reach the fleet: 5 of 13 members have no aggregate gate, 3 cannot consume dev-tooling at all. |
| `livespec-dev-tooling-ov9o` | dev-tooling | `worktree-create` copies the pack from the PRIMARY checkout, so every worktree made across a pin bump is born failing byte-verification. |
| `livespec-dev-tooling-teje` | dev-tooling | `worktree-reap` judges merged-ness by ancestry — false for EVERY branch under rebase-merge. 17 worktrees, 0 removable. |
| `livespec-dev-tooling-3pre` | dev-tooling | `worktree_primary_path` SIGPIPEs under `pipefail`; `just worktree-create` dies silently with exit 141 in any repo with enough worktrees. |
| `livespec-dev-tooling-i655` | dev-tooling | `subagent_stop_guard` resolves the PR by local branch name, wedging on a rebase-merged branch pushed under a different name. |

**`overseer-jct` deserves reading in full before anyone touches `.py` here.** The 123
violations are NOT new code and NOT a regression. Controlled measurement, identical
Python sources: **0 violations under pin v1.18.0, 123 under v1.19.1.** The check's
UNIVERSE widened — v1.19 removed its `pure_trees` role-absence gate — so this repo had
been passing VACUOUSLY, scanning essentially nothing. The violations were always there.

## Explicitly rejected — do not propose these again

- **Making `registry.archived_or_gone` file-level.** Its directory-first precedence is
  adversarial-review blocker **B6**. Reviewers confirmed it survives the ban as daemon
  ROBUSTNESS for transient working-tree states (a lagging checkout, a mid-operation
  tree) — it is not a sanction of the both-present pair as a durable state.
- **Relaxing architecture invariant 1** so the daemon may stat `plan/`. The invariant is
  correct; the fix belongs on the archival side or in a store-side check.
- **Hand-editing `~/.livespec-overseer.jsonl`** to pre-empt the GC. It is shared fleet
  state read by every track.
- **A content-sniffing detector** that greps a live handoff for "COMPLETE AND ARCHIVED".
  Evadable by rewording, and it false-positives on any document that legitimately quotes
  the phrase — including this thread's own research notes. Detect the STRUCTURE.
- **Removing the ARMED-ONLY gating on `plan_thread_epic_parity`.** Deliberate and
  correct; it just means parity can never be the primary guard.
- **Narrowing `plan_thread_no_tombstone`** so it distinguishes a stub from a retired-slug
  reuse. Structurally impossible without content sniffing. The prose moved instead.
- **Moving a sibling proposal aside to ratify ours alone.** See §"Why nothing is
  ratified yet".

## Traps that have already cost turns — all measured, none hypothetical

**`plan/foreman/` IS A LIVE THREAD, NOT A TOMBSTONE.** The stub was removed at
`c80aa52` and the thread REOPENED at `a10e00a`. `overseer-5nuir3`'s stated acceptance
("`plan/foreman/` absent from the primary checkout") would have DESTROYED live work — it
was closed as satisfied-by-another-route instead. **A stale acceptance criterion is more
dangerous than a stale status.**

**A THIRD dispatch-failure shape, distinct from the two in CLAUDE.md.** An anchor filed
as a cross-repo `depends_on` produces `drive.py` exit 1, dispatcher exit 3,
`ERROR: requested work-item(s) not in the ready set`, and **no fabro run at all** — so
unlike the `{{...}}` trap it leaves NO phantom claim. All five out-of-repo children of
this epic carried `non_local_depends_on` pointing at their own parent epic, which the
ranker reads as a BLOCKING dependency; an epic cannot close before its children, so the
hold was circular. It was also unresolvable regardless of status, because the consuming
repos' `cross_repo_targets` manifests lack a `livespec-overseer` entry and an
unresolvable sibling FAILS CLOSED. **Thread membership belongs in the item TEXT, never
in a dependency edge.**

**A LEDGER-EDIT item cannot be factory-dispatched.** `overseer-3i43qx`'s deliverable was
rewriting another item's description in beads. The fabro sandbox has no `bd`, no
`BEADS_DOLT_PASSWORD` and no `.beads/` by design, and forbids creating one — so no
sandboxed agent can ever satisfy it. It cost one run and left a blocked run holding a
claim. Tier such items supervisor/host.

**A RED MASTER BLOCKS EVERY DISPATCH IN A REPO.** The Dispatcher refuses with
`latest master CI is not proven green at required check ci-green` before any sandbox
work. This repo's master was red for hours because
`plan/ready-certification-deadlock/`'s charter bound `ledger_anchor = overseer-er6ikw`
while its handoff declared that id only as prose — the gate's regex requires the literal
"ledger anchor" phrase before the backticked id. One line fixed it (PR #693). **Check
master health before scheduling any dispatch.**

**A SLICE CAN BE GREEN ON ITS OWN ACCEPTANCE AND STILL UNDISPATCHABLE.** The
`livespec-runtime` fan-out slice was measured compliant, and its agent did the work
correctly — then could not push, because that repo's master is red and it carries
pre-existing violations outside the slice's scope. Measure REPO HEALTH, not just the
slice's own precondition.

**`bd update --notes` is SET, not APPEND.** Use `--append-notes`, which exists. Read
back after writing either way.

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never a commit on the primary checkout.
Never `--no-verify`; halt and report on hook failure. Never touch another session's
worktrees or branches. Never kill the acting overseer daemon in tmux
`livespec-overseer:1.1`. Resolve a repo's default branch from the forge
(`gh repo view --json defaultBranchRef`) — `homelab` is `main`, not `master`.

**Create worktrees with `just worktree-create <branch> [base_ref]`** — but in THIS repo
that recipe is currently DEAD (`livespec-dev-tooling-3pre`: it exits 141 silently once a
repo has enough worktrees; this one has 123). The documented rescue is
`git worktree add` followed by `just install-worktree-pack` INSIDE the new worktree,
then discard the `worktree_discipline` key it writes into the tracked `.livespec.jsonc`.
**Run `install-worktree-pack` in any worktree created across a pin bump** — otherwise
the pack copied from the primary is stale and reddens `check-shell-quality` and
`check-baseline` with errors that name the consumer's justfile, not the pack
(`livespec-dev-tooling-ov9o`).

## Next action

Re-measure `overseer-7zhfdr` and its children from the ledger first — everything above
is a claim with a timestamp.

Then, in rough order of value:

1. **`overseer-jct`** — clear the 123 result-typed violations. Nothing `.py` can land in
   this repo until it is done, including `overseer-e723tt`. Expect it to need grooming
   into per-module slices; the `overseer-bg2` precedent is cited on the item.
2. **Ratify the three spec proposals** once each tree's other pending proposals can be
   legitimately disposed of in the same revise pass.
3. **`livespec-fvhvui`'s remaining eight slices**, cheapest first, measuring repo health
   before scheduling each.
4. **`livespec-akg7k5`** is what stands between core and enforcement. Not this thread's
   work, but it is this thread's last unenforced repo.

**Implementation route is the FACTORY PATH** — the Dispatcher drain, or an operator
running `/livespec-orchestrator-beads-fabro:drive --action impl:<id>`. Do NOT hand-code
factory items in a planning session. The exceptions this session made were deliberate
and each is recorded on its item: a ledger-edit item the sandbox cannot perform, and
CI-wiring pushed onto PRs a factory run had already opened.

Before dispatching anything, confirm the item's text carries no literal double-brace
interpolation token, and confirm the target repo's master CI is green. `fabro ps` is the
evidence of a run; a `drive.py` exit of 0 means the request was accepted, not that work
started.

## Closing this thread

**This thread stays UN-ARCHIVED, and that is disposition 1 of its own rule, working.**
Its epic has open children — a hard blocker in `overseer-jct`, three unratified spec
changes, and a groomed fan-out epic with eight slices left. The rule says: leave the
plan un-archived until its blockers are resolved, or transfer them all first. It is not
finished, so it is not archived.

When it does close, either every child is closed or the survivors are transferred to a
live thread or work-item first. Then
`git mv plan/kill-tombstones plan/archive/kill-tombstones` — whole directory, nothing
left behind, and the epic CLOSED in the same motion so the lifecycle binding holds.
**If you find yourself wanting to leave a note at the live path, that is the exact
impulse this thread exists to forbid** — and as of v1.19.0,
`check-plan-thread-no-tombstone` will fail your build if you try.
