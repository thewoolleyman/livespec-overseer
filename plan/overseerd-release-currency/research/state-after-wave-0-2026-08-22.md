# State after wave 0 — what is proven, what is not

ledger anchor `overseer-6s3pk6`

Children `.1` and `.2` are merged and closed. This note records what that
actually bought, because two of the three things a reader would assume from
"the isolated prefix landed" are **not** yet true on this host.

## Proven, and merged

**`.1` — the eligibility rule.** `overseer/release_currency.py`'s
`update_target` decides whether the commit `refs/heads/release` resolves to may
replace what the daemon runs. Pure function of three supplied values; the forge
call stays in the caller, matching `release_lane_watch`'s existing shape, so no
network reaches the enforcement aggregate. Every unknown falls toward NOT
adopting — unresolvable ref, unreadable rollup, unsettled run, and a commit
reporting no checks at all.

**`.2` — the daemon-owned runtime prefix.** `overseer/runtime_prefix.py`
installs the adopted release into `~/.local/share/livespec-overseer/runtime/
<version>/` from `git+<url>@v<APP_VERSION>` — an immutable tag, never the
working tree — and `overseer-start` now launches the daemon from that prefix's
venv. On failure it refuses and says so rather than falling back to the
checkout.

## NOT proven, and the distinction matters

**The ACTING daemon still runs from the checkout.** Measured 2026-08-22T09:1xZ:
`daemon_package.package_dir` is `/data/projects/livespec-overseer/overseer`.
`.2` changed the BOOTSTRAP path, and the running daemon predates it. Nothing
about a merge reaches a process that has already imported its code. So `.2`'s
acceptance — "with a deliberately broken edit in the primary working tree, the
running daemon is unaffected" — is **structurally satisfied and not yet
demonstrated live**. It becomes true for the first daemon started by an
`overseer-start` bootstrap after the merge, and not before.

That is the third staleness surface applied to this plan's own work: a merged
fix is not in effect until the thing that holds the old copy is replaced.

**Nothing yet consumes `.1`'s rule.** No module imports `release_currency`. The
forge-reading caller that supplies the resolved ref and the check rollup is
still to be written. So the repo now knows how to *decide* and how to *install*,
and still has nothing that *checks on a schedule and acts*.

**Therefore the plan's headline is still false.** "overseerd runs only released
green code and keeps itself current" describes none of what is running right
now. The gap that motivated the plan is unchanged, and it WIDENED WHILE THIS
NOTE WAS BEING WRITTEN: at 09:14:17Z the acting daemon publishes 1.28.3
(instance `c9ac6e55…`, healthy, package_dir on the working tree) against
`origin/master` at **v1.34.0** — six releases behind. Measured across this
session master moved v1.21.0 → v1.34.0 while the acting daemon was found
multiple releases behind on four separate occasions, each caught only because a
person happened to read the version field.

**Treat every version figure in this note as a measurement with an expiry.** The
v1.32.5 reading taken twenty minutes before this edit was already wrong by the
time the edit was made — which is the plan's own thesis arriving inside its own
research note.

## The claim boundary, restated because it is easy to lose

Even when every child lands, "the daemon is current" will not imply "the fleet
is current". Operator contracts under `.claude-plugin/prose/` are read at
skill-invocation time and held for the life of a session, so a session that
started before a contract change runs the old contract however current the
daemon is, and no bounce reaches it.

## A deferral whose precondition is now met

The ratification note deferred unifying the daemon's runtime with the command
entrypoints' plugin-cache build, "reconsidered as its own thread once the daemon
owns a versioned runtime". `.2` has landed, so that condition is satisfied. It
remains **out of scope here** — this plan is daemon-scoped by its own scoping
event — but it is now ripe to open rather than merely deferred, and the skew is
real: measured tonight, `overseerd` ran from the project venv while
`overseer-declare` resolved from a plugin cache build, with independent update
cadences.

## Bounce mechanics, earned from three live bounces

Recorded on `.6` in full; summarised here because they are the operational half
of what this plan automates.

- Stop with `kill -TERM` on the daemon pid, not Ctrl-C into the pane. The pane
  survives where its own process is an interactive shell with `overseerd` as a
  child; Ctrl-C kills the pane where `overseerd` **is** the pane's command.
- Verify by the **instance id changing**, not by the version. A within-release
  bounce leaves the version identical whether or not the bounce happened, so
  that check cannot discriminate in the case you depend on it. Allow ~40s: a
  snapshot written by the previous instance reads exactly like a failed bounce.
- Check the safe point first — no supervised session declared ready or mid
  restart — or a bounce can strand one between its declaration and its respawn.
