"""An interrupted herdr layout change stays UNCERTAIN, and is never retried.

`split_window_top` is three bounded mutations in sequence, so it has three
distinct write boundaries and a failure can land on any of them. This file pins
what the caller is told in each case, and — the part that matters more — that
nothing is resent.

**Why a repeat would be worse than the failure.** A swap that was sent and went
unanswered may well have landed; repeating it would swap the panes BACK, so the
daemon would end up below the session it supervises while every call reported
success. A launch that went unanswered may have started the command; repeating
it would run the command twice. `SPECIFICATION/contracts.md` permits replaying
only a failure "proven to precede" the effect, and past the write boundary no
such proof exists. The honest answer is an outcome that says so.

**These are CONTROLLED socket peers, not a herdr server**, because the
conditions here are invalid-protocol boundaries: a server that accepts a
request and then dies without answering is exactly what a real timeout looks
like from the client side, and it cannot be provoked reliably on a healthy
server. The behaviour against a REAL server is proven in
`tests/test_herdr_live_layout.py`; this file covers what that one cannot stage.

**Scope note, stated rather than implied:** the write-boundary RULE itself
(`RpcOutcome.effect_unknown`, and the rejections that feed it) carries its own
Red-first evidence from the transport and bounds cycles. What this file adds is
the LAYOUT sequence's use of that rule across its three stages, and its bytes
were authored after `split_window_top` — it is postimplementation coverage of
those branches, not original Red-first evidence for them.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

PANE = "w1:p1"
CREATED = "w1:p2"
SPLIT_RESULT: dict[str, object] = {"type": "pane_info", "pane": {"pane_id": CREATED}}
# A swap reply must say it CHANGED something and echo the panes it moved; see
# `tests/test_herdr_layout_exact_target.py` for the measured refusal shapes that
# arrive inside an otherwise successful envelope.
SWAP_RESULT: dict[str, object] = {
    "type": "pane_swap",
    "swap": {"changed": True, "source_pane_id": PANE, "target_pane_id": CREATED},
}
OK_RESULT: dict[str, object] = {"type": "ok"}


def _modules() -> tuple[Any, Any]:
    return (
        importlib.import_module("herdr_write_calls"),
        importlib.import_module("herdr_write"),
    )


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _envelope(*, result: dict[str, object], request_id: str) -> bytes:
    return json.dumps({"id": request_id, "result": result}).encode("utf-8")


def _answer_scripted(
    *,
    conn: socket.socket,
    reply: dict[str, object] | None,
    request_id: str,
    received: list[bytes],
) -> None:
    """Read one request, record it, and answer it only when `reply` is not None.

    `reply is None` models a server that COMMITTED to the request — it read the
    bytes — and then went away without answering, which is the client-side
    shape of a real timeout and the condition the uncertainty rule exists for.
    """
    conn.settimeout(5.0)
    buffered = b""
    try:
        while not buffered.endswith(b"\n"):
            chunk = conn.recv(65536)
            if not chunk:
                break
            buffered += chunk
    except OSError:
        return
    if not buffered:
        return
    received.append(buffered)
    if reply is None:
        return
    try:
        conn.sendall(_envelope(result=reply, request_id=request_id) + b"\n")
    except OSError:
        return


def _serve_script(*, address: Path, script: list[dict[str, object] | None]) -> list[bytes]:
    """A REAL AF_UNIX peer answering one scripted reply per connection.

    A `None` entry is a server that ACCEPTS the request, reads it, and then
    closes WITHOUT answering — the client-side shape of a committed request
    that went unanswered. The returned list records every request that actually
    crossed the socket, which is what makes "nothing was resent" assertable
    rather than merely plausible.
    """
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(8)
    received: list[bytes] = []

    def run() -> None:
        listener.settimeout(5.0)
        for index, reply in enumerate(script):
            try:
                conn, _ = listener.accept()
            except OSError:
                break
            with conn:
                _answer_scripted(
                    conn=conn,
                    reply=reply,
                    request_id=f"rq-{index + 1}",
                    received=received,
                )
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return received


def _live_target(*, identity: Any, address: Path) -> Any:
    """A qualified target naming THIS process as the server generation."""
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return identity.HerdrPaneTarget(
        socket_path=str(address),
        server_pid=os.getpid(),
        server_starttime=starttime,
        pane_id=PANE,
    )


def _ids() -> Iterator[str]:
    return (f"rq-{index}" for index in range(1, 64))


def _split_top(*, address: Path) -> Any:
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    return writer_module.HerdrWriter(request_ids=_ids()).split_window_top(
        target=_live_target(identity=identity, address=address),
        cwd="/tmp",
        command="sleep 120",
        ratio=0.25,
    )


def _methods(*, received: list[bytes]) -> list[str]:
    return [str(json.loads(raw)["method"]) for raw in received]


def test_a_split_refused_before_the_write_is_certain_and_creates_nothing(*, socket_dir: Path):
    """Nothing listening means nothing was attempted, so the outcome is CERTAIN.

    This is the one layout failure that is safe to reconsider, and keeping it
    distinguishable from the uncertain ones is the whole point of the flag.
    """
    outcome = _split_top(address=socket_dir / "absent.sock")

    assert outcome.ok is False
    assert outcome.pane_id == ""
    assert outcome.effect_unknown is False, outcome.error


def test_a_split_whose_reply_does_not_name_a_pane_is_uncertain(*, socket_dir: Path):
    """An ACKNOWLEDGED split probably made a pane; an unnamable one cannot be used.

    The server answered, so something very likely happened — but the caller has
    no id to address, so it can neither continue the sequence nor report which
    pane to look at. Reporting that as a clean refusal would invite a retry that
    created a SECOND pane.
    """
    address = socket_dir / "h.sock"
    received = _serve_script(address=address, script=[{"type": "pane_info", "pane": {}}])

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert outcome.pane_id == ""
    assert outcome.effect_unknown is True, outcome.error
    assert _methods(received=received) == ["pane.split"], "the sequence must stop at the split"


def test_an_unanswered_swap_stays_uncertain_and_is_not_resent(*, socket_dir: Path):
    """The measured hazard: a swap that may have landed must NOT be repeated.

    The new pane's id is still reported, because the split did succeed and that
    pane is exactly what an operator has to go and look at.
    """
    address = socket_dir / "h.sock"
    received = _serve_script(address=address, script=[SPLIT_RESULT, None, OK_RESULT])

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is True, outcome.error
    assert _methods(received=received) == [
        "pane.split",
        "pane.swap",
    ], "the swap must not be resent, and the launch must not follow it"


def test_an_unanswered_launch_stays_uncertain_and_is_not_resent(*, socket_dir: Path):
    """A command that may already be running must not be started a second time."""
    address = socket_dir / "h.sock"
    received = _serve_script(address=address, script=[SPLIT_RESULT, SWAP_RESULT, None, OK_RESULT])

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is True, outcome.error
    assert _methods(received=received) == [
        "pane.split",
        "pane.swap",
        "pane.send_input",
    ], "the launch must not be resent"


def test_a_fully_answered_sequence_reports_the_new_pane_and_no_uncertainty(*, socket_dir: Path):
    """The positive control, so the assertions above cannot pass by never working."""
    address = socket_dir / "h.sock"
    received = _serve_script(address=address, script=[SPLIT_RESULT, SWAP_RESULT, OK_RESULT])

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is False
    assert _methods(received=received) == ["pane.split", "pane.swap", "pane.send_input"]


def test_an_unnamable_pane_id_is_refused_whatever_shape_it_arrives_in(*, socket_dir: Path):
    """`new_pane_id` is fail-closed on every non-usable shape, not just a missing key.

    An empty string and a non-string are both things a caller could otherwise
    address a swap at, so each has to be rejected as firmly as an absent member.
    """
    calls_module, _writer = _modules()

    assert calls_module.new_pane_id(result={"pane": {"pane_id": CREATED}}) == CREATED
    assert calls_module.new_pane_id(result={}) is None
    assert calls_module.new_pane_id(result={"pane": "not an object"}) is None
    assert calls_module.new_pane_id(result={"pane": {"pane_id": ""}}) is None
    assert calls_module.new_pane_id(result={"pane": {"pane_id": 5}}) is None


def test_an_unreadable_swap_member_is_refused_rather_than_assumed_successful(*, socket_dir: Path):
    """`required_fields` proves `swap` is PRESENT; it cannot prove it is usable.

    The expectation gate admits a `swap` of any JSON type, so a reply carrying
    a string there reaches the reader. Treating that as a completed swap would
    launch the command into a pane that was never moved — the same end state as
    the measured `changed: false` refusals, reached by a different route.
    """
    calls_module, _writer = _modules()
    readable = {"changed": True, "source_pane_id": PANE, "target_pane_id": CREATED}

    assert (
        calls_module.swap_refusal(
            result={"swap": readable}, source_pane_id=PANE, target_pane_id=CREATED
        )
        == ""
    )
    assert calls_module.swap_refusal(
        result={"swap": "not an object"}, source_pane_id=PANE, target_pane_id=CREATED
    )
    assert calls_module.swap_refusal(result={}, source_pane_id=PANE, target_pane_id=CREATED)


def test_the_launch_is_atomic_while_the_paste_is_not(*, socket_dir: Path):
    """The two text-delivering shapes differ exactly where they must.

    A launch submits (`keys: ["Enter"]`) because a known shell command has no
    observe step; a paste does not (`keys: []`) because a supervised agent's
    payload must be seen before it runs. Pinning both here keeps a future
    simplification from collapsing them into one call.
    """
    calls_module, _writer = _modules()

    assert calls_module.launch_params(pane_id=PANE, command="sleep 120") == {
        "pane_id": PANE,
        "text": "sleep 120",
        "keys": ["Enter"],
    }
    assert calls_module.paste_params(pane_id=PANE, text="sleep 120") == {
        "pane_id": PANE,
        "text": "sleep 120",
        "keys": [],
    }
    # `target_pane_id`, NOT `pane_id`: herdr does not alias them and ignores
    # unknown members, so the wrong key silently splits the FOCUSED pane.
    assert calls_module.split_down_params(pane_id=PANE, cwd="/tmp", ratio=0.25) == {
        "target_pane_id": PANE,
        "direction": "down",
        "ratio": 0.25,
        "cwd": "/tmp",
        "focus": False,
    }
    assert calls_module.swap_params(source_pane_id=PANE, target_pane_id=CREATED) == {
        "source_pane_id": PANE,
        "target_pane_id": CREATED,
    }


def test_an_input_write_reports_its_own_certainty(*, socket_dir: Path):
    """A paste and an Enter carry the same write-boundary rule the layout does."""
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    address = socket_dir / "h.sock"
    received = _serve_script(address=address, script=[OK_RESULT, None])
    writer = writer_module.HerdrWriter(request_ids=_ids())
    target = _live_target(identity=identity, address=address)

    delivered = writer.bracketed_paste(target=target, text="ONE\nTWO")
    unanswered = writer.send_enter(target=target)

    assert delivered.ok is True and delivered.effect_unknown is False, delivered.error
    assert unanswered.ok is False and unanswered.effect_unknown is True
    assert _methods(received=received) == ["pane.send_input", "pane.send_input"]
