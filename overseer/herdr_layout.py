"""herdr_layout.py — placing a new retained-shell herdr pane ABOVE a supervised one.

Split out of :mod:`herdr_write` along the seam between its two concerns.
:mod:`herdr_write` DELIVERS input to a pane that already exists — one bounded
request, no question about which pane it is. This module CONSTRUCTS a pane and
then has to prove, before writing anything into it, that the pane it is about to
write to is the one it meant to make. Those are different jobs with different
failure modes, and the proving is most of the code here.

**Why so much proof for one split.** Herdr supports only `right` and `down`
splits, so "above" is a split followed by a swap, and every step answers with a
CLAIM the adapter would otherwise take at face value. Two of those claims were
measured to be dangerous when trusted:

  - `pane.split` ignores unknown members, so addressing it wrongly silently
    splits the FOCUSED pane and reports ordinary success.
  - `pane.swap` reports its refusals INSIDE a successful envelope
    (`{"changed": false, "reason": "cross_tab"}`), so the expectation gate
    passes them.

And a split acknowledgement naming the ORIGINAL pane as the pane it created was
reproduced driving a self-swap followed by a daemon command pasted into the live
supervised agent. That is the invariant this module exists to hold: the command
goes into a pane that is provably NEW, provably in the target's tab, and
provably above the target — or it is not sent at all.

The requester is taken as a :class:`BoundedRequests` protocol rather than a
concrete writer so this module owns no socket, no deadline and no peer policy;
:mod:`herdr_transport` owns those, and :class:`herdr_write.HerdrWriter` supplies
them. Each step is independently peer-validated by that requester, so a server
generation replaced midway cannot receive the remainder of the sequence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import herdr_calls
import herdr_identity
import herdr_protocol
import herdr_transport
import herdr_write_calls

__all__: list[str] = [
    "DEFAULT_TOP_RATIO",
    "BoundedRequests",
    "LayoutOutcome",
    "place_above",
]

# The share of the column the new TOP pane takes by default, matching
# `overseer-start`'s tmux-side `_DAEMON_PANE_HEIGHT_PERCENT` intent: the daemon
# pane carries the table plus the NEEDS YOU block, the supervised pane is a
# prompt. Callers that want a different split pass `ratio`.
DEFAULT_TOP_RATIO = 0.66


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


@dataclass(frozen=True, kw_only=True)
class LayoutOutcome:
    """A layout mutation's result, naming the pane it created when it got that far.

    `pane_id` is reported even on a FAILED outcome whenever a TRUSTWORTHY new
    pane was identified, because a partially-applied layout is exactly the state
    a caller has to re-observe: the pane exists, and the step that failed
    afterwards did not un-create it. It is deliberately EMPTY when the split's
    own account of what it created was refused — the only id on offer in that
    case is one this module has just declined to believe.
    """

    ok: bool
    pane_id: str
    error: str
    effect_unknown: bool


def place_above(
    *,
    requester: BoundedRequests,
    target: herdr_identity.HerdrPaneTarget,
    cwd: str,
    command: str,
    ratio: float = DEFAULT_TOP_RATIO,
) -> LayoutOutcome:
    """Run `command` in a new retained-shell pane placed ABOVE `target`.

    Enumerate, split, re-enumerate, swap, re-measure, launch. `target` keeps its
    pane id, its shell and its focus throughout; the swap moves rectangles, not
    identities.

    **No step is retried.** Each mutation is its own write boundary, so one that
    was sent and went unanswered leaves `effect_unknown` set and the layout in a
    state only re-observation can resolve. Repeating a swap that may have landed
    would undo it, and repeating a launch would run the command twice;
    `SPECIFICATION/contracts.md` forbids resubmitting past that boundary.
    """
    owned, ownership_error = _owned_panes(requester=requester, target=target)
    if ownership_error:
        # Refused BEFORE the split, so nothing was created and nothing is
        # uncertain: the caller named a pane this server does not own.
        return LayoutOutcome(ok=False, pane_id="", error=ownership_error, effect_unknown=False)
    split = requester.request(
        target=target,
        method=herdr_write_calls.SPLIT_METHOD,
        params=herdr_write_calls.split_down_params(pane_id=target.pane_id, cwd=cwd, ratio=ratio),
        expect=herdr_write_calls.EXPECT_PANE_INFO,
    )
    if not split.ok:
        return LayoutOutcome(
            ok=False, pane_id="", error=split.error, effect_unknown=split.effect_unknown
        )
    created, creation_error = _proven_new_pane(
        requester=requester, target=target, result=split.result, owned=owned
    )
    if creation_error:
        # The split was ACKNOWLEDGED, so a pane probably exists; it simply
        # cannot be trusted or addressed. That is an uncertain mutation.
        return LayoutOutcome(ok=False, pane_id="", error=creation_error, effect_unknown=True)
    return _raise_above_and_launch(
        requester=requester, target=target, created=created, command=command
    )


def _raise_above_and_launch(
    *,
    requester: BoundedRequests,
    target: herdr_identity.HerdrPaneTarget,
    created: str,
    command: str,
) -> LayoutOutcome:
    """Swap `created` above `target`, PROVE it landed, and only then launch.

    Everything here already knows `created` is a real, new, correctly-placed
    pane; everything before it was establishing that.
    """
    swap = requester.request(
        target=target,
        method=herdr_write_calls.SWAP_METHOD,
        params=herdr_write_calls.swap_params(source_pane_id=target.pane_id, target_pane_id=created),
        expect=herdr_write_calls.EXPECT_PANE_SWAP,
    )
    if not swap.ok:
        return LayoutOutcome(
            ok=False, pane_id=created, error=swap.error, effect_unknown=swap.effect_unknown
        )
    refusal = herdr_write_calls.swap_refusal(
        result=swap.result, source_pane_id=target.pane_id, target_pane_id=created
    ) or _placement_refusal(requester=requester, target=target, created=created)
    if refusal:
        # Either herdr said it moved nothing, or the rectangles say it did not.
        # Both are REFUSALS rather than uncertainties — the server answered —
        # and both leave the new pane below the target, where launching the
        # command would hide it from the operator.
        return LayoutOutcome(ok=False, pane_id=created, error=refusal, effect_unknown=False)
    launch = requester.request(
        target=target,
        method=herdr_write_calls.PASTE_METHOD,
        params=herdr_write_calls.launch_params(pane_id=created, command=command),
        expect=herdr_write_calls.EXPECT_OK,
    )
    if not launch.ok:
        return LayoutOutcome(
            ok=False, pane_id=created, error=launch.error, effect_unknown=launch.effect_unknown
        )
    return LayoutOutcome(ok=True, pane_id=created, error="", effect_unknown=False)


def _owned_panes(
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


def _proven_new_pane(
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
    rows, error = _owned_panes(requester=requester, target=target)
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


def _placement_refusal(
    *, requester: BoundedRequests, target: herdr_identity.HerdrPaneTarget, created: str
) -> str:
    """Why the live geometry does not show `created` above `target`, or `""`.

    The last proof before the command is written, and the only one taken from
    the rectangles themselves. A swap can report success and leave the panes
    where they were; launching on that report alone would put the daemon beneath
    the session it supervises.
    """
    layout = requester.request(
        target=target,
        method=herdr_write_calls.LAYOUT_METHOD,
        params=herdr_write_calls.layout_params(pane_id=target.pane_id),
        expect=herdr_write_calls.EXPECT_LAYOUT,
    )
    if not layout.ok:
        return f"the new pane's placement could not be verified: {layout.error}"
    tops = herdr_write_calls.pane_tops(result=layout.result)
    if tops is None:
        return "herdr layout reply is unreadable, so the placement is unproven"
    if created not in tops or target.pane_id not in tops:
        return f"herdr layout does not place both {created!r} and {target.pane_id!r}"
    if tops[created] >= tops[target.pane_id]:
        return (
            f"herdr left {created!r} at row {tops[created]}, not above "
            f"{target.pane_id!r} at row {tops[target.pane_id]}"
        )
    return ""
