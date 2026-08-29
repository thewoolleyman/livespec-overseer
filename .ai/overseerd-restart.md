# Restarting `overseerd`, and knowing what code it is running

Moved verbatim from `AGENTS.md`.

## The `overseerd` daemon may be restarted at any time, as long as it isn't broken

Ratified by the maintainer 2026-08-17, superseding an earlier operator-gated
posture that had been established as a same-thread convention during a live
verification session rather than written down anywhere — this section is that
missing write-down, not a change to a previously-documented rule.

**The ruling, verbatim:** the daemon can be restarted at any time as long as
it isn't broken. No maintainer approval is required per restart. This applies
to the acting `overseerd` process specifically; it does not authorize
force-killing or force-respawning a tracked *session* (a worker or supervisor
pane) — that remains gated by the cardinal rule in
`overseer/marker-protocol.md` (a session is restarted only after it declares
itself `ready`).

**The "isn't broken" carve-out.** Before restarting, a quick sanity check that
the daemon is currently serving correctly (e.g. `overseerd --help`, or reading
a recent, sane `~/.livespec-overseer-status.json`) is reasonable diligence,
but this is not a formal precondition requiring separate sign-off — an agent
acting under this ruling uses ordinary judgment, the same as for any other
routine operational action.

**The checkout-fast-forward + respawn procedure**, observed working correctly
across three bounces during the ratifying session:

1. Fast-forward the primary checkout to the target commit
   (`git pull --ff-only` or `git merge --ff-only origin/master`) — do this
   *immediately* before the restart, not minutes ahead, since `overseerd` is a
   single long-lived process that imports `overseer.*` once at startup and
   never hot-reloads; whatever the checkout holds at the moment of import is
   what runs until the next bounce.
2. Stop the running `overseerd` process and start a fresh one
   (`overseerd`) from that checkout.
3. Verify the bounce actually picked up the intended change — do not assume:
   confirm the new process's pid and start time (`ps -o lstart=`), confirm via
   `git reflog` that the fast-forward landed *before* that start time (not
   after — a checkout pulled forward post-start does not affect an
   already-running process), and confirm the target commit is an ancestor of
   what was checked out (`git merge-base --is-ancestor`). A checkout pulled
   forward even a few seconds late produces a daemon that silently runs the
   prior release; this was observed directly during the ratifying session (one
   bounce landed one release behind because the pull that would have carried
   the fix arrived after the daemon had already started).

   **NORMALIZE THE CLOCKS BEFORE COMPARING THEM — `ps -o lstart` prints LOCAL
   time.** Step 3 is a before/after comparison between two instruments, and on
   this host they do not speak the same clock: the timezone is `Europe/Berlin`
   (CEST, **UTC+2**), so `ps -o lstart=` renders two hours ahead of the `Z`
   timestamps used by the ledger, the dispatch journal, `date -u`, and this
   file's own measurements. Applying that offset to only one side inverts the
   very test the step exists to make — a bounce that landed two hours BEFORE a
   fast-forward reads as having landed after it, and vice versa.

   Measured 2026-08-22, and it very nearly produced a published wrong
   conclusion: a listener's owning process showed `lstart` of `01:43:39` against
   a UTC wall clock of `01:23:53`, i.e. **twenty minutes in the future**, which
   reads as "started by the thing I just ran". Normalizing gave a true start of
   `23:43Z` — an hour and forty minutes EARLIER, a different process, a different
   session, and the opposite conclusion. A future start time is the tell; treat
   it as a unit error, never as a clock skew to reason around.

   Take the process start as an absolute instead of parsing the rendered string:

       stat -c '%y' /proc/<pid>          # start time WITH its UTC offset
       date -u -d "@$(stat -c %Y /proc/<pid>)" +%Y-%m-%dT%H:%M:%SZ

   and pin the other side to the same clock with `git reflog --date=iso-strict`
   (which carries an explicit offset) rather than the default relative rendering.
   The rule generalizes past this one step: **every timestamp comparison in this
   fleet has two sides, and any side rendered without an offset is a guess.**

**Rider, ratified 2026-08-20 — maintainer, typed directly into the foreman
pane; verbatim on the `overseer-z5fo4y` decision-batch comment:** "Yes it can
be restarted any time but whatever is restarting it must ensure that it stays
properly in the top pane of the overseer TMUX session as the overseer skill
prescribes." So the procedure above carries one more obligation: whatever
performs the restart must ensure the fresh `overseerd` lands, and stays, in
the TOP pane of the two-pane overseer tmux session per the overseer skill
(`overseer/SKILL.md`) — a daemon respawned into the wrong pane or into a
detached shell satisfies the three bounce steps and still violates the ruling.

**BEFORE TRUSTING THE ACTING DAEMON, CHECK WHAT IT IS RUNNING — AND USE THE ONE-READ
DISCRIMINATOR.** The section above is about restarting correctly. This is the
inverse and more common case: the daemon is healthy, serving, writing a fresh
status file every tick, and running **code from hours ago**. Nothing surfaces
that, because a stale daemon and a current one are indistinguishable from every
symptom except the one that is missing.

`~/.livespec-overseer-status.json` publishes the answer directly:

    daemon_package: {"package_dir": "…/overseer", "version": "1.7.4"}

Compare that to `git describe --tags --abbrev=0`. Measured 2026-08-21: the acting
daemon reported **1.7.4** while master was at **v1.12.0**, and two tracks sat at
`ready-uncertifiable` — one for **fifteen hours** — in precisely the state a fix
merged that afternoon was written to make certifiable.

**Prefer this to reasoning from process start times or file dates.** Both were
tried on that incident; the start-time argument was sound but laborious, and the
file-date argument was outright wrong (see the file-history rule in
`.ai/record-versus-world.md`). The
version field settles it in one read and needs no argument about import semantics.

**The asymmetry to expect, because it sends investigators at the wrong half.**
Commands like `overseer-declare` are **separate entrypoints** — a fresh subprocess
per call — so they pick up new code immediately. The daemon does not: it imports
`overseer.*` once and never hot-reloads. After a merge and before a bounce, the
command half is fixed and the daemon half is not, so a session can be told the
truth by the command and then stranded anyway by the daemon. That reads as the
command being wrong.

**So a merged fix to daemon-side code is not in effect until a bounce**, and
"merged" is not a synonym for "live on this host". When a plan's deliverable is
daemon behaviour, its acceptance should include the bounce and a live control —
not merely a green CI run.

**THERE IS A THIRD STALENESS SURFACE, AND THE TWO ABOVE ARE THE EASY ONES.**
Measured 2026-08-22 (`overseer-lixhd3.1`). The paragraphs above frame this as a
two-way split: separate entrypoints are always fresh, the daemon is stale until
bounced. A third surface behaves like neither. **Prose — the operator contracts
under `.claude-plugin/prose/` — is read at SKILL-INVOCATION time and held for the
life of that session.** A session that invoked its skill before a contract change
runs the OLD contract however current the daemon is, and **no bounce reaches it**,
because the daemon does not own that copy. It goes current only when a fresh
session starts.

**The specimen shows both halves disagreeing in one row**, which is what makes it
worth recording rather than deducing. Minutes after a correct bounce onto a merge
that changed both daemon code and `foreman.md`, the status file carried a
`foreman-blocking-prompt` row against a live foreman seat: the post-bounce daemon
raising a condition that had shipped minutes earlier, against a seat that was
still behaving under the pre-merge contract because it had started first.
**Detection current, behaviour stale, same row.**

**The trap this sets, and it is expensive because it looks like a failed bounce.**
An acceptance criterion phrased as an observed end-to-end BEHAVIOUR can be
UNSATISFIABLE after a completely correct bounce, because only a session that
STARTED AFTER the merge can demonstrate it. Do not diagnose that as a bad bounce,
and do not re-bounce chasing it. Split such an acceptance in two: the daemon half,
provable immediately after the bounce, and the contract half, which is a WAIT for a
fresh session rather than a task anyone can perform.

**And keep the claim boundary straight.** "The daemon runs current code" does not
imply "the fleet is running current code". The second is false for every session
already in flight, and a reader will infer it from the first unless told otherwise.

**Two bounce mechanics worth having before you need them.** Confirm a bounce by the
daemon's INSTANCE ID changing, not by its version — version discriminates only when
the release actually changed, so a within-release bounce checked by version is a
check that cannot fail. And stop the daemon with `kill -TERM` on its pid, never
Ctrl-C into the pane: the pane's process is an interactive shell with `overseerd` as
its child, so TERM returns the shell to a prompt and the pane survives, while Ctrl-C
closes the pane and violates the top-pane rider even though all three procedure
steps were followed. Allow ~40s for the new instance to publish its first snapshot;
reading too early shows the PREVIOUS instance's snapshot, which is indistinguishable
from a failed bounce.

**When requesting or reporting a bounce, say which kind of evidence it can carry:**
an OBSERVED ROW, or only an INSPECTION OF THE LOADED TREE. A change whose new
condition has no live input yet can only be confirmed structurally, and saying so
keeps a structural check from reading as weaker than it is — and a positive one from
reading as stronger. Of three bounces on 2026-08-22, exactly one carried both a new
status-vocabulary entry and a live input for it.
