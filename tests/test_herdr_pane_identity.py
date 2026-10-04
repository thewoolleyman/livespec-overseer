"""Backend-qualified terminal coordinates for the herdr pane backend.

`SPECIFICATION/contracts.md` requires a durable terminal coordinate to
distinguish backend, backend INSTANCE and exact pane, "so equal names or pane ids
on different backends or herdr servers cannot alias", while an UNQUALIFIED legacy
value keeps its tmux meaning and "MUST NOT be reinterpreted as a herdr target".

The aliasing hazard is measured, not hypothetical:
`plan/herdr-overseer/research/002-herdr-api-evidence.md` records that herdr pane
ids "are opaque and only unique within a server (`w1:p1` repeats between test and
default instances)", and `SPECIFICATION/constraints.md` adds that a socket path
alone is insufficient because "server restarts may reuse that path and pane ids"
— so the server GENERATION (peer pid plus process start time) is part of the
identity.

Every malformed case below is built by MUTATING a value the encoder itself
produced, rather than by hand-spelling an encoded string. Hand-spelling is how a
refusal test goes green for the wrong reason: a literal that is malformed in two
ways at once collapses several distinct refusals into whichever one is checked
first, and nothing in the assertion can tell. Mutation keeps each case one step
away from valid, so the refusal it names is the refusal it gets.

The module import is function-local and sits behind an assertion on the expected
module path, so this file collects and reaches a real assertion at Red instead of
dying as a `ModuleNotFoundError` at collection time.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
MODULE_PATH = PACKAGE_DIR / "herdr_identity.py"

# A socket path that exercises BOTH hostile characters at once: a space (which a
# naive shell-ish encoding loses) and a colon (which a naive `:`-delimited
# encoding mis-splits). The pane id carries herdr's own measured `w1:p1` shape,
# which is itself colon-bearing.
HOSTILE_SOCKET = "/home/op/herdr sessions/a:b/herdr.sock"
MEASURED_PANE = "w1:p1"


def _identity() -> Any:
    assert MODULE_PATH.is_file(), (
        f"the herdr identity encoder must live at {MODULE_PATH.relative_to(PACKAGE_DIR.parent)}; "
        "a qualified terminal coordinate has no other home in this package"
    )
    return importlib.import_module("herdr_identity")


def _target(*, identity: Any) -> Any:
    return identity.HerdrPaneTarget(
        socket_path=HOSTILE_SOCKET,
        server_pid=1015684,
        server_starttime="884421",
        pane_id=MEASURED_PANE,
    )


def _encoded_fields(*, identity: Any) -> list[str]:
    """The field list of a VALID encoding — the base every mutation starts from."""
    encoded = identity.encode_herdr_target(target=_target(identity=identity))
    assert encoded.startswith(identity.HERDR_SCHEME)
    return encoded[len(identity.HERDR_SCHEME) :].split(identity.FIELD_SEPARATOR)


def _qualified(*, identity: Any, fields: list[str]) -> str:
    return identity.HERDR_SCHEME + identity.FIELD_SEPARATOR.join(fields)


def test_a_qualified_target_round_trips_a_space_and_colon_bearing_instance():
    identity = _identity()
    target = _target(identity=identity)

    decoded = identity.decode_target(value=identity.encode_herdr_target(target=target))

    assert decoded.backend == identity.HERDR_BACKEND
    assert decoded.herdr == target
    assert decoded.tmux_session == ""
    assert decoded.error == ""


def test_the_same_pane_id_on_two_socket_instances_does_not_alias():
    identity = _identity()
    named = identity.HerdrPaneTarget(
        socket_path="/home/op/.config/herdr/sessions/probe/herdr.sock",
        server_pid=4242,
        server_starttime="884421",
        pane_id=MEASURED_PANE,
    )
    default = identity.HerdrPaneTarget(
        socket_path="/home/op/.config/herdr/herdr.sock",
        server_pid=4242,
        server_starttime="884421",
        pane_id=MEASURED_PANE,
    )

    assert identity.encode_herdr_target(target=named) != identity.encode_herdr_target(
        target=default
    )
    assert identity.herdr_instance_key(target=named) != identity.herdr_instance_key(target=default)


def test_the_same_pane_id_across_a_server_generation_change_does_not_alias():
    identity = _identity()
    socket_path = "/home/op/.config/herdr/herdr.sock"
    before = identity.HerdrPaneTarget(
        socket_path=socket_path,
        server_pid=4242,
        server_starttime="884421",
        pane_id=MEASURED_PANE,
    )
    # A restart that REUSES the pid is the case a pid-only identity cannot see,
    # which is why the start time is carried alongside it.
    reused_pid = identity.HerdrPaneTarget(
        socket_path=socket_path,
        server_pid=4242,
        server_starttime="919004",
        pane_id=MEASURED_PANE,
    )
    fresh_pid = identity.HerdrPaneTarget(
        socket_path=socket_path,
        server_pid=4243,
        server_starttime="884421",
        pane_id=MEASURED_PANE,
    )

    keys = {
        identity.herdr_instance_key(target=before),
        identity.herdr_instance_key(target=reused_pid),
        identity.herdr_instance_key(target=fresh_pid),
    }
    assert len(keys) == 3


def test_the_instance_key_excludes_the_pane_so_two_panes_share_one_instance():
    identity = _identity()
    first = _target(identity=identity)
    second = identity.HerdrPaneTarget(
        socket_path=first.socket_path,
        server_pid=first.server_pid,
        server_starttime=first.server_starttime,
        pane_id="w1:p9",
    )

    assert identity.herdr_instance_key(target=first) == identity.herdr_instance_key(target=second)
    assert identity.encode_herdr_target(target=first) != identity.encode_herdr_target(target=second)


def test_an_unqualified_legacy_value_keeps_its_tmux_meaning():
    identity = _identity()

    decoded = identity.decode_target(value="livespec-overseer")

    assert decoded.backend == identity.TMUX_BACKEND
    assert decoded.tmux_session == "livespec-overseer"
    assert decoded.herdr is None
    assert decoded.error == ""


def test_a_malformed_qualified_target_fails_closed_without_a_backend():
    identity = _identity()
    fields = _encoded_fields(identity=identity)
    sep = identity.FIELD_SEPARATOR

    cases = {
        "scheme with no fields at all": identity.HERDR_SCHEME,
        "one field short": _qualified(identity=identity, fields=fields[:-1]),
        "one field too many": _qualified(identity=identity, fields=[*fields, "extra"]),
        "server pid is not a number": _qualified(
            identity=identity, fields=[fields[0], "not-a-pid", *fields[2:]]
        ),
        "server pid is negative": _qualified(
            identity=identity, fields=[fields[0], "-1", *fields[2:]]
        ),
        "unencodable socket path": _qualified(identity=identity, fields=["@@", *fields[1:]]),
        "empty socket path": _qualified(identity=identity, fields=["", *fields[1:]]),
        "empty server start time": _qualified(
            identity=identity, fields=[*fields[:2], "", fields[3]]
        ),
        "empty pane id": _qualified(identity=identity, fields=[*fields[:3], ""]),
        "no coordinate at all": "",
    }
    # Guard the premise the mutation strategy rests on: a four-field encoding, so
    # `fields[:-1]` really is one short and `fields[3]` really is the pane.
    assert len(fields) == 4
    assert sep not in "".join(fields)

    for reason, value in cases.items():
        decoded = identity.decode_target(value=value)
        assert decoded.backend == "", f"{reason}: {value!r} must not resolve to any backend"
        assert decoded.herdr is None, f"{reason}: {value!r} must yield no herdr target"
        assert decoded.tmux_session == "", f"{reason}: {value!r} must not read as a tmux session"
        assert decoded.error != "", f"{reason}: {value!r} must name why it was refused"
