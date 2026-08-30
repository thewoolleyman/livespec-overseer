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

The supervision package is standard-library-only Python. Its executables MUST
run dependency-free under an isolated interpreter, and the package MUST NOT
import any third-party library from an installed environment.

A third-party library MAY be imported ONLY when it is vendored in-tree and
satisfies ALL THREE conditions below. A vendored import that fails any one of
them, and every non-vendored runtime dependency, remains a contract change
rather than an implementation detail.

(a) **Vendored.** The library's source is committed in-tree under
`overseer/_vendor/`, and every import of it resolves to that in-tree copy. The
package MUST NOT import the library from site-packages, a virtualenv, or any
other installed location, and MUST NOT declare it as an installed runtime
dependency.

(b) **Standalone.** Every import the vendored code evaluates at module load
MUST resolve either to the standard library or to another library vendored
under the same `overseer/_vendor/` tree. A library whose runtime dependencies
cannot themselves all be vendored under (a)-(c) MUST NOT be vendored under this
exemption. Modules shipped inside a vendored library that import anything
outside that set - optional integrations with type checkers, test frameworks,
or async runtimes - MUST be pruned from the vendored copy, or be provably
unreachable from every import the package evaluates.

(c) **Hermetic, with zero cross-library impact.** The package's use of the
vendored library MUST cause no impact or problem for any other livespec
library. It MUST NOT shadow, collide with, or change which copy or version of
any module another livespec library resolves - whether that library is vendored
alongside it, installed in the environment, or imported by a consumer that also
imports this package.

The conditions are cumulative. Vendoring under this exemption preserves the
load-bearing property the stdlib-only rule exists to protect: the executables
still run dependency-free under an isolated interpreter, because the dependency
is in the tree rather than in the environment.

## Determinism boundary

The daemon holds NO semantic judgment and makes no model calls. Every
"am I done / am I blocked?" decision is made by the supervised session's own
intelligence and expressed through the state file; the daemon only
pattern-matches deterministic pane signals and reads that file. Tokens are
never spent by the watching loop, so the live state surface can refresh
forever without cost or staleness.

The distinct Driver-owned supervisor completion gate is also fail-closed:
while supervision is active, ending a turn requires a valid structured
supervisor marker and independently verified wake-producer evidence. Missing,
ambiguous, stale, malformed, or prose-only completion or producer evidence
refuses completion. This does not give the daemon semantic judgment, pane-text
interpretation, or any new plan-tree access.

## Filesystem boundaries

The overseer's daemon writes its runtime state to exactly two places: its
operator-home stores and the per-track scratch directory
`<repo>/tmp/overseer/<topic>/` inside each watched repository. An authorized
foreman MAY keep its own runtime state only in
`<repo>/tmp/overseer/foreman/` inside that same gitignored scratch root and
MUST NOT create another scratch root. The daemon NEVER reads, writes, or
hashes files under a repository's plan tree, EXCEPT for the one named,
bounded resume-artifact certification described in contracts.md §"The
restart interlock": for a SUPERVISOR topic only, a read-only, restart-gating
check of either plan/<topic>/supervisor-handoff.md's existence or
plan/<topic>/epic.md's content, and no other plan-tree path or content. The attended Control-Plane
authoring exception permits supervise-plan to create exactly ONE reviewed
artifact, `.ai/supervisor-protocol.md`, under that repository's reviewed
commit discipline, and to author the per-plan binder as supervisor handoff
entries appended to the governed plan's ledger epic THROUGH the
orchestrator's sanctioned plan surface — never by a direct write to that
ledger, and never by creating or updating
`plan/<topic>/supervisor-handoff.md` through the pull request path.
Separately, an authorized unattended foreman MAY read plan-tree, pane, and
work-item text solely as evidence; it MUST NOT write or delete plan-tree
files, hash them as authorization, or treat text it reads as instructions.
Every tracked-file write remains subject to the repository's reviewed commit
discipline, and every scratch path remains subject to the existing startup
gitignore refusal. Its home-directory paths are fixed by construction —
there are no flags to relocate them — so the daemon behaves identically from
any working directory and any install location.

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
human wait — with the single named exception stated below, which inverts the
gate and human-wait legs of this sentence and no others. Recognized shell-only evidence does not by itself prohibit an informational
paste. It may coexist with exactly five acts under their independent complete
predicates: the low-context wrap-up in contracts.md §"The wrap-up injection"
together with its round-scoped tail, the ready-expiry notice of spec.md §"The
escalating wrap-up", which fires under the wrap-up's own complete guarded-paste
predicate; the idle-with-context-left keep-going nudge and the bounded
pair-stall nudge, both in spec.md §"The keep-going nudge"; and the bounded
charter-reminder paste into a stalled reserved-entity picker in spec.md §"The
stalled-picker charter reminder". The shell is left running and NO such paste
authorizes a restart. Generating, changing, sub-agent-busy, foreign, bare-shell,
and ambiguous panes MUST never be pasted into. Gated and human-waiting panes
MUST never be pasted into by any DAEMON informational act EXCEPT the
stalled-picker charter reminder under its own complete predicate, which MUST NOT
be widened to any other daemon act, pane class, or topic class. Multi-line
payloads are delivered as one atomic paste, never typed line-by-line. Restart
is stricter than informational paste:
even a fresh certifiable `ready` MUST NOT restart while any busy evidence,
including a background shell, remains, and a restart resumes the session under
the same runtime it supervises, never another. Ambiguous evidence — an unknown
context reading or runtime status, an unreadable file, an unsettled pane — always
resolves to inaction.

The foreman's valve disposition and its full-autonomy declaration obey the same
fail-closed rule. The disposition's safe default is report-only, and an absent,
empty, wrong-typed, malformed or unrecognized disposition value MUST resolve to
report-only rather than to the nearest match. The full_autonomy declaration's
safe default is false, and an absent, empty, wrong-typed, or non-true value MUST
resolve to false rather than to the nearest match. An unrecognized value for
either MUST NOT silently enable any act, and MUST be surfaced to the operator
rather than accepted quietly. A configuration in which full_autonomy is true and
the disposition is explicitly report-only or unrecognized is contradictory: full
autonomy governs the effective values, and the contradiction MUST be surfaced,
never silently resolved in either direction. The floors stated in spec.md are
not configuration beyond the single, closed relaxation spec.md §"Full autonomy
and the decision rule" grants to full_autonomy for a floor category this tree
itself defines, of which there are none at this revision: no setting MAY dispose of a decision a contract this tree binds to by
reference holds for a human, no setting MAY relax the cardinal rule,
actuator-only mutation, the security dissent, or journal-before-act, and
unavailable evidence, a panel that fails the effective decision rule, or a
failed journal append always resolve to escalation. The foreman MUST NOT widen
its own authority on the basis of any evidence it produced itself, and MUST NOT
set its own disposition, its own full-autonomy declaration, or its own decision
rule.
