"""_herdr_layout_proofs.py — the LIVE EVIDENCE a herdr layout change rests on.

Split out of :mod:`herdr_layout` along the seam between its two concerns.
:mod:`herdr_layout` ORDERS the mutations — split, swap, launch — and decides what
each failure means to a caller. This module answers the questions those decisions
are made from, and every one of them has the same shape: a claim the server has
already made, re-asked of the live terminal.

That is why the proving is a concern of its own rather than a detail of the
sequence. Each function here exists because one specific acknowledgement was
measured to be untrustworthy when believed:

  - `pane.split` ignores unknown members, so a wrongly-addressed split silently
    splits the FOCUSED pane and reports ordinary success — hence
    :func:`owned_panes` recording what existed BEFORE, and
    :func:`proven_new_pane` refusing any id that is the original or a
    pre-existing neighbour.
  - a split acknowledgement naming the ORIGINAL pane was reproduced driving a
    self-swap and a daemon command pasted into the live supervised agent — hence
    the tab membership check being taken from a fresh enumeration rather than
    from the reply.
  - a swap can report success and leave the rectangles where they were — hence
    :func:`placement_refusal` reading the geometry itself.
  - a pane that is correctly placed can still have acquired a foreground child
    before anything is written to it — hence :func:`retained_shell`, which is
    about PROCESSES rather than geometry and is the only question here that the
    layout cannot answer at all.

The members are PUBLIC because they cross a module boundary; the module is
private because it is a collaborator of one façade, exactly as the
`_registry_*` and `_supervisor_*` groups are. Nothing here mutates anything: a
proof that cannot be completed is a named refusal, never an assumed success.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

import herdr_calls
import herdr_identity
import herdr_protocol
import herdr_transport
import herdr_write_calls

__all__: list[str] = [
    "BoundedRequests",
    "owned_panes",
    "placement_refusal",
    "proven_new_pane",
    "retained_shell",
]


class BoundedRequests(Protocol):
    """The one capability this module needs: a bounded, peer-validated request.

    A protocol rather than an import of the concrete writer, so the layout
    sequence can be reasoned about without the socket, and so neither module
    has to reach into the other's privates.
    """

    def request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome: ...


def owned_panes(
    *, requester: BoundedRequests, target: herdr_identity.HerdrPaneTarget
) -> tuple[tuple[herdr_calls.PaneRow, ...], str]:
    """The server's live pane rows, having proved `target` is among them.

    This runs BEFORE the split for two reasons. It establishes that the
    coordinate names a pane this generation actually owns — every later claim
    about that pane is unverifiable otherwise — and it records which panes
    already existed, which is the only way to tell a genuinely new pane from one
    the server merely pointed at.
    """
    listing = requester.request(
        target=target,
        method=herdr_protocol.METHOD_PANE_LIST,
        params=herdr_calls.list_params(),
        expect=herdr_calls.EXPECT_LIST,
    )
    if not listing.ok:
        return (), listing.error
    rows = herdr_calls.pane_rows(result=listing.result)
    if rows is None:
        return (), "herdr pane listing is unreadable"
    if not any(row.pane_id == target.pane_id for row in rows):
        return (), f"herdr server does not own pane {target.pane_id!r}"
    return rows, ""


def proven_new_pane(
    *,
    requester: BoundedRequests,
    target: herdr_identity.HerdrPaneTarget,
    result: dict[str, object],
    owned: tuple[herdr_calls.PaneRow, ...],
) -> tuple[str, str]:
    """The created pane id, proven NEW and in the target's tab, or why not.

    Three separate claims, none of which the acknowledgement can settle on its
    own: that a pane was named, that the named pane is neither the original nor
    a pre-existing neighbour, and that it really exists in the target's tab. The
    last is taken from a fresh enumeration rather than from the reply, because a
    reply that is wrong about which pane it made is equally capable of being
    wrong about where it made it.
    """
    created = herdr_write_calls.new_pane_id(result=result)
    if created is None:
        return "", "herdr split reply does not name the pane it created"
    refusal = herdr_write_calls.created_pane_refusal(
        created=created,
        original=target.pane_id,
        known=frozenset(row.pane_id for row in owned),
    )
    if refusal:
        return "", refusal
    rows, error = owned_panes(requester=requester, target=target)
    if error:
        return "", f"the new pane could not be verified: {error}"
    expected = next((row.tab_id for row in rows if row.pane_id == target.pane_id), "")
    placed = next((row for row in rows if row.pane_id == created), None)
    if placed is None:
        return "", f"herdr does not list {created!r} as a live pane after the split"
    if placed.tab_id != expected:
        return "", (
            f"herdr created {created!r} in tab {placed.tab_id!r}, "
            f"not the target's tab {expected!r}"
        )
    return created, ""


def placement_refusal(
    *, requester: BoundedRequests, target: herdr_identity.HerdrPaneTarget, created: str
) -> tuple[str, bool]:
    """Why the geometry does not show `created` above `target`, and whether that is UNKNOWN.

    The last structural proof before the command is written, and the only one
    taken from the rectangles themselves. A swap can report success and leave the
    panes where they were; launching on that report alone would put the daemon
    beneath the session it supervises.

    **The second member distinguishes "unproven" from "disproven", and they are
    not the same state.** This runs only after a swap whose acknowledgement was
    believed, so the panes have very likely already been exchanged. A placement
    read that is refused, unparsable, or missing one of the two panes therefore
    leaves the mutation UNRESOLVED — the rectangles are the evidence, and the
    evidence did not arrive. A read that SUCCEEDS and shows the created pane at
    or below the target is the opposite: a fully observed layout, known rather
    than open, however unwelcome the answer is. Reporting that one as unresolved
    would turn the flag into "the call failed" and destroy the only distinction
    it carries.
    """
    layout = requester.request(
        target=target,
        method=herdr_write_calls.LAYOUT_METHOD,
        params=herdr_write_calls.layout_params(pane_id=target.pane_id),
        expect=herdr_write_calls.EXPECT_LAYOUT,
    )
    if not layout.ok:
        return f"the new pane's placement could not be verified: {layout.error}", True
    tops = herdr_write_calls.pane_tops(result=layout.result)
    if tops is None:
        return "herdr layout reply is unreadable, so the placement is unproven", True
    if created not in tops or target.pane_id not in tops:
        return f"herdr layout does not place both {created!r} and {target.pane_id!r}", True
    if tops[created] >= tops[target.pane_id]:
        return (
            f"herdr left {created!r} at row {tops[created]}, not above "
            f"{target.pane_id!r} at row {tops[target.pane_id]}"
        ), False
    return "", False


def retained_shell(
    *,
    requester: BoundedRequests,
    target: herdr_identity.HerdrPaneTarget,
    created: str,
    expected_shell_pid: int | None,
) -> herdr_write_calls.RetainedShell:
    """FRESH process evidence that `created` is an idle retained shell, or why not.

    Addressed at `created` through the same bounded, peer-validated path as every
    mutation, so the reading is taken from the exact server generation the
    coordinate names rather than from whichever server now answers on that
    socket. A read this one cannot complete is a refusal, never an idle shell:
    `SPECIFICATION/contracts.md` forbids treating an unsupported or malformed
    backend response as proof of an idle pane, and that prohibition is at its
    sharpest here, where the next step writes a command plus Enter.
    """
    reading = requester.request(
        target=target,
        method=herdr_protocol.METHOD_PANE_PROCESS_INFO,
        params=herdr_calls.process_info_params(pane_id=created),
        expect=herdr_calls.EXPECT_PROCESS_INFO,
    )
    if not reading.ok:
        return herdr_write_calls.RetainedShell(
            shell_pid=0,
            error=f"the new pane's retained shell could not be read: {reading.error}",
        )
    return herdr_write_calls.retained_shell(
        result=reading.result, pane_id=created, expected_shell_pid=expected_shell_pid
    )
