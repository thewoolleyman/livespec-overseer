"""herdr_calls.py — the herdr OBSERVATION operations' params and replies. PURE, no I/O.

One layer above :mod:`herdr_protocol`, which owns the transport envelope, and one
below :mod:`herdr_adapter`, which owns the socket. This module knows what each
observation ASKS FOR and what its answer MEANS, and nothing else: it opens no
socket, reads no `/proc`, and makes no claim that anything it parsed is live.

Keeping it pure is what lets every fail-closed refusal below be reached without a
herdr server at all — which matters more here than it looks, because this
repository's CI container does not ship herdr, so the deterministic suite is the
only thing covering this code on that lane.

**Every shape here is MEASURED, not inferred**
(`plan/herdr-overseer/research/002-herdr-api-evidence.md`, plus the live probes
recorded in `tests/test_herdr_live_observation.py`): `pane.read` answers
`result.read.text`, `pane.list` answers `result.panes[]`, and
`pane.process_info` answers `result.process_info` with `shell_pid`,
`foreground_process_group_id` and `foreground_processes[]`.

**Reading is FAIL-CLOSED, and the required-fields gate is not enough on its own.**
`SPECIFICATION/contracts.md` forbids treating an unsupported or malformed backend
response as "proof of an idle pane". A `ReplyExpectation`'s `required_fields`
proves a member is PRESENT; it cannot prove the member is usable. So every parser
here returns `None` rather than a plausible empty value: an unreadable capture
must not become `""`, an unreadable listing must not become no panes, and an
unreadable process reading must not become an idle shell.

**The foreground process is selected by GROUP LEADERSHIP, never by list order.**
The research is explicit that an implementation must not read "arbitrary
process-list order". The entry whose `pid` equals the reported
`foreground_process_group_id` is the group leader, which is a property of the
reply rather than of its ordering, so a server that lists the leader second
resolves identically. A reply with no such entry is AMBIGUOUS, and ambiguous
evidence is unavailable — not a guess at the first entry.
"""

from __future__ import annotations

from dataclasses import dataclass

import herdr_protocol
import jsonio

__all__: list[str] = [
    "EXPECT_LIST",
    "EXPECT_PROCESS_INFO",
    "EXPECT_READ",
    "FORMAT_ANSI",
    "FORMAT_TEXT",
    "SOURCE_VISIBLE",
    "ForegroundProcess",
    "PaneRead",
    "PaneRow",
    "foreground_process",
    "list_params",
    "pane_read",
    "pane_rows",
    "process_info_params",
    "read_params",
    "visible_text",
]

# The daemon reads what a pane is SHOWING, not its scrollback: a wrap-up decision
# is about the current screen, and `recent`/`recent-unwrapped` would mix in
# historical prompts that are not on it any more.
SOURCE_VISIBLE = "visible"
FORMAT_ANSI = "ansi"
FORMAT_TEXT = "text"

EXPECT_READ = herdr_protocol.ReplyExpectation(result_type="pane_read", required_fields=("read",))
EXPECT_LIST = herdr_protocol.ReplyExpectation(result_type="pane_list", required_fields=("panes",))
EXPECT_PROCESS_INFO = herdr_protocol.ReplyExpectation(
    result_type=herdr_protocol.RESULT_TYPE_PANE_PROCESS_INFO,
    required_fields=("process_info",),
)


@dataclass(frozen=True, kw_only=True)
class PaneRow:
    """One pane as the selected server enumerates it.

    The three ids IDENTIFY the pane and are required. The two paths DESCRIBE it
    and default to empty: they are reported on every measured row, but a row
    whose identity is intact must not be discarded for lacking them, because
    discarding it would hide a real pane from the daemon.

    `foreground_cwd` is carried separately from `cwd` deliberately — the shell's
    cwd and the foreground child's cwd differ the moment anything runs, and the
    research warns against reading the former as the latter.
    """

    pane_id: str
    tab_id: str
    workspace_id: str
    cwd: str
    foreground_cwd: str
    focused: bool


@dataclass(frozen=True, kw_only=True)
class PaneRead:
    """One pane capture, together with the pane the SERVER says it describes.

    `pane_id` is carried rather than discarded because matching a reply's
    request id proves it answers THIS REQUEST, not that it describes THIS PANE —
    two different claims, and only the bound caller knows which pane it asked
    about. It is `""` when the reply echoed none, which a bound caller treats as
    unowned rather than as agreement.
    """

    pane_id: str
    text: str


@dataclass(frozen=True, kw_only=True)
class ForegroundProcess:
    """What is ACTUALLY running in a pane, beside the shell that is hosting it.

    `shell_pid` and `process_group_id` are both carried because their
    RELATIONSHIP is the reading that matters: equal means the shell itself owns
    the foreground, which is the idle case, while different means a child does.
    A caller that only saw the child's name could not tell those apart. That is
    also why both must be POSITIVE — see :func:`foreground_process`.

    `pane_id` is carried for the same reason as on :class:`PaneRead`.
    """

    pane_id: str
    shell_pid: int
    process_group_id: int
    name: str
    cmdline: str
    cwd: str


def read_params(*, pane_id: str, retain_ansi: bool) -> dict[str, object]:
    """Params for one visible-pane capture of `pane_id`.

    `strip_ansi` is the inverse of `retain_ansi` rather than an independent knob,
    because `format=ansi` with `strip_ansi=true` is a contradiction no caller
    should be able to express. Retaining styling is the default the daemon needs:
    a dim SGR is what separates a generated placeholder from typed input, so a
    capture that dropped it would make an occupied pane read as idle.
    """
    return {
        "pane_id": pane_id,
        "source": SOURCE_VISIBLE,
        "format": FORMAT_ANSI if retain_ansi else FORMAT_TEXT,
        "strip_ansi": not retain_ansi,
    }


def list_params() -> dict[str, object]:
    """Params for enumerating the addressed server's panes — there are none.

    The SERVER is selected by the socket the request is sent on, not by a
    parameter, which is why two servers with identical pane ids cannot be
    conflated by this call.
    """
    return {}


def process_info_params(*, pane_id: str) -> dict[str, object]:
    """Params for reading `pane_id`'s shell and foreground process."""
    return {"pane_id": pane_id}


def _text_at(*, obj: dict[str, object], name: str) -> str | None:
    value = obj.get(name)
    return value if isinstance(value, str) else None


def _int_at(*, obj: dict[str, object], name: str) -> int | None:
    """`obj[name]` as an int, excluding `bool`.

    `bool` is an `int` subclass, so a bare `isinstance` check would accept
    `true` as a pid of 1 — a plausible-looking process identity invented out of
    a flag.
    """
    value = obj.get(name)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _positive_int_at(*, obj: dict[str, object], name: str) -> int | None:
    """`obj[name]` as a POSITIVE int, or None.

    There is no process 0 and no negative pid, so a reply claiming one is
    malformed — and the zero/zero case is the consequential one: `shell_pid`
    equal to `foreground_process_group_id` is exactly how a pane is reported as
    idle at its prompt, so without this a malformed reply could manufacture the
    single most load-bearing reading this module produces.
    """
    value = _int_at(obj=obj, name=name)
    return value if value is not None and value > 0 else None


def pane_read(*, result: dict[str, object]) -> PaneRead | None:
    """One capture plus the pane the reply claims it describes, or None."""
    read = jsonio.as_object(value=result.get("read"))
    if read is None:
        return None
    text = _text_at(obj=read, name="text")
    if text is None:
        return None
    return PaneRead(pane_id=_text_at(obj=read, name="pane_id") or "", text=text)


def visible_text(*, result: dict[str, object]) -> str | None:
    """The captured pane text, or None when the reply does not carry one.

    The field-parser view of :func:`pane_read`, for a caller that has already
    established ownership or has no pane to establish it against.
    """
    parsed = pane_read(result=result)
    return None if parsed is None else parsed.text


def _pane_row(*, row: dict[str, object]) -> PaneRow | None:
    pane_id = _text_at(obj=row, name="pane_id")
    tab_id = _text_at(obj=row, name="tab_id")
    workspace_id = _text_at(obj=row, name="workspace_id")
    # Falsiness rather than `is None`, so an EMPTY id is refused by the same
    # check as a missing one. They are the same defect: an empty string
    # identifies nothing, and a row carrying one would enumerate a pane with no
    # identity that a caller could then try to address.
    if not pane_id or not tab_id or not workspace_id:
        return None
    return PaneRow(
        pane_id=pane_id,
        tab_id=tab_id,
        workspace_id=workspace_id,
        cwd=_text_at(obj=row, name="cwd") or "",
        foreground_cwd=_text_at(obj=row, name="foreground_cwd") or "",
        # Anything other than a literal `true` is not focus. A missing key and a
        # non-boolean value are both "not the focused pane", which is the safe
        # reading: claiming focus the server did not report would let a caller
        # act on the wrong pane.
        focused=row.get("focused") is True,
    )


def pane_rows(*, result: dict[str, object]) -> tuple[PaneRow, ...] | None:
    """Every enumerated pane, or None if ANY row is unreadable.

    All-or-nothing on purpose: a partial listing silently omits panes, and the
    daemon uses this to decide whether a pane it is bound to still exists. An
    omission would read as "the pane is gone".

    **A REPEATED pane coordinate refuses the listing** for the same reason. A
    pane id is unique within a server by construction (the research measured
    that ids repeat only BETWEEN servers, which is why the coordinate carries
    the instance), so a listing that names one twice is contradictory — and
    "does my pane still exist?" cannot be answered by two conflicting records.
    The refusal is on the repeat itself rather than on whether the two rows
    disagree, because a caller cannot know which fields a server might repeat
    consistently, and a repeated coordinate is malformed either way.
    """
    rows = jsonio.as_list(value=result.get("panes"))
    if rows is None:
        return None
    parsed: list[PaneRow] = []
    seen: set[str] = set()
    for raw in rows:
        row = jsonio.as_object(value=raw)
        if row is None:
            return None
        one = _pane_row(row=row)
        if one is None:
            return None
        if one.pane_id in seen:
            return None
        seen.add(one.pane_id)
        parsed.append(one)
    return tuple(parsed)


def _group_leader(*, processes: list[object], group_id: int) -> dict[str, object] | None:
    """The entry that OWNS `group_id`, or None when the reply does not name it.

    **A repeated pid refuses the whole reply.** One pid names one process, so a
    list claiming otherwise is self-contradictory — and two entries both
    claiming the group id defeated leader-selection entirely, resolving to
    whichever came first: `name='real'` in one order and `name='imposter'` in
    the reverse. Selecting the leader by group ownership exists precisely so
    ORDER does not decide, so a duplicate is not an edge case of that rule but
    a reply that makes it unanswerable.

    The scan reaches the end rather than returning at the first match, because
    a duplicate AFTER the leader is just as contradictory as one before it.

    **EVERY entry's identity is required to be a real pid, not just the leader's.**
    An earlier cut validated only the entry it was going to use and let an
    invalid sibling through — `pid: true`, `0`, `-1`, a string, or no `pid` at
    all — returning the leader beside it. That made a duplicate the only trigger,
    which is the wrong one: one impossible pid already means the server's process
    list cannot be trusted, and this list is what a restart interlock would read
    to prove a predecessor gone. A VALID unique sibling is untouched, because a
    pane running a pipeline legitimately reports several foreground processes.
    """
    leader: dict[str, object] | None = None
    seen: set[int] = set()
    for raw in processes:
        entry = jsonio.as_object(value=raw)
        if entry is None:
            return None
        pid = _positive_int_at(obj=entry, name="pid")
        if pid is None or pid in seen:
            return None
        seen.add(pid)
        if pid == group_id:
            leader = entry
    return leader


def foreground_process(*, result: dict[str, object]) -> ForegroundProcess | None:
    """The pane's shell plus its foreground group leader, or None if unreadable.

    See the module docstring for why the LEADER is selected rather than the first
    listed entry, and why a reply naming no leader is unavailable rather than
    approximated.
    """
    info = jsonio.as_object(value=result.get("process_info"))
    if info is None:
        return None
    shell_pid = _positive_int_at(obj=info, name="shell_pid")
    group_id = _positive_int_at(obj=info, name="foreground_process_group_id")
    processes = jsonio.as_list(value=info.get("foreground_processes"))
    if shell_pid is None or group_id is None or processes is None:
        return None
    leader = _group_leader(processes=processes, group_id=group_id)
    if leader is None:
        return None
    name = _text_at(obj=leader, name="name")
    if name is None:
        return None
    return ForegroundProcess(
        pane_id=_text_at(obj=info, name="pane_id") or "",
        shell_pid=shell_pid,
        process_group_id=group_id,
        name=name,
        cmdline=_text_at(obj=leader, name="cmdline") or "",
        cwd=_text_at(obj=leader, name="cwd") or "",
    )
