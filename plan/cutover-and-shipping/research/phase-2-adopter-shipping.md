# Phase 2 — shipping the overseer to adopter families (shape DRAFT)

**Status: DRAFT for maintainer review** — the thread's eventual payload,
drafted 2026-07-23 while the entry-points slice ran in the factory. Grounded
in the recorded decisions (D5/D7/D8/D9 on core epic `livespec-b1uo`, read
back from the core tenant before drafting) and the operator-surface decision
(`operator-surface.md` beside this note). Nothing here is filed to the
ledger yet — the runway (slices `overseer-m5dtmj` → `overseer-tn3hmi` →
`overseer-5aaeyd`, plus `overseer-vlu5cd`) lands first, and the maintainer
owns every cut below.

## What "adopter family" means

A family is one operator with one `$HOME`, running the overseer against the
family's OWN repos and sessions. The development fleet this repo grew up in
is simply the FIRST family — nothing the code reads distinguishes it. That
is the meaning of D5 in shipping terms: `.livespec-fleet-manifest.jsonc` is
fleet-self-application, so the shipped tool's ONLY discovery input is the
family's own declaration file.

## The shipping shape (derived from standing decisions, not new ones)

1. **Install vehicle** — the plugin + package pair from the
   operator-surface decision: the plugin ships `/overseer` (the interactive
   pane contract); the package ships the `overseerd` / `overseer-start`
   entry points. An adopter installs both; versions ride release-please
   tags (and `overseer-vlu5cd` puts the running version on the render
   header, so an operator can SEE what they run).
2. **Configuration surface** — exactly one hand-edited file:
   `~/.livespec-overseer-repos.json` (the declared watch-set; leniently
   parsed per contracts.md). Everything else is fixed by construction. The
   per-repo precondition (the gitignored scratch path, refused at startup
   otherwise) is the only repo-side setup.
3. **Runtime envelope** — stdlib-only Python, tmux, and the agent CLIs the
   family actually uses; zero fleet coupling at runtime (D5), zero console
   coupling (peer, per D7's plane ruling and the repo-class split in
   D8/D9).
4. **The session-side half is part of the product.** marker-protocol.md is
   the contract an adopter's session briefs must follow; the
   fleet-pin-propagation protocol-misuse episodes (status prose written
   into the state file, twice on 2026-07-23) show the failure mode when a
   brief does not internalize it. Shipping includes teaching it —
   plugin-prose and README carry the token contract, not just this repo's
   internals.

## "Shipped" acceptance sketch (the bar, to be maintainer-ratified)

- On a CLEAN `$HOME` with the plugin + package installed and ONE declared
  repo carrying a plan thread, `overseer-start` brings up the two-pane
  supervision and the daemon supervises that thread — with no access to
  this fleet's manifest, credentials, or repos. (The scratch-`HOME` recipe
  in `overseer/AGENTS.md` §"How to exercise it live" is the seed of this
  smoke test.)
- The supervision contract is proven where the family runs it: either the
  smoke test exercises a full inject → declare → restart round in the
  scratch `HOME`, or the maintainer rules this fleet's Stage-4 proof plus
  the isolation smoke test sufficient.
- The install story is documented (the `overseer-5aaeyd` slice's README
  work) and names the D5 boundary out loud.

## Open questions — the maintainer's cut, not this note's

1. Marketplace hosting: does this repo publish its own plugin marketplace
   (as livespec core does) or join an existing family marketplace?
2. Is the Codex arm in scope for first ship? (`.livespec.jsonc` declares
   `codex: exempt` today; the daemon side is harness-neutral already.)
3. Does "shipped" warrant a SPECIFICATION scenario (an adopter-install
   scenario would route through `/livespec:propose-change` when ripe —
   spec-side, human-gated)?

## Non-goals, bounded by standing decisions

Never reads the fleet manifest (D5). Never a console component (D7 peers).
No new ledger state, no new store paths.

**Supervision prompts — position CORRECTED 2026-07-23.** An earlier
revision of this note read core's `plan-skill-supervisor-handoff` §10 as
foreclosing plan-tree supervision prompts; that read came from a stale
checkout and is SUPERSEDED by the thread's §11 (maintainer-adopted, livespec
PR #1695): a **Control-Plane `supervise-plan` skill in THIS repo's plugin
namespace** creates `plan/<topic>/supervisor-handoff.md` under a single
named carve-out, writing ONLY through the target repo's own commit
discipline (worktree → PR → merge). The DAEMON still never touches any plan
tree — the protected property ("supervision can never dirty a tracked
working tree") holds literally, because the attended, reviewed skill write
is not the unattended tick loop the non-interference clause governs. So
supervision prompts are plausibly part of what ships to adopter families,
as a sibling slice of the operator surface (filed under `overseer-3wt`).
