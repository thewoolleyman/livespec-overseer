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

`llm-provider-manager` is likewise Linux-only. Its architecture depends on the
Linux process model, enforceable local ownership and modes, a user-scoped
kernel keyring, a host identity suitable for secret-store namespace binding,
the configured local SecretStore executable, an authenticated local agent CLI,
and a headed browser in a graphical session. The exact paths, permissions,
capability probes and failure mappings are defined once in contracts.md. The
manager MUST validate each prerequisite before its dependent action and MUST
NOT fall back to another operating system, plaintext secret storage, another
agent credential source, a bundled or cloud browser, or network-exposed browser
control.

## Language and dependencies

The product package is standard-library-only Python. Every substantive
executable path MUST run dependency-free under an isolated interpreter, and
the package MUST NOT import any third-party library from an installed
environment. The installer-generated wrapper and the standard-library-only
`llm-provider-manager` bootstrap are permitted only to establish the exact
isolated companion boundary in contracts.md before any substantive manager
import or action. Credential backends and browser control MUST obey this same
rule; they MAY use only the standard library or the vendoring exemption below.

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

## Filesystem boundaries

The overseer's daemon writes its runtime state to exactly two places: its
operator-home stores and the per-track scratch directory
`<repo>/tmp/overseer/<topic>/` inside each watched repository. The daemon NEVER reads, writes, or
hashes files under a repository's plan tree, EXCEPT for the one named,
bounded resume-artifact certification described in contracts.md §"The
restart interlock": for a SUPERVISOR topic only, a read-only, restart-gating
check of either plan/<topic>/supervisor-handoff.md's existence or
plan/<topic>/epic.md's content, and no other plan-tree path or content. Every tracked-file write remains subject to the repository's reviewed commit
discipline, and every scratch path remains subject to the existing startup
gitignore refusal. Its home-directory paths are fixed by construction —
there are no flags to relocate them — so the daemon behaves identically from
any working directory and any install location.

## Atomicity and single instance

This section governs only the supervision daemon's stores. The caam operation's
last-writer-wins publication and fail-loudly exit semantics are defined in
contracts.md §"The account-rotation operation"; the manager's fail-closed store,
audit and provisioning semantics are defined in contracts.md §"The LLM
credential-provider operation". Neither operation inherits the warning-only
fallback below.

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
