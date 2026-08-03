# Plan — daemon-liveness-truth (TERMINAL)

## STOP. THIS TRACK IS COMPLETE AND ARCHIVED.

You were handed this path by a respawn prompt. That prompt names a FIXED path and
is stale by design: this thread archived on **2026-08-03** (PR #562). This file
exists only so the prompt resolves to something true instead of a missing file.

The real records are at **`plan/archive/daemon-liveness-truth/`** — `handoff.md`,
`supervisor-handoff.md`, and `research/rung-3-corpus-measurement.md`. Read them for
history; nothing there is pending.

**Epic `overseer-x29` is CLOSED, 4/4.** Verify rather than trust this line:

```bash
with-livespec-env.sh -- bd show overseer-x29
```

A bare `bd` returns `Access denied` here; the credential wrapper is required, and
it prints a benign `auto-backup failed` warning on every call — the record still
prints, so do not read that as a failed measurement.

| child | outcome |
|---|---|
| `overseer-j1r` | fixed, PR #468 |
| `overseer-mkx` | fixed, PR #477 |
| `overseer-oydugu` | built, PR #521 — the first executable rung-3 gate |
| `overseer-x29.1` | documented, PR #545 |

Both daemon fixes shipped in `v0.16.1` and were verified **running** in the live
daemon, not merely merged.

## THE ONE THING THIS TRACK LEFT UNFINISHED, and it is small

`tests/prompts/test_picker_conduct_discriminates.py` line ~66 still cites
`plan/daemon-liveness-truth/research/rung-3-corpus-measurement.md`, a path that
moved under `plan/archive/` when this thread was archived. The repoint is a
one-line docstring edit.

**It is BLOCKED, not forgotten.** It cannot be committed while `overseer-bgs` is
open, because a changeset containing any `.py` file takes the hooks off their
doc-only fast path and onto the full aggregate, which cannot pass on a loaded
host. Check the blocker first:

```bash
with-livespec-env.sh -- bd show overseer-bgs
```

If `overseer-bgs` is CLOSED, do the repoint on its own branch through the normal
worktree → PR → merge path. If it is still open, **leave it alone** — the citation
already dangles on master and nothing gates it, so it is not urgent and not
worth fighting the aggregate for. Do NOT re-open this plan thread for it.

## Do not re-derive these — they cost this track real time

- **`check-agents-ai-references-resolve` does NOT resolve `plan/` paths.** It reads
  `.ai/<topic>.md` references out of AGENTS.md files only — verified by reading the
  checker, not inferred from its name. That is why the citation above rots
  silently and master stays green.
- **The doc-only fast path is the difference between 0.6s and never finishing**
  (`justfile:833` pre-commit, `justfile:883` pre-push), and it keys on **zero
  `.py` across the whole BRANCH vs origin/master**, not just the commit. Splitting
  a commit is not enough; the `.py` must leave the branch.
- **`overseer-bgs` is the live blocker on any `.py` commit here.** PR #568 merged
  and did **not** fix it — measured against `origin/master` itself, post-merge, at
  load 107: both `(c)` scrollback legs still fail. Its renew-on-change deadline
  covers the printing phase but not the window before the first output appears.
  The item is `ready` with that measurement recorded; do not close it on #568.
- **A `drive.py` exit of 0 means the request was ACCEPTED, not that work started.**
  A queued fabro run can be evicted before executing, leaving a phantom
  `active`/`fabro` claim. `fabro ps` is the evidence; `ACTIVE` never is. Both this
  and the `{{...}}` cause are in the repo's `AGENTS.md`.
- **An empty result is not a finding.** This track read four structurally
  guaranteed zeros as evidence in one session: `pgrep -x tmux` against a process
  named `tmux: server`; `timeout command tmux` unable to exec a shell builtin; a
  `drive.py` exit of 0; and a `bd update` run from the wrong directory. Each looked
  like a clean negative. Run a positive control.

## Related items left open, none of them this thread's

`overseer-bgs` (P1, the aggregate blocker), `overseer-jdo` (the general
flaky-aggregate cut — three named legs do not close it), `overseer-6i0` (the
real-tmux rig leaks a socket per test and never reaps its servers).

## The tombstone is temporary

Retiring this file and `supervisor-handoff.md` from the live path belongs to
whoever retires the `daemon-liveness-truth-supervisor` session — the same
three-step shape `supervisor-prompt-quality` used (`0464d6e` → `927ee49` →
`aa923de`). Until then both must stay, so this respawn path resolves.

## Your correct action

Report that this track is complete and archived, then stand down. Do not start
work. Do not adopt its successors.
