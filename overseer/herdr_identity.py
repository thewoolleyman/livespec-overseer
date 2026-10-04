"""herdr_identity.py — backend-qualified terminal coordinates. PURE, no I/O.

`SPECIFICATION/contracts.md` requires the durable terminal coordinate to
distinguish BACKEND, backend INSTANCE and EXACT PANE, so that equal names or pane
ids on different backends or different herdr servers cannot alias; and it
requires an UNQUALIFIED legacy value to retain its tmux meaning rather than be
reinterpreted as a herdr target. This module is that encoding and nothing else:
it reads no socket, spawns no process, and makes no claim that a coordinate it
decoded is LIVE. Proving a coordinate names a live server generation is
:mod:`herdr_transport`'s job.

Three measured facts shape the format
(`plan/herdr-overseer/research/002-herdr-api-evidence.md`):

  - A herdr pane id is opaque and unique only WITHIN a server — `w1:p1` was
    observed on both the named probe instance and the default instance — so the
    socket path belongs in the identity.
  - `SPECIFICATION/constraints.md` adds that the socket path alone is NOT enough,
    because a server restart may reuse both that path and the pane ids. The live
    server GENERATION is therefore carried too, as the peer pid plus that
    process's start time. The pid alone is reusable; the pair is not.
  - Pane ids and session directories carry colons and spaces (`w1:p1`, and any
    operator `--session` path), so the two free-text fields are HEX-encoded
    before being joined with the field separator.

**Why hex rather than percent-encoding.** Hex needs no import at all, and that is
load-bearing here rather than incidental: `percent`-encoding lives in
`urllib.parse`, and `overseer/test_package_constraints.py` bans every
network-capable stdlib module — `urllib` included — from the supervision loop, so
that the daemon provably cannot make a model call. Reaching for `urllib` for pure
string work would have spent that guard's one exception on something that needs
no exception. Hex also makes the encoding TOTAL over arbitrary bytes and leaves
no escape-sequence ambiguity to get wrong. The server pid stays decimal because
it is the one field an operator reads directly against `ps`.

**The `herdr:` prefix is a RESERVED scheme, not a guess about content.** A value
that starts with it is read as a qualified herdr coordinate or REFUSED; it is
never re-read as a tmux session name of that spelling.

**Decoding is FAIL-CLOSED and says why in the value.** A malformed qualified
target resolves to NO backend (`backend == ""`), carries no herdr target and no
tmux session, and names its refusal in `error`. There is deliberately no
"probably meant tmux" fallback: `SPECIFICATION/constraints.md` forbids silently
falling back to the other backend when ownership is absent, ambiguous or
unreadable, and a wrong-backend act is the whole hazard qualification exists to
remove.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = [
    "FIELD_SEPARATOR",
    "HERDR_BACKEND",
    "HERDR_SCHEME",
    "TMUX_BACKEND",
    "HerdrPaneTarget",
    "TargetDecoding",
    "decode_target",
    "encode_herdr_target",
    "herdr_instance_key",
]

HERDR_BACKEND = "herdr"
TMUX_BACKEND = "tmux"
HERDR_SCHEME = "herdr:"
FIELD_SEPARATOR = ":"

_FIELD_COUNT = 4


@dataclass(frozen=True, kw_only=True)
class HerdrPaneTarget:
    """One exact pane on one exact live herdr server generation.

    `server_pid` + `server_starttime` ARE the generation: the pid identifies the
    running server process and the start time makes that identity non-reusable
    across a restart that happens to be handed the same pid.
    """

    socket_path: str
    server_pid: int
    server_starttime: str
    pane_id: str


@dataclass(frozen=True, kw_only=True)
class TargetDecoding:
    """A fail-closed reading of one durable terminal coordinate.

    Exactly one of three shapes: a herdr target (`backend == HERDR_BACKEND`, with
    `herdr` set), a legacy tmux session (`backend == TMUX_BACKEND`, with
    `tmux_session` set), or a refusal (`backend == ""`, with `error` set and
    nothing else populated).
    """

    backend: str
    tmux_session: str
    herdr: HerdrPaneTarget | None
    error: str


def _encode_field(*, value: str) -> str:
    return value.encode("utf-8").hex()


def _decode_field(*, value: str) -> str | None:
    """The field's text, or None when it is not a well-formed encoded field.

    One `ValueError` covers both halves: `bytes.fromhex` raises it for a
    non-hex or odd-length field, and `UnicodeDecodeError` — which the decode
    raises for bytes that are not UTF-8 — is itself a `ValueError` subclass.
    """
    try:
        return bytes.fromhex(value).decode("utf-8")
    except ValueError:
        return None


def herdr_instance_key(*, target: HerdrPaneTarget) -> str:
    """The exact-INSTANCE key: socket path plus server generation, pane EXCLUDED.

    Two coordinates share an instance key when they name the same live server
    generation on the same socket. It is deliberately pane-free so a caller can
    ask "is this the instance whose peer credentials I validated?" without also
    asking "is this the pane I validated?" — two questions with different answers
    and different remedies, which a combined key would conflate.
    """
    return FIELD_SEPARATOR.join(
        (
            _encode_field(value=target.socket_path),
            str(target.server_pid),
            _encode_field(value=target.server_starttime),
        )
    )


def encode_herdr_target(*, target: HerdrPaneTarget) -> str:
    """Render `target` as the opaque qualified value a durable store may carry."""
    return HERDR_SCHEME + FIELD_SEPARATOR.join(
        (
            herdr_instance_key(target=target),
            _encode_field(value=target.pane_id),
        )
    )


def _refusal(*, error: str) -> TargetDecoding:
    return TargetDecoding(backend="", tmux_session="", herdr=None, error=error)


def _decode_qualified(*, body: str) -> TargetDecoding:
    fields = body.split(FIELD_SEPARATOR)
    if len(fields) != _FIELD_COUNT:
        return _refusal(
            error=f"qualified herdr target needs {_FIELD_COUNT} fields, found {len(fields)}"
        )
    socket_field, pid_field, starttime_field, pane_field = fields
    # `isdigit` rejects a sign as well as a non-number, so a negative pid never
    # reaches `int()`. A pid is a process id; there are no negative ones.
    if not pid_field.isdigit():
        return _refusal(error=f"server pid is not a non-negative integer: {pid_field!r}")
    texts: list[str] = []
    for name, raw in (
        ("socket path", socket_field),
        ("server start time", starttime_field),
        ("pane id", pane_field),
    ):
        text = _decode_field(value=raw)
        if text is None:
            return _refusal(error=f"qualified herdr target has an unreadable {name}: {raw!r}")
        if not text:
            return _refusal(error=f"qualified herdr target has an empty {name}")
        texts.append(text)
    socket_path, starttime, pane_id = texts
    return TargetDecoding(
        backend=HERDR_BACKEND,
        tmux_session="",
        herdr=HerdrPaneTarget(
            socket_path=socket_path,
            server_pid=int(pid_field),
            server_starttime=starttime,
            pane_id=pane_id,
        ),
        error="",
    )


def decode_target(*, value: str) -> TargetDecoding:
    """Read one durable terminal coordinate, fail-closed.

    An unqualified non-empty value is a legacy tmux session and is returned as
    one, unchanged. A value under the reserved `herdr:` scheme is decoded or
    REFUSED — never downgraded to a tmux reading.
    """
    if value.startswith(HERDR_SCHEME):
        return _decode_qualified(body=value[len(HERDR_SCHEME) :])
    if not value:
        return _refusal(error="terminal coordinate is empty")
    return TargetDecoding(backend=TMUX_BACKEND, tmux_session=value, herdr=None, error="")
