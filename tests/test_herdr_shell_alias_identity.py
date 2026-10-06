"""When a reported shell NAME and a kernel executable describe one program anyway.

Unit-level companion to `tests/test_herdr_live_alias_shell_launch.py`, which
drives the same defect against real herdr servers. That file proves the
behaviour on a live pane; this one pins the rule, including the shapes a healthy
host will not produce on demand.

**The rule.** The retained-shell proof requires the server's reported name and
the kernel's resolved executable to describe the same program, so that one lying
source refuses rather than decides. Basename equality answers that in the
ordinary case and is still the first thing tried. It is not the only truthful
case: a host may register a login shell under a name that is a SYMLINK to the
real binary, and then the two sources answer different questions truthfully —
the server reports what the shell was INVOKED as, the kernel reports what
`/proc/<pid>/exe` RESOLVED to. On a Debian-family host `/bin/sh` -> `dash` makes
that `'sh'` against `/usr/bin/dash`.

**What may mediate between them is the host's own shell register, and only
that.** `system_shell_aliases` pairs each name `/etc/shells` and the invoking
user's passwd entry DECLARE with the path that name resolves to, so an alias is
accepted exactly when the system itself says those two strings name one program.
Three properties make that a narrowing rather than a relaxation, and each has a
test below:

  - a name the host registers for NOTHING never agrees, however plausible;
  - a registered name that resolves to a DIFFERENT executable than the one the
    kernel reports never agrees — matching the name alone would reinstate the
    single-source trust the whole rule exists to prevent;
  - an EMPTY register mediates nothing, which refuses every establish. That is
    deliberately not special-cased: for a write, refusing is the safe direction.

Everything the agreement rule previously refused it still refuses. The two
cases that carry the most weight — an `exec` replacement at the same pid, and a
pane whose foreground belongs to a child — are re-driven here against an ALIAS
shell, because a repair that widened agreement could have widened them too.

The live reader is exercised against the host's real `/etc/shells` rather than a
fixture, because a hand-authored pairing substituted here would prove only that
this file agrees with itself.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import pytest

__all__: list[str] = []

PANE = "w1:p2"
OTHER_PANE = "w1:p1"
SHELL_PID = 4100
CHILD_PID = 4200
DASH = "/usr/bin/dash"
BASH = "/usr/bin/bash"
SLEEP = "/usr/bin/sleep"
STARTTIME = "164433575"
# The pairing a Debian-family host publishes: `/bin/sh` and `/usr/bin/sh` are
# both registered names for the dash binary.
SH_ALIASES = frozenset({("sh", DASH), ("bash", BASH)})
LOGIN_SHELLS = frozenset({DASH, BASH})


def _module() -> Any:
    """The shell-identity collaborator, imported INSIDE the test body."""
    return importlib.import_module("_herdr_shell_identity")


def _reply(
    *,
    pane_id: str = PANE,
    shell_pid: int = SHELL_PID,
    group_id: int | None = None,
    name: str = "sh",
) -> dict[str, object]:
    """A measured `pane.process_info` result, idle unless a group id is given."""
    leader = shell_pid if group_id is None else group_id
    return {
        "process_info": {
            "pane_id": pane_id,
            "shell_pid": shell_pid,
            "foreground_process_group_id": leader,
            "foreground_processes": [{"pid": leader, "name": name, "cmdline": name, "cwd": "/tmp"}],
        }
    }


def _evidence(*, module: Any, executable: str, starttime: str = STARTTIME) -> Any:
    """A live-evidence seam answering for any pid with the given executable."""

    def read(*, pid: int) -> Any:
        return module.ShellIdentity(pid=pid, executable=executable, starttime=starttime)

    return read


def _establish(
    *,
    module: Any,
    reply: dict[str, object],
    executable: str,
    aliases: frozenset[tuple[str, str]] = SH_ALIASES,
) -> Any:
    return module.retained_shell(
        result=reply,
        pane_id=PANE,
        expected=None,
        evidence_of=_evidence(module=module, executable=executable),
        login_shells=LOGIN_SHELLS,
        shell_aliases=aliases,
    )


def test_the_alias_table_is_read_from_the_host_not_listed_in_this_repo():
    """Each name `/etc/shells` declares is paired with what that name resolves to.

    Asserted against the host's own file so a hand-authored pairing substituted
    later would not satisfy it. Skipped rather than faked where the host carries
    no `/etc/shells`, because inventing one here would defeat the point.
    """
    module = _module()
    registry = Path("/etc/shells")
    if not registry.is_file():
        pytest.skip("this host carries no /etc/shells to read")

    aliases = module.system_shell_aliases()

    declared = [
        line.strip()
        for line in registry.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert declared, "fixture precondition: /etc/shells names at least one shell"
    expected = {(Path(entry).name, os.path.realpath(entry)) for entry in declared}
    assert expected <= aliases, f"{expected - aliases} declared in /etc/shells but not paired"
    assert module.system_login_shells() == {resolved for _, resolved in aliases}, (
        "the resolved login-shell set and the alias table must come from one reading, "
        "so they cannot disagree about what the host registers"
    )


def test_a_registered_alias_name_agrees_with_the_binary_it_resolves_to():
    """The regression at rule level: `sh` reported, `/usr/bin/dash` on the kernel side."""
    module = _module()

    established = _establish(module=module, reply=_reply(name="sh"), executable=DASH)

    assert established.error == "", established.error
    assert established.identity == module.ShellIdentity(
        pid=SHELL_PID, executable=DASH, starttime=STARTTIME
    )


def test_exact_name_agreement_is_unchanged_and_needs_no_alias():
    """The ordinary case still answers first, and an empty table does not block it."""
    module = _module()

    established = _establish(
        module=module, reply=_reply(name="bash"), executable=BASH, aliases=frozenset()
    )

    assert established.error == "", established.error
    assert established.identity is not None


def test_a_name_the_host_registers_for_nothing_never_agrees():
    """`sleep` is not a shell name on any host here, however the kernel answers."""
    module = _module()

    established = _establish(module=module, reply=_reply(name="sleep"), executable=DASH)

    assert established.identity is None
    assert "sleep" in established.error, established.error


def test_a_registered_name_resolving_to_another_binary_never_agrees():
    """The table names `sh`, but this pane is not running what `sh` resolves to.

    Matching the name alone would accept this, which is exactly the
    single-source trust the agreement rule exists to prevent.
    """
    module = _module()

    established = _establish(module=module, reply=_reply(name="sh"), executable=SLEEP)

    assert established.identity is None
    assert SLEEP in established.error, established.error


def test_an_empty_register_mediates_nothing_and_refuses():
    """A host that declines to answer leaves the disagreement standing."""
    module = _module()

    established = _establish(
        module=module, reply=_reply(name="sh"), executable=DASH, aliases=frozenset()
    )

    assert established.identity is None
    assert "one of the two is wrong" in established.error, established.error


def test_the_recheck_still_refuses_an_exec_replacement_of_an_alias_shell():
    """The corroborating half is untouched by alias agreement.

    The established identity is a dash shell reached through the `sh` alias;
    the recheck finds `sleep` at the same pid. The reported name still says
    `sh`, so an agreement rule that had become name-only would wave this
    through — and this is the defect the retained-shell gate was built for.
    """
    module = _module()
    established = module.ShellIdentity(pid=SHELL_PID, executable=DASH, starttime=STARTTIME)

    def recheck(*, executable: str, starttime: str = STARTTIME) -> Any:
        return module.retained_shell(
            result=_reply(name="sh"),
            pane_id=PANE,
            expected=established,
            evidence_of=_evidence(module=module, executable=executable, starttime=starttime),
            login_shells=LOGIN_SHELLS,
            shell_aliases=SH_ALIASES,
        )

    unchanged = recheck(executable=DASH)
    exec_replaced = recheck(executable=SLEEP)
    reused_pid = recheck(executable=DASH, starttime="999999999")

    assert unchanged.error == "", unchanged.error
    assert unchanged.identity == established
    assert exec_replaced.identity is None, "an exec-replaced alias shell must not recheck clean"
    assert reused_pid.identity is None, "a different start time at the same pid is not the shell"


def test_an_occupied_or_foreign_alias_pane_is_still_refused_before_any_evidence():
    """The reply-level refusals are unchanged, re-driven against an alias shell."""
    module = _module()

    occupied = _establish(
        module=module, reply=_reply(name="sh", group_id=CHILD_PID), executable=DASH
    )
    foreign = _establish(
        module=module, reply=_reply(name="sh", pane_id=OTHER_PANE), executable=DASH
    )

    assert occupied.identity is None and "OCCUPIED" in occupied.error, occupied.error
    assert foreign.identity is None, foreign.error


def test_an_alias_shell_the_host_does_not_register_as_a_login_shell_is_refused():
    """Agreement is not establishment: the narrowing half still has to pass.

    A name and an executable can agree perfectly about a program the host does
    not register as a login shell, and the establish must still refuse it.
    """
    module = _module()

    established = _establish(
        module=module,
        reply=_reply(name="sh"),
        executable=DASH,
        aliases=frozenset({("sh", DASH)}),
    )
    assert established.error == "", "control: with dash registered this establishes"

    refused = module.retained_shell(
        result=_reply(name="sh"),
        pane_id=PANE,
        expected=None,
        evidence_of=_evidence(module=module, executable=DASH),
        login_shells=frozenset({BASH}),
        shell_aliases=frozenset({("sh", DASH)}),
    )

    assert refused.identity is None
    assert "login shell" in refused.error, refused.error


def test_the_writer_resolves_its_alias_table_from_the_host_by_default():
    """The wiring, pinned: an unwired default would silently refuse every alias pane.

    The defect this file exists for is invisible to a fixture that injects its
    own table, so the DEFAULT is what has to come from the host. Asserted as an
    equality against the reader rather than as mere non-emptiness, because a
    table built from some other source would also be non-empty.
    """
    writer_module = importlib.import_module("herdr_write")
    module = _module()

    writer = writer_module.HerdrWriter()

    assert (
        writer.shell_aliases == module.system_shell_aliases()
    ), "HerdrWriter must default to the host's own shell register"
    assert writer.login_shells == module.system_login_shells()
