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

**All three spec changes are RATIFIED:** `livespec-zp5mkd` (core, v194),
`overseer-ihwyin` (this repo, v008), `bd-ib-xhcqbc` (orchestrator, v057, carrying the
`prose/plan.md` co-edit). The ban is now written into the guidance every adopter
inherits, into this repo's own discovery contract, and into the operation prose an agent
reads at archive time.

**`livespec-fvhvui` is GROOMED** into nine measured per-repo slices, each filed in its
OWN tenant. The index is in that epic's notes. One has landed
(`livespec-driver-codex-g5a`).

## The fan-out slices were filed WITHOUT INTAKE — measured 2026-08-04 ~17:00

This arrived as a cross-track receipt from `governed-repo-bootstrap` about ONE slice,
and re-measuring turned it into a class. **The `/groom` pass that cut
`livespec-fvhvui` into nine slices filed them with `metadata = null` (so no rank) and
without `intake:triaged`.** Audited across all nine tenants:

| slice | tenant | status | rank | `intake:triaged` |
|---|---|---|---|---|
| `dolt-server-d8w` | dolt-server | **ready** | **a1** | **yes** — repaired, see below |
| `bd-gj-9tf` | orchestrator-git-jsonl | backlog | — | **no** |
| `bd-ib-ud0y` | orchestrator-beads-fabro | backlog | — | **no** |
| `livespec-console-beads-fabro-0c5` | console-beads-fabro | backlog | — | **no** |
| `livespec-driver-claude-zbw` | driver-claude | backlog | — | **no** |
| `livespec-rh2y` | livespec | backlog | — | **no** |
| `livespec-runtime-acq` | runtime | **ready** | — | **no** |
| `overseer-2i9` | overseer | backlog | — | **no** |
| `livespec-driver-codex-g5a` | driver-codex | closed | — | no (closed) |

**Seven open slices still carry the defect.** Note `livespec-runtime-acq` is already
`ready` with no rank at all — so a ranked drain cannot order it against its siblings.

**Why this is worth a section rather than a shrug.** Nothing in this thread noticed;
it surfaced only because `governed-repo-bootstrap` ran a ledger-rank probe (its B5
acceptance) and tripped over `dolt-server-d8w`. A defect that is invisible until an
unrelated track happens to assert on it will be found one slice at a time, by
whichever track pays for it. Repair the remaining seven deliberately.

**`dolt-server-d8w` is REPAIRED** — intake DoR run and applied 2026-08-04 ~16:55:
`metadata.rank = a1` (a FREE slot between the `a0` bootstrap cluster and
`dolt-server-wgy` at `a3`, so **no sibling rank moved** and no tenant-wide migrate or
rebalance was run), `intake:triaged` added, status routed `backlog` → **`ready`**, and
the full DoR record appended to its notes. Read-back over all ten tenant rows confirms
nothing else changed.

**Do NOT bulk-apply this to the other seven.** The `d8w` DoR was worth running because
it CORRECTED THE ITEM, and only a per-repo measurement finds that class of error:

- Its stated blocker had already cleared — `dolt-server` PR #42 ("bump the dev-tooling
  pin to v1.19.0 and wire the tombstone check") is MERGED. That is what made `ready`
  the honest routing rather than leaving it in `backlog`.
- **Its central premise was wrong in the dangerous direction.** The item says one
  handoff has "no anchor" and advises FILING an epic if a thread genuinely lacks one.
  Measured: `plan/governed-repo-bootstrap/handoff.md:4` already declares a concrete,
  resolving epic — "The ledger status anchor is epic `dolt-server-3ychlx`" — and that
  epic exists. It is invisible to `plan_thread_anchor_declared` only because it is
  written as PROSE instead of the literal bold `Ledger anchor:` form the extraction
  regex requires. **The repair is a one-line reformat**; following the item's own
  advice would have filed a duplicate epic. Same trap already recorded in this repo's
  `.claude/CLAUDE.md`.

Each slice's description came from the same forge-API scan, so **expect the same
prose-vs-literal confusion in the other seven** — a repo reported as "anchorless" may
have a perfectly good anchor written the wrong way. Re-measure locally per repo before
repairing, exactly as each slice already tells you to.

Incidental, for whoever mutates that tenant next: `bd` printed
`Warning: auto-backup failed: … command denied to user 'dolt-server'@'%'`. The write
succeeded and verified on read-back, but that tenant's backup credential is failing.
Not this thread's to fix.

## All three are RATIFIED — and this section previously said the opposite

`livespec` **v194** (MERGED), `livespec-overseer` **v008** (MERGED), and
`livespec-orchestrator-beads-fabro` **v057** — the last carrying the `prose/plan.md`
co-edit via `resulting_files[]`. Doctor static is 21 findings / 0 non-pass in each.

**RESOLVED 2026-08-04 ~17:00 — PR #1302 MERGED** at `2026-08-04T16:33:59Z`
("chore(spec): revise — ratify the plan-thread tombstone ban (v057)"). The
"first thing on resume" question this section used to pose is **answered and
discharged**: ratification is complete in all three trees, and next-action item 0
below needs nothing further.

**BUT THE LEDGER DOES NOT AGREE, and the close depends on it.** Re-measured the same
minute, all three items still read **`blocked`** with `blocked-reason:needs-human`:

| item | tenant | spec revision | ledger status |
|---|---|---|---|
| `livespec-zp5mkd` | livespec | v194 merged | **`blocked`** |
| `overseer-ihwyin` | overseer | v008 merged | **`blocked`** |
| `bd-ib-xhcqbc` | orchestrator | v057 merged (PR #1302) | **`blocked`** |

The work is DONE and the records say it is not. §"Closing this thread" requires that
every child be closed or transferred before this thread archives, so these three
stale rows are a hard blocker on the close — and worse, anything reading the ledger
rather than this file will conclude the spec work is still pending and may re-do it.
**Close them against their merged revisions.** They are human-gated `spec-change`
items, so that is a maintainer action, not a factory dispatch.

### Two rendering defects the byte-level review caught — expect this class again

Neither came from the clause. Both came from RENDERING it into a target file, and
neither was visible by reading:

- **A line-wrap split the `capture-work-item` code span.** `textwrap` breaks on hyphens
  by default, and CommonMark renders a newline INSIDE a code span as a SPACE — so the
  ratified contract would have named the operation "capture- work-item", and a
  single-line grep for the real token would have missed it. Fix: `break_on_hyphens=False`
  plus an assertion that no inserted line carries an ODD backtick count. Note the file's
  PRE-EXISTING multi-line spans (`` `bd` `` / `` `update` ``) are fine — there the
  rendered space is correct because the text is two words.
- **The prose rendering dropped a CONDITIONAL.** The contract permits epic-reopening only
  "if the new work genuinely continues the old thread"; the operative-voice prose offered
  it flat. Since an agent reads the prose and not `contracts.md`, that would have handed
  anyone wanting a retired slug a sanctioned way to resurrect a finished thread to steal
  it. A rendering into a different voice is a REWRITE — diff it against the clause
  claim-by-claim, not by eye.

### `reviewed_at` must name the review that saw the FINAL bytes

`ratification_evidence.content_digest` binds the reviewer's verdict to the proposal AND
the exact resulting-file bytes, so the timestamp beside it must come from the review that
saw THOSE bytes. A byte-level review can only ever post-date the bytes it checks, so the
order is **build → review the built bytes → capture that timestamp → run revise**.

v194 and v008 each recorded a timestamp ONE ROUND EARLY — naming the review that cleared
the PROPOSAL rather than the landed file. The substance was verified sound both times
(independently and by the reviewer), but the trail was imprecise; both merged before it
was noticed, so the correction is recorded as a comment on each PR naming the review that
does cover the merged bytes. **v057 was done in the correct order**, and before running
its pass the rebuild was asserted BYTE-IDENTICAL to the reviewed commit — without that
assertion, "redo with the new timestamp" silently risks landing different bytes under a
verdict that saw the old ones, which is the same error one layer up.

**An earlier revision of this handoff said ratification was blocked and declined it on
principle. That was WRONG, and the error is a shape worth remembering.** I had read
SKILL.md's INTERACTIVE PROSE — its Step 3 enumerate-all / Step 5 decide-each walkthrough
— and concluded the tooling forces an accept/modify/reject on every pending proposal, so
ratifying ours meant disposing of a sibling thread's in-flight work. Then I verified the
wrapper instead of the walkthrough:

- `revise.py` and its helpers never `glob` / `iterdir` / `listdir` `proposed_changes/`.
  The payload is the wrapper's entire universe.
- `_validate_proposal_topics_exist` checks only that topics NAMED IN THE PAYLOAD resolve
  to files. It never checks the reverse, and its own docstring treats a partial pass as
  the expected case ("the topic was already processed in a prior revise pass").
- `revise_input.schema.json` sets `decisions.minItems: 1` — a floor, not a completeness
  requirement.
- No doctor static check requires full-directory coverage;
  `proposed_changes_and_history_dirs` only asserts both directories EXIST.

So a payload naming ONE topic is the wrapper's ordinary contract. It is categorically
different from the file-shuffling this section used to weigh: nothing reads, moves or
disposes of the sibling proposal — it simply is not in the payload. Confirmed
empirically in all three repos: after each pass the other threads' proposals are
byte-identical and still pending.

**A DOCUMENTED UX PROCEDURE IS NOT AN ENFORCED GATE.** Read the wrapper before
concluding the tooling forbids something. That is the same discipline this thread
applied to everything else and I failed to apply here.

### The ratification evidence is cryptographically bound — three things that cost a cycle each

`ratification_evidence.content_digest` is NOT a hash of the proposal. It is sha256 over
uint64-BE length-prefixed proposal bytes, then each `resulting_files[]` entry's
length-prefixed path and content, sorted by path. The reviewer's verdict is therefore
bound to the proposal AND THE EXACT FINAL BYTES.

That is a good design and it caught a real defect in this very pass. A third review
comparing LANDED BYTES against the cleared clause found four words of framing I had
silently reintroduced while re-flowing prose into the target file's house style — words
a previous round had asked be deleted. No normative shift, but it contradicted the
proposal's own "nothing else is to be landed" instruction. **Patching the active file
was not an option**: the `vNNN` snapshot and the recorded digest would then describe
bytes that no longer exist. The pass was redone from master so the digest covers what
actually lands. If you ever need to amend a ratified clause, redo the pass; do not edit
the active file.

Two smaller constraints: `reviewer_identity` MUST EQUAL `reviewer_model`, and that value
must match `ratification_reviewer_model` in `.livespec.jsonc` where the key is present
(`livespec` sets `fable`; `livespec-overseer` does not set it, so the model check is
skipped but the identity/model equality still applies).

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
| `overseer-ihwyin` | overseer | **RATIFIED** (v008) | the ban into this repo's `spec.md` |
| `livespec-zp5mkd` | livespec | **RATIFIED** (v194) | the ban into core's Planning Lane guidance |
| `bd-ib-xhcqbc` | orchestrator | **RATIFIED** (v057) | the realization spec + `prose/plan.md` Step 5 |
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
- **Moving a sibling proposal aside to ratify ours alone.** Still rejected — but note
  the SANCTIONED route is a scoped `--revise-json` payload naming only your topic, which
  touches nothing else. See §"All three are RATIFIED".

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

0. ~~**Check PR #1302**~~ — **DONE 2026-08-04 ~17:00. It MERGED** at
   `2026-08-04T16:33:59Z`. Ratification is complete in all three trees. Nothing further
   here. **But see §"All three are RATIFIED": all three items still read `blocked` in
   their ledgers and must be CLOSED against their merged revisions** — a maintainer
   action, and a hard blocker on this thread's own close.
1. **`overseer-jct`** — clear the 123 result-typed violations. Nothing `.py` can land in
   this repo until it is done, including `overseer-e723tt`. Expect it to need grooming
   into per-module slices; the `overseer-bg2` precedent is cited on the item.
2. **`livespec-fvhvui`'s remaining eight slices**, cheapest first, measuring repo health
   before scheduling each. **Run an intake DoR on each before scheduling it** — seven of
   the eight still have `metadata = null` (no rank) and no `intake:triaged`, and one
   (`livespec-runtime-acq`) is already `ready` with no rank, so a ranked drain cannot
   order it. `dolt-server-d8w` is done and is the worked example; see §"The fan-out
   slices were filed WITHOUT INTAKE", including why its DoR corrected the item and why
   you should expect the same prose-vs-literal anchor confusion in the others.
   **This epic is MORE load-bearing than it looks.** The ban's
   new "never move an archived thread back without reopening its epic" MUST is correct
   but UNENFORCED — no credential-free check can see epic state, so it leans on
   `plan_thread_epic_parity`, which is armed-only and dark in 11 of 12 repos. Its
   tenant-prefix bug is fixed (`livespec-dev-tooling-q6oob4`, merged `e81cde7`), so
   arming it per repo is exactly what these slices do. Until then that MUST is prose
   only.
3. **`livespec-akg7k5`** is what stands between core and enforcement. Not this thread's
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
Its epic has open children — a hard blocker in `overseer-jct` and a groomed fan-out epic
with eight slices left. The rule says: leave the
plan un-archived until its blockers are resolved, or transfer them all first. It is not
finished, so it is not archived.

When it does close, either every child is closed or the survivors are transferred to a
live thread or work-item first. Then
`git mv plan/kill-tombstones plan/archive/kill-tombstones` — whole directory, nothing
left behind, and the epic CLOSED in the same motion so the lifecycle binding holds.
**If you find yourself wanting to leave a note at the live path, that is the exact
impulse this thread exists to forbid** — and as of v1.19.0,
`check-plan-thread-no-tombstone` will fail your build if you try.
