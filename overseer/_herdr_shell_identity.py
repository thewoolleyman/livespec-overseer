"""_herdr_shell_identity.py — what counts as a created pane's RETAINED SHELL.

A private collaborator of :mod:`herdr_layout`, split from
:mod:`_herdr_layout_proofs` because it answers a different kind of question. The
other proofs ask the herdr server about panes: which exist, where they sit, which
is new. This one asks the KERNEL about a process, and it exists because the
server's answer to "is this pane an idle shell?" is not sufficient.

**The defect that shaped this module.** The first cut of the retained-shell proof
compared `shell_pid` and its equality with `foreground_process_group_id` across
two readings. `exec` replaces a process image IN PLACE, so it survives all of
that. Measured against herdr 0.9.3, running `exec sleep 300` in a pane:

    before   shell_pid 179303   group 179303   name bash    exe /usr/bin/bash
    after    shell_pid 179303   group 179303   name sleep   exe /usr/bin/sleep
    /proc starttime 164433575 BOTH BEFORE AND AFTER

Same pid, same group, same start time. The pane reads as an idle retained shell
and its root is `sleep`, so the daemon command plus Enter goes to that program's
stdin. The start time is kept in the identity anyway, but NOT for this: it cannot
see a replacement, it sees PID REUSE — a genuinely different process arriving at
the same number.

**Two halves, carrying different weight — and NEITHER is airtight. An earlier
version of this paragraph called the first one that, which overstated what two
point-in-time snapshots can prove.**

  - :func:`retained_shell` with `expected` set is a FRESH CORROBORATION. The
    whole observed identity is recorded at establish and re-read immediately
    before the write, and any difference refuses. What that buys is detection of
    an OBSERVED IMAGE CHANGE: between those two readings the kernel came to
    report a different executable, or a different start time, for the pid herdr
    calls the pane's shell. It needs no judgement about what a shell is, which
    is what makes it the stronger of the two halves.

    Two things it does NOT do, stated because "airtight" implied both. It does
    not atomically exclude a LATER `exec` — the recheck is a snapshot taken
    before the write, not a lock held across it, so a replacement landing after
    that read is outside what any snapshot can see. And it does not detect a
    SAME-EXECUTABLE replacement: an `exec` of the same binary keeps the pid, the
    start time AND the executable, leaving the comparison nothing to refuse. The
    guarantee is "the image this operation observed did not change", never "the
    image cannot have changed".
  - `expected=None` — the establish — needs POSITIVE evidence, because a root
    replaced BEFORE either reading produces two readings that agree perfectly.
    What refuses it is that the kernel's executable is not a login shell
    ACCORDING TO THE SYSTEM: :func:`system_login_shells` reads `/etc/shells` and
    the invoking user's passwd entry. That is the operating system's own answer,
    not an allowlist authored here — and it is explicitly NOT ownership proof.
    Its limit is that one login shell `exec`-ing over another is invisible to
    it, and no caller should read it as more than a narrowing.

**Neither source is trusted alone.** The server's reported `name` is a claim by
the process's host; the executable is a claim by the kernel. They must AGREE, so
a single lying source refuses rather than decides.

**Agreement is not basename equality, and assuming it was refused every pane on
a Debian-family host.** The two sources answer different questions: the server
reports what the shell was INVOKED as, the kernel reports what `/proc/<pid>/exe`
RESOLVED to. Where a registered shell is a symlink those answers differ while
both stay true — `/bin/sh` -> `dash` yields `'sh'` against `/usr/bin/dash`,
which the first cut read as a contradiction and refused. Measured: herdr roots a
pane at `$SHELL` and falls back to `/bin/sh` when it is absent, so an
interactive operator shell produced `bash` (names agree, everything passed)
while a gate invocation produced `sh` and every launch refused.

What may mediate between a name and an executable is :func:`system_shell_aliases`
— the same two host sources, read keeping the name each entry DECLARES beside
the path it resolves to. So an alias is accepted exactly when the system itself
says those two strings name one program, which NARROWS rather than relaxes: a
name the host registers for nothing never agrees, a registered name resolving to
a different executable than the kernel reports never agrees, and an empty
register mediates nothing and refuses every establish. Basename equality is
still tried first and is unchanged.

Every reader fails closed: no readable `/proc` identity is NOT an idle shell, it
is no evidence at all, and `SPECIFICATION/contracts.md` forbids treating an
unreadable backend answer as proof of an idle pane. The handlers are narrow
(`OSError`, `KeyError`) because each is a seam handling one expected failure.
"""

from __future__ import annotations

import os
import pwd
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import claude_sessions
import herdr_calls

__all__: list[str] = [
    "LOGIN_SHELL_REGISTRY",
    "RetainedShell",
    "ShellEvidence",
    "ShellIdentity",
    "ShellProof",
    "proc_shell_identity",
    "retained_shell",
    "system_login_shells",
    "system_shell_aliases",
]

# The system's own register of valid login shells. Read, never enumerated here.
LOGIN_SHELL_REGISTRY = "/etc/shells"


@dataclass(frozen=True, kw_only=True)
class ShellIdentity:
    """One process as the KERNEL describes it, not as a server reports it.

    `executable` is the resolved target of `/proc/<pid>/exe`, which a process
    cannot set about itself — unlike its `comm` or its `cmdline`, both of which
    it can. That is the whole reason this is the field the recheck compares.
    """

    pid: int
    executable: str
    starttime: str


@dataclass(frozen=True, kw_only=True)
class RetainedShell:
    """The created pane's retained shell, or why it may not be written into.

    `identity` is None on every refusal rather than carrying a partial reading,
    so a caller cannot accidentally use a refused observation as the EXPECTED
    identity on a later check and certify the comparison against itself.
    """

    identity: ShellIdentity | None
    error: str


class ShellEvidence(Protocol):
    """Read live kernel evidence about a pid, or None when it cannot be read."""

    def __call__(self, *, pid: int) -> ShellIdentity | None: ...


@dataclass(frozen=True, kw_only=True)
class ShellProof:
    """The capabilities the retained-shell proof needs, as one parameter.

    Bundled rather than threaded separately because they are never useful apart:
    kernel evidence with no registry to corroborate it cannot establish, and a
    registry with no evidence has nothing to judge.

    `shell_aliases` defaults EMPTY rather than to the host reader, so a caller
    that forgets to supply it degrades to exact name agreement — refusing an
    alias pane — instead of silently widening what authorizes a write.
    """

    evidence_of: ShellEvidence
    login_shells: frozenset[str]
    shell_aliases: frozenset[tuple[str, str]] = frozenset()


def proc_shell_identity(*, pid: int) -> ShellIdentity | None:
    """`pid`'s kernel identity from `/proc`, or None when it cannot be read.

    `Path.readlink` rather than resolving the `exe` path: a realpath of
    `/proc/<pid>/exe` returns the literal path unchanged for a process that is
    gone, which would manufacture an executable for a dead pid, while readlink
    raises. The link target is then resolved so a host where `/bin/bash`
    symlinks to `/usr/bin/bash` compares equal to the registry either way.
    """
    try:
        target = Path(f"/proc/{pid}/exe").readlink()
    except OSError:
        return None
    starttime = claude_sessions.proc_starttime(pid=pid)
    if starttime is None:
        return None
    return ShellIdentity(pid=pid, executable=str(target.resolve()), starttime=starttime)


def _declared_login_shells() -> set[str]:
    """The paths `/etc/shells` declares, UNRESOLVED.

    The declared form is kept rather than resolved in place because both callers
    need it: the resolved set answers "is this binary a login shell" and the
    alias table answers "which names does this host register that binary under",
    and the second question is unanswerable once the names are discarded.
    """
    try:
        raw = Path(LOGIN_SHELL_REGISTRY).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {
        entry
        for entry in (line.strip() for line in raw.splitlines())
        if entry and not entry.startswith("#")
    }


def _passwd_login_shell() -> set[str]:
    """The invoking user's passwd shell, UNRESOLVED, for the same reason."""
    try:
        recorded = pwd.getpwuid(os.getuid()).pw_shell
    except KeyError:
        return set()
    return {recorded} if recorded else set()


def _registered_shell_paths() -> set[str]:
    """Every path THIS HOST registers as a login shell, as declared.

    The union of `/etc/shells` and the invoking user's passwd shell, because
    either can legitimately name a shell the other omits: a host can run a shell
    that was never registered, and a registry can list shells no account uses.
    """
    return _declared_login_shells() | _passwd_login_shell()


def system_login_shells() -> frozenset[str]:
    """The login shells THIS HOST recognises, resolved to real paths.

    An empty result is possible and is deliberately not special-cased — it makes
    every establish refuse, which is the safe direction for a write.
    """
    return frozenset(str(Path(entry).resolve()) for entry in _registered_shell_paths())


def system_shell_aliases() -> frozenset[tuple[str, str]]:
    """Each NAME this host registers a login shell under, paired with its real path.

    `("sh", "/usr/bin/dash")` on a Debian-family host, from the declared
    `/bin/sh`. This is the only thing permitted to reconcile a server's reported
    name with a different kernel executable, and it is the host's own answer
    rather than an allowlist authored here — it reads the SAME two sources as
    :func:`system_login_shells`, keeping the name each entry DECLARES beside the
    path it resolves to.

    The sources are common; the READING is not shared. This function and
    :func:`system_login_shells` each call :func:`_registered_shell_paths`
    themselves, and `HerdrWriter` reaches them through two independent
    `default_factory` fields — measured: constructing one writer reads the
    register twice. Nothing holds the register still across the pair, so there is
    no atomic or shared-snapshot guarantee between the two readings. An earlier
    version of this docstring claimed the opposite — "the same single reading …
    so the two cannot disagree about what is registered" — and that is withdrawn.
    """
    return frozenset(
        (Path(entry).name, str(Path(entry).resolve())) for entry in _registered_shell_paths()
    )


def _agrees_with_reported(
    *, identity: ShellIdentity, reported: str, aliases: frozenset[tuple[str, str]]
) -> bool:
    """Whether the kernel's executable and the server's reported name name one program.

    Basename equality is the ordinary case and is answered first. Failing that,
    the reported name agrees only if this host registers a login shell under
    THAT name which resolves to EXACTLY the executable the kernel reports — both
    halves required, because matching the name alone would reinstate the
    single-source trust this whole comparison exists to prevent.
    """
    name = Path(reported).name
    if Path(identity.executable).name == name:
        return True
    return any(alias == name and resolved == identity.executable for alias, resolved in aliases)


def _server_reading(
    *, result: dict[str, object], pane_id: str
) -> tuple[herdr_calls.ForegroundProcess | None, str]:
    """The server's own account of the pane's shell, or why it is unusable.

    Separated from the evidence steps because these three refusals are about the
    REPLY — unreadable, about another pane, or about a pane whose foreground
    belongs to a child — and none of them needs to look at a process at all.
    """
    process = herdr_calls.foreground_process(result=result)
    if process is None:
        return None, f"herdr process reading for {pane_id!r} is unreadable or ambiguous"
    if process.pane_id != pane_id:
        return None, (
            f"herdr process reading describes pane {process.pane_id!r}, "
            f"not the created {pane_id!r}"
        )
    if process.process_group_id != process.shell_pid:
        return None, (
            f"{pane_id!r} is OCCUPIED: foreground group {process.process_group_id} "
            f"is not its retained shell {process.shell_pid}"
        )
    return process, ""


def retained_shell(
    *,
    result: dict[str, object],
    pane_id: str,
    expected: ShellIdentity | None,
    evidence_of: ShellEvidence,
    login_shells: frozenset[str],
    shell_aliases: frozenset[tuple[str, str]] = frozenset(),
) -> RetainedShell:
    """The pane's live idle retained shell, or why it does not authorize a write.

    `expected is None` ESTABLISHES the identity and is the only path that applies
    the login-shell corroboration; a supplied identity REQUIRES exact equality,
    which corroborates the live image against the one observed at establish and
    refuses an observed change. See the module docstring for why those two halves
    are not interchangeable, and for what the comparison does not prove — it
    neither excludes a later `exec` nor sees one that keeps the same executable.
    """
    process, unusable = _server_reading(result=result, pane_id=pane_id)
    if process is None:
        return RetainedShell(identity=None, error=unusable)
    identity = evidence_of(pid=process.shell_pid)
    if identity is None:
        return RetainedShell(
            identity=None,
            error=(
                f"no live kernel evidence for shell {process.shell_pid} in {pane_id!r}, "
                "so it cannot be shown to be the retained shell"
            ),
        )
    if not _agrees_with_reported(identity=identity, reported=process.name, aliases=shell_aliases):
        return RetainedShell(
            identity=None,
            error=(
                f"herdr calls shell {process.shell_pid} {process.name!r} while the kernel "
                f"runs {identity.executable!r}; one of the two is wrong"
            ),
        )
    if expected is None:
        return _established(identity=identity, pane_id=pane_id, login_shells=login_shells)
    if identity != expected:
        return RetainedShell(
            identity=None,
            error=(
                f"{pane_id!r} no longer holds the shell this operation created: "
                f"expected {expected}, found {identity}"
            ),
        )
    return RetainedShell(identity=identity, error="")


def _established(
    *, identity: ShellIdentity, pane_id: str, login_shells: frozenset[str]
) -> RetainedShell:
    """The first observation, corroborated against the system's own shell register."""
    if identity.executable not in login_shells:
        return RetainedShell(
            identity=None,
            error=(
                f"{pane_id!r} is rooted at {identity.executable!r}, which this host does "
                f"not register as a login shell; it is not the shell herdr created"
            ),
        )
    return RetainedShell(identity=identity, error="")
