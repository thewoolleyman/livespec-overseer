# What was in `tmp/supervisor/`, and what nearly died there

Audit run 2026-07-28 against the live directory, at maintainer request. This
note is the EVIDENCE for the thread's rule. Do not re-derive it.

## The measurement

`tmp/supervisor/` is gitignored (`.gitignore:2` — the whole `tmp/` tree). At
audit time it held:

| | count |
|---|---|
| files | 25 |
| `.md` prose | **18** |
| `.json` state | **0** |
| total prose lines | **1,811** |

Plus two directory-level artifacts that were not briefs at all:

- **`groom-draft-01.md`** (14 KB) — the 13-slice groom cut for epic
  `overseer-hbr`.
- **`workflow-changeset/`** — five `.yml` files, two `.diff` files and a
  `README.md`, staged for the maintainer to apply by hand into
  `.github/workflows/`.

## Why this was dangerous, in three specific ways

### 1. A confirmed near-loss

The lesson that `/livespec-orchestrator-beads-fabro:plan <slug>` is
**strict-resume-or-fail** — creation happens only through the no-argument
interview path — existed ONLY in `brief-17.md` and a tmux pane. It would have
died with the session. It survived because the maintainer happened to ask
whether two reported defects were covered; it is now recorded in
`plan/codex-parity-and-rollout-safety/supervisor-handoff.md` §Corrections.

**One session, one confirmed near-loss, caught by luck rather than by rule.**

### 2. A shadow copy that silently went stale

`workflow-changeset/` held duplicates of five files that already live under
`.github/workflows/`. Diffed against `origin/master` at audit time, four were
identical and one had **drifted**:

```
release-dispatch.yml
  master: reusable-release-dispatch.yml@v0.56.6
  staged: reusable-release-dispatch.yml@v0.54.18
```

**Applying the staged copy would have reverted a pin bump.** The staged set
existed only because a supervisor wrongly decided workflow files were
maintainer-side; once that invented gate was removed the worker landed the
files normally in PR #115, and the copies became stale duplicates nobody was
watching.

### 3. A tracked artifact citing an untracked one

`plan/codex-parity-and-rollout-safety/handoff.md` had to carry an explicit
warning that its provenance brief is gitignored and therefore "not a readable
artifact for a cold-open reader". A committed file pointing at an uncommitted
one is a dangling reference by construction — the handoff self-sufficiency
gate's own §3 (no dangling reference, fail-closed) exists to stop exactly this.

## What was NOT lost, and why that is not reassurance

Most content HAD been mirrored durably as it was produced:

- the groom draft → ledger items `overseer-hbr.10`–`.22` (all 13 present, all
  closed);
- the workflow changeset → merged in PR #115;
- brief findings → `handoff.md`, research notes, and ledger items.

But that mirroring was **convention, not enforcement** — a judgement call made
on every write by the same actor writing the file. That judgement failed once
(see §1) in a single session. The correct conclusion is not "the loss was
small"; it is "the loss rate is nonzero and unmonitored".

## Disposition applied at audit time

- `workflow-changeset/` — **deleted.** Verified superseded: all five files
  tracked on master, the one drift being a stale pin.
- `groom-draft-01.md` — **deleted.** Verified superseded: 13/13 slices in the
  ledger.
- the 18 briefs — **moved to `tmp/supervisor/briefs/`**, leaving zero files at
  the top level.

## The constraint that shapes any fix

`tmp/` is gitignored, so **CI never sees this directory**. A check over it
cannot run on a fresh clone and cannot be armed in the release path. Any
enforcement is meaningful ONLY on the operator's machine, where the risk
actually lives. Say that plainly in whatever ships — an enforcement that looks
armed and cannot fire is the pattern this repo has already shipped twice
(`check-no-workflow-edits`, wired into nothing; `LIVESPEC_RUN_MUTATION`, a
verified no-op).
