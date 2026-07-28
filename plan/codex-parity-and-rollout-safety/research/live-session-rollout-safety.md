# Research — problem 2: a plugin rollout breaks already-running Codex sessions

> **ANNOTATED 2026-07-28 after the groom. The cause, the `oh-my-codex #3024`
> precedent and the live-acceptance bar below all still hold and were not
> re-derived.** Two ownership claims were corrected by measurement and are
> marked inline as `[SUPERSEDED]` / `[FILED]`. Kept as the reasoning record and
> annotated rather than rewritten; `handoff.md` carries current state and wins
> on a conflict.

**Provenance: maintainer supervisor brief 17, researched and confirmed before
this thread existed. Do NOT re-derive it.**

## The cause, in the order the failure happens

1. Codex resolves plugin hook entrypoints to **absolute versioned paths** and
   keeps using them **for the lifetime of the process**. That is sound design,
   not a bug — it is what makes a running session stable against concurrent
   edits.
2. `codex plugin marketplace upgrade` materializes the new version and
   **prunes the old versioned cache directory**.
3. Our `ensure-codex-plugins` runs that upgrade at **bootstrap / session start**.
4. Therefore **starting a NEW Codex session deletes the directory an
   ALREADY-RUNNING session is still pointing at**, and the running session then
   fails on a path that no longer exists.

## Where the fix belongs — and where it does not

**Fleet code deletes nothing itself.** That was grepped and confirmed; the prune
is codex's own behavior. But **we choose WHEN `upgrade` runs**, so the trigger
is ours and so is the remedy. Do not go looking for a fleet `rm` to delete —
there isn't one, and hunting for it will waste a pass.

Disk evidence that pruning is real and non-uniform:
`~/.codex/plugins/cache/livespec` held **1** version;
`livespec-driver-codex` held **2**.

## Independent precedent — read it before designing anything

**`oh-my-codex` issue #3024** — *"Keep old versioned plugin cache dirs during
setup/update so live Codex sessions do not lose hook entrypoints"*. **Identical
failure**, independently reported, and **CLOSED** with a recommended policy:

- materialize the new version **first**;
- **keep old versioned dirs by default**;
- **never delete during normal setup/update**;
- cleanup only via one of: an **explicit command**, a **TTL / generation
  scheme**, or a **liveness-aware check** that proves no running Codex process
  references the old path.

That the same failure was found and closed elsewhere is the strongest signal
available that the shape of the fix is settled and should be adopted rather than
re-invented.

## Ownership — name it, do not silently absorb

This is **host-wide**, not an overseer concern. It affects `livespec`,
`livespec-driver-codex` and `livespec-orchestrator-beads-fabro` equally.

- The `ensure-codex-plugins` recipe lives in **`livespec-dev-tooling`**.

  > **[SUPERSEDED — the recipe is per-repo.]** Measured 2026-07-28:
  > `livespec_dev_tooling/fleet/_rows_local.py:22` and `justfile:76-78` state
  > that each governed repo's recipe **stays the single source**;
  > `livespec-dev-tooling` owns the shared module, not the bodies. This repo's
  > own copy — including the three `codex plugin marketplace upgrade` calls that
  > are this defect's TRIGGER — is at **`justfile:137-139`** within
  > `justfile:127-142`. So every governed repo is a trigger site in its own
  > right, which widens this problem's surface rather than narrowing it.

- The problem's natural home is **livespec core**, where epic **`livespec-c1k9`**
  (fleet plugin currency) lived.

  > **[FILED 2026-07-28]** as **`livespec-1p31`** in the `livespec` core tenant,
  > at `backlog`. It is slice **C1** of the groom's six-slice cut. The
  > groom-minted id `overseer-qfnjj6` recorded elsewhere is **DEAD** — bd
  > rejects a foreign-prefixed id at the destination tenant (groom defect
  > `bd-ib-a8zi`) — so look it up by `livespec-1p31` and nothing else.
- **`livespec-c1k9.10`** and **`livespec-c1k9.14`** are its closed ancestors.
  Cite them, and cite them precisely: they solved *becoming current at session
  start*. They did **NOT** address *not breaking a live session*. This thread is
  the second half of that story, not a re-run of the first.

This thread may carry cross-repo children, but **every child must name its
owning repo.** Silently absorbing another repo's work is the burial failure the
predecessor thread was created to prevent.

## ACCEPTANCE — live, not reasoned

**Start a Codex session; roll a real new plugin version through the normal path
while that session is alive; show the session still works.**

**A test that never has a live session open during a rollout proves nothing.**
The whole defect is an interaction between two processes in time — a unit test
over the upgrade path cannot observe it, and neither can inspecting the cache
directory afterwards.

## Coupling to problem 1 — recorded, and NOT a block

The two problems are **independent in cause and can run in parallel**. Two
couplings, neither of which sequences the work:

- **Problem 1 ENLARGES problem 2's blast radius.** It adds one more plugin whose
  rollout can break live sessions — and this repo publishes releases *several
  times a day*, so it is the worst possible addition from problem 2's point of
  view.
- **Problem 2's fix makes problem 1's acceptance CLEANER.** Testing problem 1
  means rolling a version into a Codex session, which is exactly the action that
  triggers problem 2. Until problem 2 is fixed, problem 1's live test is running
  on top of a known hazard.

Neither coupling justifies serializing them. Record both, run both.
