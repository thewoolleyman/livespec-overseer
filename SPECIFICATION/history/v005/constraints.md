# livespec-overseer — constraints

Architecture-level constraints an operator can observe from outside. Each one
is a boundary the implementation MUST hold, stated without prescribing the
internal composition that holds it.

## Runtime requirements

The overseer runs on Linux with tmux, and that is a DECLARED requirement, not
an unfinished portability story: session-to-pane joins read the Linux process
filesystem, and every acting mechanic drives a real tmux. The host boundary
is deliberately NOT abstracted — no per-OS shims, no terminal-multiplexer
abstraction; supporting another host would be a design decision taken on its
own evidence, never smuggled in as a seam.

On an unsupported host the daemon REFUSES to start and names exactly which
precondition failed. That check runs BEFORE every other startup gate, so an
unsupported host is never first reported as some downstream failure.

## Language and dependencies

The supervision package is standard-library-only Python: no third-party
imports anywhere in the package, and its executables run dependency-free
under an isolated interpreter. A change that introduces a runtime dependency
is a contract change, not an implementation detail.

## Determinism boundary

The daemon holds NO semantic judgment and makes no model calls. Every
"am I done / am I blocked?" decision is made by the supervised session's own
intelligence and expressed through the state file; the daemon only
pattern-matches deterministic pane signals and reads that file. Tokens are
never spent by the watching loop, so the live state surface can refresh
forever without cost or staleness.

## Filesystem boundaries

The overseer's daemon writes its runtime state to exactly two places: its
operator-home stores and the per-track scratch directory
`<repo>/tmp/overseer/<topic>/` inside each watched repository. The daemon
NEVER reads, writes, or hashes files under any repository's plan tree, and it
refuses to run while any watched repository fails to gitignore the scratch
path. The one attended exception is Control-Plane authored, not
daemon-written: the supervise-plan operator skill MAY create
plan/<topic>/supervisor-handoff.md in a watched repository, writing only
through that repository's own reviewed commit discipline (worktree, pull
request, review, merge), never directly to a primary checkout — an authored
artifact, not overseer runtime state. Its home-directory paths are fixed by
construction — there are no flags to relocate them — so the daemon behaves
identically from any working directory and any install location.

## Atomicity and single instance

Writes to the overseer's own stores replace the whole file atomically: a
reader observes the previous or the new complete content, never a partial
write, even across a crash mid-write. Concurrent writers — the daemon and
one-shot operator commands — serialize through advisory locks. At most ONE
daemon instance runs per mapping store, enforced by a singleton lock taken
for the daemon's whole lifetime. Storage failures on the overseer's own
files degrade with a warning; they never crash the supervision loop.

## Acting safety

Every keystroke-bearing act is suppressed unless the target pane is
positively identified as this track's supervised session, satisfies that act's
runtime-specific input predicate, is settled, and shows no structured gate or
human wait. Recognized shell-only evidence does not by itself prohibit an informational
paste. It may coexist with exactly two acts under their independent complete
predicates: the low-context wrap-up in contracts.md §"The wrap-up injection",
and the bounded pair-stall nudge in spec.md §"The keep-going nudge". The shell
is left running and neither paste authorizes a restart. Generating, changing,
sub-agent-busy, gated, human-waiting, foreign, bare-shell, and ambiguous panes
MUST never be pasted into. Multi-line payloads are delivered as one atomic
paste, never typed line-by-line. Restart is stricter than informational paste:
even a fresh certifiable `ready` MUST NOT restart while any busy evidence,
including a background shell, remains, and a restart resumes the session under
the same runtime it supervises, never another. Ambiguous evidence — an unknown
context reading or runtime status, an unreadable file, an unsettled pane — always
resolves to inaction.
