"""Canonical JSON and length-prefixed digest identity for `llm-provider-manager`.

SPECIFICATION/contracts.md fixes ONE byte
representation for stored metadata, audit entries and pending metadata-effect fences, and
ONE digest input form — `LP(value)`, the unsigned eight-byte big-endian length of the
value's UTF-8 bytes followed by those bytes — for every manager-generated local-state
path, lock identity and idempotency digest that concatenates variable values.

Both definitions live here, together, because the whole operation is decided by comparing
these bytes. A conditional-set's `predecessor_sha256`, an audit append's `effect_id`
idempotency scan and a fence's byte-identical retry all fail CLOSED the moment two
encoders disagree by a space or a key order — and failing closed on a mismatch nobody
made is indistinguishable, from the outside, from the corruption the comparison exists to
catch.

WHY LENGTH PREFIXING RATHER THAN A DELIMITER: a lease path hashes
`LP(provider) || LP(account_id)`. Delimiter-joined text would let an account id containing
the delimiter collide with a different provider/account pair, and a collision here means
two different accounts sharing one lease file. The prefix makes the boundary unforgeable
from inside a value. Explicit external-backend wire forms — the values-vault item title
and `value_ref` — are stated literally by the contract and MUST keep their own syntax;
they do not come through here.

DUPLICATE MEMBER NAMES ARE REJECTED, never silently collapsed. `json.loads` keeps the
last occurrence by default, which would let a hand-edited record carry a second `status`
that no reader ever sees. The contract requires detection at every JSON parser boundary in
this operation, so the detection is in the ONE parser rather than in each caller.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "JsonDefect",
    "JsonParse",
    "canonical_json_bytes",
    "canonical_json_text",
    "length_prefixed",
    "length_prefixed_digest",
    "parse_canonical_json",
    "sha256_hex",
]

_LENGTH_PREFIX_BYTES = 8
_SURROGATE_FIRST = 0xD800
_SURROGATE_LAST = 0xDFFF
_LAST_CONTROL = 0x1F


@dataclass(frozen=True, kw_only=True)
class JsonDefect:
    """A secret-free reason one JSON text is not acceptable at a parser boundary.

    Deliberately NOT a typed manager error: the same defect maps to `invalid-request` for
    configuration or consumer input and to `store-unavailable` for a stored metadata
    record, and only the caller knows which boundary it stands at.
    """

    reason: str


JsonParse = Result[object, JsonDefect]


def length_prefixed(*, value: str) -> bytes:
    """`LP(value)` — eight-byte big-endian UTF-8 length, then the UTF-8 bytes."""
    data = value.encode("utf-8")
    return len(data).to_bytes(_LENGTH_PREFIX_BYTES, "big") + data


def length_prefixed_digest(*, values: Sequence[str]) -> str:
    """Lowercase SHA-256 over the ordered `LP` values — the local-path identity digest."""
    digest = hashlib.sha256()
    for value in values:
        digest.update(length_prefixed(value=value))
    return digest.hexdigest()


def sha256_hex(*, data: bytes) -> str:
    """Lowercase SHA-256 of raw bytes, for the digests the contract states unprefixed."""
    return hashlib.sha256(data).hexdigest()


def canonical_json_text(*, value: object) -> Result[str, JsonDefect]:
    """Encode `value` in the operation's one canonical form, or report why it cannot be.

    Canonical means: object members recursively sorted by the UTF-8 bytes of each decoded
    name; array order preserved; no insignificant whitespace; lowercase `true`, `false`
    and `null`; base-10 integers with a minus sign only when negative and no leading zero
    except the value zero; and no trailing newline.

    A float, a non-string object key or a lone surrogate is refused rather than coerced.
    Each would produce bytes that no second encoder reproduces — a float's shortest
    repr is platform-sensitive and a lone surrogate is not a Unicode scalar value — and
    an irreproducible byte string silently defeats every comparison downstream.
    """
    encoded = _encode(value=value)
    if encoded is None:
        return Failure(JsonDefect(reason="value is not canonical-JSON encodable"))
    return Success(encoded)


def canonical_json_bytes(*, value: object) -> Result[bytes, JsonDefect]:
    """The UTF-8 bytes of :func:`canonical_json_text`, without a byte-order mark."""
    text = canonical_json_text(value=value)
    if isinstance(text, Failure):
        return text
    return Success(text.unwrap().encode("utf-8"))


def parse_canonical_json(*, text: str) -> JsonParse:
    """Parse `text`, refusing malformed JSON and any duplicate object member name."""
    duplicates: list[str] = []
    try:
        # `object_pairs_hook`'s calling convention is fixed by the stdlib — it is invoked
        # with ONE positional list of member pairs — so the lambda is that adapter and
        # nothing else; the work it forwards to keeps this package's keyword-only surface.
        parsed: object = json.loads(
            text,
            object_pairs_hook=lambda pairs: _object_from_pairs(pairs=pairs, duplicates=duplicates),
        )
    except ValueError:
        return Failure(JsonDefect(reason="malformed JSON"))
    if duplicates:
        return Failure(JsonDefect(reason=f"duplicate member name: {sorted(duplicates)[0]}"))
    return Success(parsed)


def _object_from_pairs(
    *, pairs: list[tuple[str, object]], duplicates: list[str]
) -> dict[str, object]:
    """Build one JSON object from its parsed member pairs, recording repeated names."""
    names = [name for name, _ in pairs]
    duplicates.extend(sorted({name for name in names if names.count(name) > 1}))
    return dict(pairs)


def _encode(*, value: object) -> str | None:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _encode_string(value=value)
    return _encode_container(value=value)


def _encode_container(*, value: object) -> str | None:
    if isinstance(value, list):
        return _encode_array(value=cast("list[object]", value))
    if isinstance(value, dict):
        return _encode_object(value=cast("dict[object, object]", value))
    return None


def _encode_array(*, value: list[object]) -> str | None:
    members: list[str] = []
    for element in value:
        encoded = _encode(value=element)
        if encoded is None:
            return None
        members.append(encoded)
    return f"[{','.join(members)}]"


def _encode_object(*, value: dict[object, object]) -> str | None:
    # Names are collected before ordering so a non-string key is refused rather than
    # compared: the contract orders members by the UTF-8 bytes of each DECODED NAME,
    # and a key that has no decoded name has no place in that order.
    named: dict[str, object] = {}
    for name, member in value.items():
        if not isinstance(name, str):
            return None
        named[name] = member
    members: list[str] = []
    for name in sorted(named, key=lambda text: text.encode("utf-8", "surrogatepass")):
        encoded_name = _encode_string(value=name)
        encoded_member = _encode(value=named[name])
        if encoded_name is None or encoded_member is None:
            return None
        members.append(f"{encoded_name}:{encoded_member}")
    return f"{{{','.join(members)}}}"


def _encode_string(*, value: str) -> str | None:
    pieces: list[str] = ['"']
    for character in value:
        point = ord(character)
        if _SURROGATE_FIRST <= point <= _SURROGATE_LAST:
            return None
        if character in {'"', "\\"}:
            pieces.append(f"\\{character}")
        elif point <= _LAST_CONTROL:
            pieces.append(f"\\u{point:04x}")
        else:
            pieces.append(character)
    pieces.append('"')
    return "".join(pieces)
