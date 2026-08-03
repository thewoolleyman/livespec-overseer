# Plan — daemon-liveness-truth

Ledger anchor: `overseer-x29` (epic). Read status from the ledger, never from this
file — every claim below is dated, and a date is a claim with an expiry.

```bash
with-livespec-env.sh -- bd show overseer-x29
```

A bare `bd` returns `Access denied` here; the fleet credential wrapper is required.
`bd` also prints a benign `auto-backup failed: command denied` warning on every
call in this tenant (`overseer-n04`); the record still prints, so do not read it as
a failed measurement.

## What this thread is

The daemon's view of whether a track is alive disagreed with reality, in **both
directions**: a live, working, in-tmux track reported `session-gone`
(`overseer-j1r`), and a deliberately torn-down track stayed red forever
(`overseer-mkx`). One raised a false alarm about a session that was fine; the
other about a session that no longer existed. Both eroded the same thing — an
operator's ability to trust the display — and an operator who learns to discount
one will discount the other.

A third child was adopted from the archived `supervisor-prompt-quality` thread:
`overseer-oydugu`, the first executable gate on **rung 3** of the supervision
ladder (observed conduct). It sits here because all three are the system's MODEL
of what is happening diverging from what IS happening.

## STATE, MEASURED 2026-08-03 — three children closed, one open

| child | state | evidence |
|---|---|---|
| `overseer-j1r` | **closed** | PR #468, merged 2026-08-02T18:16Z |
| `overseer-mkx` | **closed** | PR #477 (`6b58092ef`), merged 2026-08-02T18:29Z |
| `overseer-oydugu` | **closed** | PR #521 (`8901e60`), merged 2026-08-02T23:56Z |
| `overseer-x29.1` | **OPEN — needs a maintainer decision** | filed 2026-08-03 |

Both daemon fixes are RELEASED in `v0.16.1` (cut 2026-08-02T23:55Z), in the
package and in the vendored `.claude-plugin/overseer/` copy.

**The epic cannot close until `overseer-x29.1` is decided, and that decision is
not a worker's.** Everything else on this thread is done. See "Next action".

## `overseer-j1r` — the root was NOT the one the epic hypothesised

The epic argued both children shared a root in the declaration vocabulary. For
`j1r` that is **wrong**, and the contrast is the finding.

A manually-started Claude AUTO-derives its registry name from the repo directory
(`livespec-overseer-01`, `"nameSource":"derived"`); a daemon-spawned one receives
`-n <topic>` explicitly. The daemon matched on topic equality in **two** places —
the identity gate (`overseer/_supervisor_observe.py`) and its `live-outside-tmux`
softener (`overseer/_supervisor_offer.py`) — so a derived name failed **both**,
and the row degraded straight past the informational status to `session-gone`,
the only red status. The softener could only soften cases that had already
matched by name, which are exactly the cases that did not need softening.

**`nameSource` is the discriminator, and finding it was the whole difficulty.** By
NAME alone, an auto-named track (`repo-01`) and a DIFFERENT topic's session
squatting in a reused window are indistinguishable — both merely differ from the
topic. Softening both would tell the operator to rename a window another live
track is using. Only the first carries `nameSource: derived`. **The identity gate
is UNTOUCHED** — the fix is a reporting softener, never an act gate.

## `overseer-mkx` — the fix corrected the item's own account

`mkx` claimed a torn-down track renders as *hung mid-wrap-up*. Measured: it does
not. `alert_non_responder` needs a LIVE pane at danger context, so a gone session
never reaches it. The real symptom was sharper — the track reported `session-gone`
and kept reporting it, because discovery keys on the plan DIRECTORY. It sat in
`NEEDS YOU` for **327 minutes**.

The discriminator was on disk and simply unread: a session that wound down
declared `winding-down` first; one that died working declared nothing. A gone
track holding that declaration now reports the non-red `wound-down`.

**THE TRADE, stated rather than hidden:** a session that declared `winding-down`
and then genuinely CRASHED now reads as an orderly wind-down. Given up
deliberately, to keep the alarm sharp for a track dying mid-work.

That trade is what `overseer-x29.1` exists to revisit.

## `overseer-oydugu` — rung 3, and the item's central premise was FALSE

The gate is `tests/prompts/test_picker_conduct_discriminates.py`. Before touching
it, read `plan/daemon-liveness-truth/research/rung-3-corpus-measurement.md`, which
records three findings that contradict the item as filed:

1. **Turn granularity cannot discriminate.** The turn holding the violation also
   holds two correct pickers raised 45 minutes earlier, so the obvious rule
   PASSES the one violation we have. The unit is the **stop message** — the last
   assistant message of a turn, the one that hands control back.
2. **The feared false positive does not exist.** The item and charter correction
   C20 both describe the answering turn as *"prose, question marks, no picker"*.
   Measured: the prose and the `AskUserQuestion` call share one `message.id` —
   one assistant message. The hazard was inferred from rendered text, never
   measured against the record.
3. **Recall is unmeasured and cannot be measured** from this corpus — exactly one
   true positive exists. Precision is 1/1 against ten true negatives.

Live Stop-hook wiring was deliberately left out: repo-wide wiring adds a
production seam and worker-pane blast radius beyond the item's fixture-based
acceptance, on n=1 evidence. Widening the detector's reach is a decision to be
made in writing when a new positive is recorded — not a regex loosened until
something passes.

Exercised once against a LIVE, out-of-corpus transcript before landing (this
thread's own working session, 774 records): 4 stop messages, 0 flagged. That is
not a recall measurement — it is evidence the detector runs on real transcript
shapes it was not fitted to, and does not cry wolf on one.

## THE ONE OPEN DECISION — `overseer-x29.1`

There is no token meaning *"complete, parked, nothing wanted, do not restart"*.
`overseer/signals.py` defines three a SESSION may declare (`ready`, `blocked`,
`winding-down`) plus one the DAEMON owns. A finishing session must pick a
least-bad lie: `ready` authorises an unwanted restart, `idle-with-context-left`
forges a daemon marker, `blocked` alerts forever, and `winding-down` was the
least-bad — which PR #477 has now made the CONVENTIONAL way to say "finished", a
load-bearing meaning `overseer/marker-protocol.md` never assigned it. Corroborate
cheaply: that document mentions `winding-down` six times and `wound-down` **zero**
times, so the contract and the daemon's behaviour genuinely disagree.

**Option 1 (a teardown path that clears the state file) is INSUFFICIENT ALONE, and
this was measured rather than assumed.** Clearing the file makes
`no_managed_pane_row` fall through to the red `session-gone` — the very alarm the
teardown was meant to silence. So it cannot be the whole answer, and the question
is NOT a plain "option 1 or option 3".

**Option 3 (add a terminal `complete` token) is semantically right and carries a
fleet transition hazard.** It restores the crash-vs-completion distinction only if
gone+`winding-down` goes red again — and until every supervised session's charter
instructs it to write `complete`, real sessions still write `winding-down` at
teardown, so flipping it re-introduces the 327-minute false alarm.

**THE QUESTION TO PUT, in exactly these terms:** add `complete`, and then — is the
quiet `winding-down` reading a **PERMANENT compatibility floor** (accepting the
crash blind spot forever), or a **DEPRECATED one behind a dated fleet migration**
(restoring the alarm once every charter writes `complete`)? That is a policy call
recorded in no contract. It changes `overseer/marker-protocol.md` — the cardinal
contract — and the wrap-up text every supervised session receives. Do not decide
it as a worker, and do not reduce it to "option 1 or option 3".

## Next action

**Step 1 — read the item, not this file.**

```bash
with-livespec-env.sh -- bd show overseer-x29.1
```

**Step 2 — branch on a MECHANICAL condition, not on a judgement.** "Decided" is
not a ledger state, so it is spelled out here: the decision has been recorded if
and only if the item's body carries a line beginning `DECISION 2026-`. Nothing
else counts — not the status field, not this handoff, not chat history.

- **No `DECISION 2026-` line** → the next action is to put the question from the
  section above to the maintainer as ONE `AskUserQuestion` call: permanent
  compatibility floor versus dated deprecation, each option stating its own cost.
  Then do Step 3. Do not dispatch anything first.
- **A `DECISION 2026-` line is present** → skip to Step 4.

**Step 3 — write the answer back before anything else.** The worker who collects
the maintainer's answer OWNS this step, and it is where a thread otherwise
strands. Two commands, both required:

```bash
with-livespec-env.sh -- bd update overseer-x29.1 \
  --append-notes "DECISION 2026-MM-DD: <the maintainer's verdict, in their terms>"
with-livespec-env.sh -- bd update overseer-x29.1 --status ready
with-livespec-env.sh -- bd show overseer-x29.1   # confirm BOTH landed
```

An unwritten answer means the next reader re-asks a question the maintainer
already answered — which is the failure this mechanical condition exists to
prevent, so do not treat the read-back as optional.

**Step 4 — dispatch through the factory.**

```bash
/livespec-orchestrator-beads-fabro:drive --action impl:overseer-x29.1
```

or let the Dispatcher drain it now that it is `ready`. **Do NOT build it
in-session.** `ACTIVE` is never evidence that a run started; `fabro ps` is.

**Step 5 — close the epic and archive the thread**, once `overseer-x29.1` closes:
close `overseer-x29`, then `git mv plan/daemon-liveness-truth/
plan/archive/daemon-liveness-truth/` through the normal worktree → PR → merge
path. Nothing else on this thread is open.

## Deployment — measured, and it moved WHILE this was being written

**The fixes are live.** `overseerd` (pid 2796787) started 2026-08-03T00:02:21Z
from an editable install of `livespec_overseer-0.16.1` reinstalled at
2026-08-02T23:59:52Z, so it imports the source tree that carries both fixes.
Verified directly rather than inferred: `_DERIVED_NAME_SOURCE` and
`STATE_WINDING_DOWN` are both present in the `overseer/_supervisor_offer.py` the
daemon imports.

**The durable lesson, which outlives that measurement: a long-lived daemon keeps
its originally-imported modules.** Half an hour before the restart, the daemon had
been up since 2026-07-30T09:39Z — three days older than either merge — so master
was fixed, `v0.16.1` shipped the fixes, and the live top pane was still rendering
pre-fix behaviour. Merged is not released, released is not installed, and
installed is not *running*. Check the process, not the tag.

**A restart is the operator's act, not a worker's.** Never kill the acting daemon
in tmux `livespec-overseer:1.1` on your own initiative — it supervises every
tracked session in the fleet, and this thread's subject makes it especially
tempting to restart it while testing. The 00:02Z restart was not this thread's
doing.

## Acceptance shape this thread holds every child to

Demonstrate the **RED**, with a control proving the fix did not simply silence
everything. A fix that silences both halves is worse than the defect, because it
removes the alarm the whole supervision contract rests on. Sabotage against the
FINAL artifact, not an earlier draft; a sabotage producing no RED is UNVERIFIED,
not passed.

For `overseer-x29.1` specifically that means: a session that declares completion
and is then torn down must go quiet, **and** a session that declares
`winding-down` and then CRASHES must still report red. The second case is exactly
what PR #477 traded away, so a fix that does not restore it has not earned the
vocabulary change.

## Hazards this thread paid for — do not re-learn them

- **`just check` passing locally is not evidence about the tree you PUSHED.** The
  pre-push hook skips the aggregate on a green-token match (*"tree byte-identical
  to last green check"*), and the token is keyed to the tree. After moving or
  renaming a file, re-run `just check` before pushing.
- **`just check-coverage` reads an EXISTING `.coverage`** produced by
  `check-per-file-coverage`. Run it against a stale one and it reports confidently
  on a tree that no longer exists. `rm -f .coverage` first.
- **Coverage is measured over `tests/` too, at `fail-under=100`.** A new test
  module's own defensive branches must be exercised or the aggregate goes red.
- **A change to any file under `overseer/` REQUIRES a paired change under
  `tests/**`** (`commit_pairs_source_and_test`). The beside-tests in `overseer/`
  are themselves source to that check, so a beside-test alone does not satisfy it.
  `tests/conftest.py` puts `overseer/` on `sys.path`, so a module moves there
  verbatim with no import changes.
- **`just worktree-create` fails at this repo's worktree count** (SIGPIPE in
  `worktree-lib.sh`, exit 141, empty log). Rescue path, used successfully:
  `git worktree add <path> -b <branch>` then `just install-worktree-pack` inside
  it — then `git checkout -- .livespec.jsonc`, which the pack dirties with a key
  that only makes the existing default explicit. Fix tracked as
  `livespec-dev-tooling-zi4q`; never hand-edit the gitignored `dev-tooling/` copy.
- **A rejected hook-gated commit leaves the change STAGED**, and a following
  `git log` then shows some other track's commit at HEAD and reads as success.
  Check `git status`, not `git log`.
- **Master moves under you.** A worktree cut hours earlier can fail a check for a
  defect already fixed upstream; re-base before diagnosing a failure you did not
  cause.
- **`date -u -r <file>` does NOT apply `-u` on this host** (uutils, not GNU): it
  prints LOCAL time and the `Z` you append is a lie — a silent two-hour error.
  Read mtimes through `datetime.fromtimestamp(ts, timezone.utc)` when the value
  enters a claim. This cost a sibling thread a false accusation against a
  colleague's work (charter correction C19).
- The repo's own `.claude/CLAUDE.md` carries the two dispatch traps (a literal
  double-brace token in a work item's text makes it undispatchable; a stale plugin
  build's remedy appears to do nothing) and the several-Anthropic-credentials
  section. Cite them there; do not restate them here.

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never commit on the primary
checkout. Never `--no-verify`; halt and report on hook failure.
