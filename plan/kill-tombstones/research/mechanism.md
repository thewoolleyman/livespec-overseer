# Why a tombstone is wrong — the mechanism, measured

**Owning repo:** `livespec-overseer`. Companion to
`plan/kill-tombstones/handoff.md` and
`plan/kill-tombstones/research/enforcement-inventory.md`.

Every claim below is a claim with a timestamp, including this sentence.
Measurements were taken 2026-08-04 against `origin/master` of each named repo.

## What a tombstone is

A **tombstone** is a stub `handoff.md` deliberately left behind at the LIVE path
`plan/<topic>/handoff.md` after that thread's real record has been moved to
`plan/archive/<topic>/`. Its body announces its own emptiness — `# <topic> —
terminal handoff`, `## Status: COMPLETE AND ARCHIVED`, "Do not reopen or
redispatch it from this handoff."

It was adopted as a MITIGATION for `overseer-y26`, not as a design. Its own text
says so: "A tombstone is the mitigation, not the fix."

## The four things wrong with it

### 1. It leaves an archived plan registered as a live track, forever

The overseer daemon discovers one track per **unarchived plan-topic directory**
(`SPECIFICATION/spec.md` §"Track discovery and the mapping store"). Discovery
keys on the DIRECTORY existing. A tombstone keeps the directory in existence, so
a thread that is complete and archived keeps presenting as a live, startable
track in the daemon's list — which is the operator-visible symptom and the reason
this thread exists.

### 2. It disarms the mechanism that would have cleaned it up

This is the sharp part, and it is why "harmless stub" is false.

`overseer/_supervisor_discovery.archive_gc` runs every acting tick from
`build_rows` and drops a mapping row when `registry.archived_or_gone` reports the
plan archived or deleted. **That test is DIRECTORY-level**: a present
`plan/<topic>/` wins and returns `False`; otherwise a present
`plan/archive/<topic>/` returns `True`; otherwise deleted returns `True`.

The directory-first precedence is load-bearing and MUST NOT be changed — it was
adversarial-review blocker **B6**, and it protects a NEW plan that reuses a
retired topic slug from being GC-dropped every tick.

So the tombstone keeps the live directory alive at exactly the granularity the GC
tests, and the GC can never fire for that row. **The workaround defeats the
mechanism that makes the workaround unnecessary.** `overseer-y26`'s own
2026-08-02 correction records this: "THE WORKAROUND CREATED THE CONDITION."

### 2a. LIVE EVIDENCE — archived threads were NUDGED, WRAP-UP-INJECTED and RESTARTED

Not theory. Measured by this thread 2026-08-04 from
`/data/projects/livespec-overseer/tmp/overseer/daemon.log`, counting only actions
whose timestamp is AFTER that thread's archive commit:

| thread | archived at (UTC) | nudged | wrap-up injected | **RESTARTED** | last action |
|---|---|---|---|---|---|
| `fleet-charter-remediation` | 2026-08-03T05:28:28Z (`b0f748e`) | 4 | 1 | **1** | 2026-08-03T19:38:44Z |
| `release-automation-gap` | 2026-08-03T04:57:19Z (`0cfccc2`) | 0 | 21 | 0 | 2026-08-03T06:10:21Z |
| `daemon-liveness-truth` | 2026-08-03T03:05:59Z (`66adcc0`) | 0 | 1 | **1** | 2026-08-03T04:07:46Z |

Read this table honestly. The `release-automation-gap` wrap-ups, and some of the
others in the minutes right after an archive, are a session that was still alive
winding ITSELF down — those are not proof on their own. **Four rows are
unambiguous:**

- `daemon-liveness-truth` was **RESTARTED at 04:07:46Z**, 1h02m after its archive
  merged.
- `fleet-charter-remediation` was **RESTARTED at 09:47:18Z**, 4h19m after its
  archive merged, and then nudged at 11:00:42Z, 12:29:57Z and **19:38:44Z — 14h10m
  after the thread was finished and archived**.

A restart respawns a session against a completed thread. That is the cost of a
tombstone: not an idle row in a list, but the daemon spending real actions —
and a real pane — driving work that is done.

### 3. It violates the plan-thread lifecycle invariant that is already contract

livespec core, `SPECIFICATION/non-functional-requirements.md` §"Planning Lane
guidance" → "Archive on epic close":

> A plan thread's lifecycle binds to its ledger epic: `plan/<topic>/` is active
> if and only if its epic is open, and archived to `plan/archive/<topic>/` if and
> only if the epic is closed.

A tombstone is an ACTIVE `plan/<topic>/` whose epic is CLOSED. It is already
forbidden by the invariant as written; what is missing is that the invariant
never says so in words a session will recognise as covering this case, and
nothing mechanically enforces it in the repo where tombstones were being written.

The orchestrator's realization prose says the same and specifies the clean move —
`livespec-orchestrator-beads-fabro`'s `.claude-plugin/prose/plan.md` §"Step 5 —
Archive on epic close":

> ```text
> git mv plan/<topic>/ plan/archive/<topic>/
> ```

A whole-directory `git mv` leaves NOTHING at the live path. The tombstone
convention was never sanctioned by any spec or prose; it grew as an ad-hoc
workaround and then propagated by precedent.

### 4. A tombstone does not stay inert — it does plan work

`plan/fleet-charter-remediation/handoff.md` (reverted from master 2026-08-04 by
`f6728c8`, "docs(plan): revert the fleet-charter-remediation tombstone — it
defeats archive-GC") is the anti-example, and the maintainer named it as such.
It carried:

- **Live routing instructions** — "That is `overseer-x1q` (P1), and it is now
  owned by `plan/charter-gate-ratchet/`. Resume there, not here."
- **A loose end two sessions independently discharged** — its `#611` section sat
  UNCOMMITTED in the primary checkout for hours, invisible to the respawn prompt
  that resolves to that very path, so one session re-did work another had already
  finished. The tombstone's own text draws the lesson: "A tombstone edit that
  stays in the working tree is not a handoff."
- **A self-correcting count** — "That number was 41 here and 40 twelve lines
  below, and 40 is the right one."

Routing, blockers and live numbers are precisely what a NON-archived plan thread
or a work-item is for. A file that carries them is not a tombstone; it is a plan
thread pretending to be closed.

## The root cause the tombstone was mitigating — `overseer-y26`

`overseer-y26` (P1, `backlog` at time of writing) — "Archiving a plan thread
leaves the overseer's stored resume line pointing at the moved handoff.md, so a
restart pastes a missing-file path and the fresh session has no task."

It has TWO halves, and they fail differently. A fix that closes only the first
would report success while leaving the worse half broken.

**Worker half — STORED, misdirects.** The mapping store `~/.livespec-overseer.jsonl`
holds a `handoff` path and a `resume` line per track, both hard-coding
`plan/<topic>/handoff.md`. An archive moves the file; nothing rewrites the row.
On restart, `_do_restart` bracketed-pastes the stored line verbatim and the fresh
autonomous session is handed one prompt naming a file that does not exist.

**Supervisor half — COMPUTED, REFUSES.** `overseer/_supervisor_prompts.py:145-152`:

```python
def supervisor_handoff_path(*, repo: str, topic: str) -> Path:
    return Path(repo) / "plan" / topic / "supervisor-handoff.md"
```

Nothing stores it, so nothing can migrate it and no store-side assertion can see
it. `overseer/_supervisor_restart.py` existence-tests that computed path and, when
it is missing, calls `sup.alert` with `condition="supervisor-handoff-missing"`
(line 159) and **returns without restarting**. A supervisor that winds down
correctly and declares `ready` is exactly the case that hits it.

And the worker path is `overseer/_supervisor_prompts.py:142`:

```python
return str(Path(repo) / "plan" / topic / "handoff.md")
```

— a FIXED live path computed from the topic, which knows nothing about
`plan/archive/`.

**Why the daemon cannot self-detect this.** Architecture invariant 1 forbids the
overseer from reading, writing or stat-ing files under `plan/`; discovery only
enumerates directories. The one component holding the pointer is precisely the
component forbidden to check that it still resolves. The invariant is correct and
must NOT be relaxed — the fix belongs on the archival side or in a store-side
check, never in a daemon stat call.

## The replacement rule (maintainer-declared 2026-08-04)

When a plan thread would close with anything unresolved, do exactly ONE of:

1. **LEAVE THE PLAN UN-ARCHIVED** until its blockers are resolved; or
2. **TRANSFER ALL BLOCKERS** to a different or new NON-ARCHIVED plan thread
   and/or work-item, then archive with a clean whole-directory `git mv` that
   leaves NOTHING at the live path.

Leaving a stub behind is FORBIDDEN, permanently, in every fleet member and every
adopter.

Note that alternative 2 is what `fleet-charter-remediation` had ALREADY done
correctly — `plan/charter-gate-ratchet/` exists and owns `overseer-x1q`. Its
tombstone was pure residue on top of a correct transfer, which is the cleanest
demonstration that the stub adds nothing a live plan does not already carry.

## What must NOT be "fixed" in the course of this

- **Do not change `registry.archived_or_gone` to a file-level test.** Its
  directory-first precedence is adversarial-review blocker B6 and protects slug
  reuse. The defect window is a plan directory that still exists but no longer
  contains its `handoff.md` — banning tombstones closes that window at the
  source instead.
- **Do not relax architecture invariant 1** to let the daemon stat `plan/`.
- **Do not hand-edit `~/.livespec-overseer.jsonl`** to route around an open
  defect. It is shared fleet state read by every track, and editing it hides the
  condition. `overseer-y26`'s 2026-08-04 note records this decision explicitly.

## Removing a tombstone — the ordering, and the trap that costs a turn

### The ordering hazard is SUPERSEDED — read both, apply the second

`overseer-y26`'s description says: "the ordering is NOT arbitrary. Remove the
daemon mapping rows FIRST, then delete the stub files." That instruction was
written when remedy 1 (leave a stub) was believed correct.

**It is superseded by the measurement recorded on the same item 2026-08-03/04**,
which the `fleet-charter-remediation` supervisor took after reproducing the defect
themselves: a clean whole-directory `git mv` **already closes the hazard**. With
the live directory gone, `archived_or_gone` returns `True`, `archive_gc` drops the
row, and **there is no row left to respawn from** — so a stale resume line can
never be pasted. Deleting the stub is therefore sufficient on its own; no
manual row removal is needed, and hand-editing `~/.livespec-overseer.jsonl` to
pre-empt the GC is forbidden anyway (it is shared fleet state, and editing it
hides the condition).

Corroborated by this thread 2026-08-04: the mapping store holds **15 rows with
exactly ONE dangling entry** — `foreman`, the one remaining tombstone. Every
other archived topic (`fleet-charter-remediation`, `release-automation-gap`,
`daemon-liveness-truth`, `supervisor-prompt-quality`) has already been GC'd with
no human action.

### THE TRAP: the daemon reads the PRIMARY CHECKOUT'S WORKING TREE, not git

Merging the deletion is **NOT** enough. The `fleet-charter-remediation`
supervisor lost a turn to this: their revert was on `origin/master` while
`/data/projects/livespec-overseer` sat one commit behind, so the directory was
still on disk, `archived_or_gone` still returned `False`, the row survived, and
the maintainer was still seeing the track after the fix had merged.

**After every tombstone removal, confirm the PRIMARY checkout actually has it:**

```bash
git -C /data/projects/livespec-overseer rev-list --count HEAD..origin/master   # must be 0
test -d /data/projects/livespec-overseer/plan/<topic>                          # must FAIL
```

Only then does the next GC tick drop the row. Verified discharged for
`fleet-charter-remediation` 2026-08-04: count 0, directory absent, row absent.

Related: `homelab`'s default branch is **`main`**, not `master`. Resolve a repo's
default branch from the forge (`gh repo view --json defaultBranchRef`) rather than
assuming — the fleet does not share one convention.

## Corrected inventory — how many tombstones actually remain

A same-day report to this thread named `release-automation-gap` and
`daemon-liveness-truth` as surviving live instances. **Re-measured 2026-08-04
against a freshly fetched `origin/master`: that is stale — both were already
retired at `5560b5e`.** Live-path test:

| topic | `plan/<topic>/` | `plan/archive/<topic>/` |
|---|---|---|
| `foreman` | **YES — tombstone** | YES |
| `fleet-charter-remediation` | no | YES |
| `release-automation-gap` | no | YES |
| `daemon-liveness-truth` | no | YES |
| `supervisor-prompt-quality` | no | YES |

`git grep -l "COMPLETE AND ARCHIVED" origin/master -- 'plan/*'`, excluding
`plan/archive/`, returns exactly one path: **`plan/foreman/handoff.md`**. That is
the whole remaining purge in this repo, and no other fleet member or adopter
carries one (checked: all nine fleet members plus `openbrain`, `resume`,
`homelab`).

**Both-present is the tombstone signature.** A topic that is simultaneously live
and archived is the cheapest, credential-free, unambiguous detector — see
`plan/kill-tombstones/research/enforcement-inventory.md`.
