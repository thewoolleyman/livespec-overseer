"""herdr_protocol.py — the herdr socket API's wire envelopes. PURE, no I/O.

The measured protocol
(`plan/herdr-overseer/research/002-herdr-api-evidence.md`): connect
AF_UNIX/SOCK_STREAM, send ONE request object
`{"id": "unique", "method": "...", "params": {...}}` followed by a newline, read
ONE newline-terminated JSON reply wrapping either `result` or `error`, close.

This module owns the two pure halves of that — building the request bytes and
READING a reply — so that :mod:`herdr_transport` is only the socket boundary.
That separation is the repo's rule (pure data/parsing apart from I/O), and it
pays for itself here: every envelope refusal below is reachable in a test without
a socket, while the transport's own tests exercise framing and credentials.

**Reading a reply is FAIL-CLOSED at every step.**
`SPECIFICATION/contracts.md` requires that "unsupported or malformed backend
responses MUST be bounded and fail closed, never treated as proof of an idle
pane, successful paste, or successful replacement". So a reply is refused when it
is not UTF-8, is not well-formed JSON, is not a JSON object, carries an `error`
envelope, does not echo this request's `id`, carries no `result`, carries a
`result` that is not an object, declares the wrong `result.type`, or omits a
field the caller named as required. Nothing is coerced, defaulted, or
best-effort-ed.

**Why `result_type` is OPTIONAL, stated plainly rather than hidden.** The
research measured the `pane.process_info` reply end to end, including its
`"type": "pane_process_info"` discriminator. It did NOT measure the reply
discriminator for every other method. An expectation therefore carries the type
only where it is MEASURED, and leaves it empty elsewhere — where the required
FIELDS still gate the reply, so an unexpected shape is still refused, just not by
name. Guessing a discriminator string would have been worse than leaving it
empty: a wrong guess fails closed against the real server on every call, which
reads as "herdr is broken" rather than "this expectation was invented". The live
verification slice is what pins the remaining discriminators.

**The method names carry the same split.** `pane.read`, `pane.process_info` and
`pane.send_input` are MEASURED socket-API method names. The others are derived
from the measured CLI verbs (`pane list`, `pane split`, `pane swap`,
`pane layout`) by the dotted convention the measured three follow. They are
collected here, as named constants, precisely so that one live correction lands
in one place instead of being scattered across call sites.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field

import jsonio

__all__: list[str] = [
    "MAX_REPLY_BYTES",
    "MAX_REPLY_NESTING",
    "METHOD_PANE_LAYOUT",
    "METHOD_PANE_LIST",
    "METHOD_PANE_PROCESS_INFO",
    "METHOD_PANE_READ",
    "METHOD_PANE_SEND_INPUT",
    "METHOD_PANE_SPLIT",
    "METHOD_PANE_SWAP",
    "RESULT_TYPE_PANE_PROCESS_INFO",
    "ReplyExpectation",
    "ReplyReading",
    "encode_request",
    "read_reply",
]

# MEASURED socket-API method names.
METHOD_PANE_READ = "pane.read"
METHOD_PANE_PROCESS_INFO = "pane.process_info"
METHOD_PANE_SEND_INPUT = "pane.send_input"
# DERIVED from the measured CLI verbs by the dotted convention above; the live
# verification slice confirms or corrects these four, here and nowhere else.
METHOD_PANE_LIST = "pane.list"
METHOD_PANE_SPLIT = "pane.split"
METHOD_PANE_SWAP = "pane.swap"
METHOD_PANE_LAYOUT = "pane.layout"

# The one MEASURED result discriminator.
RESULT_TYPE_PANE_PROCESS_INFO = "pane_process_info"

# Ceiling on ONE reply, before its delimiter is seen. A herdr reply is a pane
# snapshot or a process list, so a megabyte is far above any legitimate answer
# and far below a size that could exhaust the daemon. It is not a performance
# budget: exceeding it means the peer is not speaking this protocol, which is the
# fail-closed case rather than a slow success.
MAX_REPLY_BYTES = 1 << 20

# Ceiling on ONE reply's NESTING, which is an entirely separate bound from its
# SIZE and has to be, because the two are unrelated: a thousand opening brackets
# is about two kilobytes, a two-hundredth of the size bound, and `json.loads`
# answers it with `RecursionError` — which is not a `ValueError` and so escaped
# the refusal below. The deepest MEASURED reply nests about six levels
# (`pane.layout`: envelope, result, layout, panes, a pane, its rect), and the
# whole-snapshot method a few more, so this is an order of magnitude above any
# legitimate answer and two orders below CPython's recursion limit. Exceeding it
# means the peer is not speaking this protocol.
MAX_REPLY_NESTING = 64


@dataclass(frozen=True, kw_only=True)
class ReplyExpectation:
    """What a caller requires of a reply's `result` before it will believe it.

    `result_type` empty means "unmeasured discriminator, do not check it" — see
    the module docstring. `required_fields` is always checked.
    """

    result_type: str = ""
    required_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class ReplyReading:
    """A fail-closed reading of one reply: a usable `result`, or a named refusal."""

    ok: bool
    result: dict[str, object]
    error: str


def encode_request(*, request_id: str, method: str, params: Mapping[str, object]) -> bytes:
    """One request envelope as the newline-delimited bytes the socket expects.

    `sort_keys` is not cosmetic: it makes the bytes on the wire a function of the
    request's CONTENT alone, so a test can assert on them and a diagnostic can be
    compared across runs.
    """
    envelope: dict[str, object] = {
        "id": request_id,
        "method": method,
        "params": dict(params),
    }
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"


def _refused(*, error: str) -> ReplyReading:
    return ReplyReading(ok=False, result={}, error=error)


def _nests_deeper_than(*, text: str, limit: int) -> bool:
    """Whether `text`'s structural nesting passes `limit`, without parsing it.

    This has to run BEFORE `json.loads`, because the failure it bounds is
    `json.loads` exhausting the stack — a guard placed after the parse never
    executes. A bracket inside a string LITERAL is not structure, and a pane
    capture is full of both brackets and backslashes (`\\u001b[2m` and friends),
    so string state is tracked and only what is outside a string is counted.

    **ONE PASS, NO BACKTRACKING, AND THAT IS THE WHOLE POINT.** This was first
    written as `re.sub` over the JSON string grammar, blanking every literal
    before counting — shorter, and C-speed on well-formed input. It is QUADRATIC
    on malformed input: an unterminated literal made of escaped quotes restarts
    and backtracks the engine at every quote, measured on this host at 0.0163s
    for 2 028 bytes, 0.0638s for 4 028 and 0.2514s for 8 028 — quadrupling per
    doubling, so a frame still inside `MAX_REPLY_BYTES` costs hours. Nothing can
    interrupt it: it is CPU inside the daemon's own tick, which no socket
    deadline reaches. A character scan is slower on the happy path (about 70ms
    for a megabyte) and BOUNDED on every path, which is the trade a supervision
    loop needs.

    The escape state is load-bearing in BOTH directions, and they fail
    oppositely. Ignoring it reads `\\"` as closing a literal, so a captured
    pane's brackets become structure and a legitimate reply is refused; and an
    escaped BACKSLASH really does close the literal, so genuine nesting after
    one must still be counted. Text this scan cannot pair up is not well-formed
    JSON and the parse immediately after refuses it.
    """
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
            if depth > limit:
                return True
        elif char in "}]":
            depth -= 1
    return False


@dataclass(frozen=True, kw_only=True)
class _MemberNameAudit:
    """A `json.loads` object hook that RECORDS every repeated member name it sees.

    `SPECIFICATION/scenarios.md` section "Duplicate JSON member names are never
    silently collapsed" forbids choosing either duplicate value, and a plain
    `dict` resolves last-wins before any caller can see that a choice was made.
    This records rather than raises, so the refusal stays a returned value on the
    same rail as every other one here, and it sees EVERY object in the reply —
    including ones nested inside `result`, where a required field's own members
    could otherwise be doubled unnoticed.

    It is a callable OBJECT rather than a function because `json.loads` invokes
    the hook POSITIONALLY. `__call__` is one of the Python-mandated positional
    signatures this repo's keyword-only rule exempts, so an externally fixed
    calling convention is met without weakening the rule or suppressing it.
    """

    repeats: list[str] = field(default_factory=list)

    def __call__(self, pairs: list[tuple[str, object]]) -> dict[str, object]:
        seen: set[str] = set()
        for name, _value in pairs:
            if name in seen:
                self.repeats.append(name)
            seen.add(name)
        return dict(pairs)


def _parsed_object(*, text: str) -> tuple[dict[str, object] | None, str]:
    """`text` as a JSON object under this module's bounds, or why it is unusable.

    Deliberately NOT `jsonio.parse_object`: that folder is the repo's shared
    narrowing boundary and its contract is "malformed or not", which is right for
    the operator's own files. A reply arrives from outside the daemon, so it
    additionally owes a nesting bound and a duplicate-member refusal that the
    shared folder has no business imposing on a hand-edited local store.
    """
    if _nests_deeper_than(text=text, limit=MAX_REPLY_NESTING):
        return None, f"herdr reply nests deeper than the bounded {MAX_REPLY_NESTING} levels"
    audit = _MemberNameAudit()
    try:
        parsed: object = json.loads(text, object_pairs_hook=audit)
    except ValueError:
        return None, "herdr reply is not well-formed JSON"
    if audit.repeats:
        return None, f"herdr reply repeats member name(s) {sorted(set(audit.repeats))}"
    envelope = jsonio.as_object(value=parsed)
    if envelope is None:
        return None, "herdr reply is not a JSON object"
    return envelope, ""


def _envelope_of(*, raw: bytes, request_id: str) -> tuple[dict[str, object] | None, str]:
    """The reply's TRANSPORT envelope, or why it cannot be read as one.

    Split from the result-level reading below along the seam the protocol itself
    draws: this half answers "did this peer answer THIS request, and did it
    answer at all?", which is decidable without knowing what the caller asked
    for. The result-level half needs the caller's expectation and nothing else.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "herdr reply is not valid UTF-8"
    envelope, parse_error = _parsed_object(text=text)
    if envelope is None:
        return None, parse_error
    if "error" in envelope:
        return None, f"herdr returned an error envelope: {envelope['error']!r}"
    if envelope.get("id") != request_id:
        return None, (
            f"herdr reply id {envelope.get('id')!r} does not match request id {request_id!r}"
        )
    return envelope, ""


def _result_of(*, envelope: dict[str, object], expect: ReplyExpectation) -> ReplyReading:
    """The envelope's `result`, gated by `expect`, or a named refusal."""
    if "result" not in envelope:
        return _refused(error="herdr reply carries no result")
    result = jsonio.as_object(value=envelope["result"])
    if result is None:
        return _refused(error="herdr reply result is not a JSON object")
    if expect.result_type and result.get("type") != expect.result_type:
        return _refused(
            error=(
                f"herdr reply result type {result.get('type')!r} is not the "
                f"expected {expect.result_type!r}"
            )
        )
    missing = [name for name in expect.required_fields if name not in result]
    if missing:
        return _refused(error=f"herdr reply result is missing required fields: {missing}")
    return ReplyReading(ok=True, result=result, error="")


def read_reply(*, raw: bytes, request_id: str, expect: ReplyExpectation) -> ReplyReading:
    """Read one reply's payload bytes against `expect`, refusing anything unusable.

    `raw` is the reply WITHOUT its delimiter; framing is the transport's job.
    """
    envelope, envelope_error = _envelope_of(raw=raw, request_id=request_id)
    if envelope is None:
        return _refused(error=envelope_error)
    return _result_of(envelope=envelope, expect=expect)
