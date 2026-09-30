"""The operator argument surface: two accepted shapes, and the vector each one builds.

SPECIFICATION/contracts.md closes this layer to ZERO arguments or the four
order-independent pairs `--provider <value>`, `--account-id <value>`, `--kind <value>`
and `--purpose <value>`, each appearing once with a non-empty value. Zero arguments run
the `attention` LIST action; four valid pairs run `acquire --acquisition-json -` with the
canonical version-1 five-member object streamed to standard input. Anything else is
`invalid-request`, and MUST NOT reach the executable at all.

THE ARGUMENT VECTOR IS THE SAFETY PROPERTY, not the accept/reject verdict. The same
executable exposes `attention --resolve <record_id>` and `attention --give-up
<record_id>`, and the contract forbids this layer from constructing, forwarding or
executing either. That is why both vectors here are module-level CONSTANTS rather than
assembled from operator tokens: a layer that built its vector by copying what the
operator typed could be steered into a mutation by an operator who typed one, and no
amount of validation on the accepted FIELDS would notice.

THE REFUSAL NAMES FIELDS, NEVER VALUES. An unknown `--flag=value` token and a bare
positional argument can each carry a credential — an operator who pastes a token in the
wrong position is precisely the case this operation exists to survive. So an unknown flag
is reported by its stem, with anything after the first `=` discarded, and a positional
argument is reported by its POSITION. Echoing the offending token would put the secret
into operator-visible output, an audit log and a shell history in one step.

`lease_seconds`-style normalization has no counterpart here: the acquisition object's five
members are exactly what the operator supplied plus the literal `version`, and the
canonical encoder — not this module — fixes their byte form.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_bytes
from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ACQUIRE_ARGV",
    "ACQUISITION_VERSION",
    "ATTENTION_ARGV",
    "OPERATOR_FLAGS",
    "OperatorRequest",
    "operator_request",
]

ACQUISITION_VERSION: Final = 1

# Both vectors are LITERAL. See the module docstring: assembling either one from operator
# tokens is the single way the forbidden `attention --resolve`/`--give-up` mutation could
# ever be constructed by this layer.
ATTENTION_ARGV: Final[tuple[str, ...]] = ("attention",)
ACQUIRE_ARGV: Final[tuple[str, ...]] = ("acquire", "--acquisition-json", "-")

OPERATOR_FLAGS: Final[tuple[str, ...]] = (
    "--provider",
    "--account-id",
    "--kind",
    "--purpose",
)

_FIELD_BY_FLAG: Final[dict[str, str]] = {
    "--provider": "provider",
    "--account-id": "account_id",
    "--kind": "kind",
    "--purpose": "purpose",
}


@dataclass(frozen=True, kw_only=True)
class OperatorRequest:
    """One accepted operator request: the exact vector, and the bytes for its stdin.

    `stdin_bytes` is `None` for the attention list, which takes no standard input at all.
    The distinction is carried in the type rather than by an empty-bytes sentinel, because
    writing zero bytes to the executable and writing nothing are different wire behaviors
    and the contract specifies the latter.
    """

    argv: tuple[str, ...]
    stdin_bytes: bytes | None


def _offender_name(*, token: str, position: int) -> str:
    """Name an unrecognized token without echoing anything that could be a secret."""
    if token.startswith("--"):
        return token.split("=", 1)[0]
    return f"positional-argument-{position}"


def _scan(*, arguments: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """Walk the tokens once, collecting accepted field values and offending field names.

    A dangling flag, a repeated flag and an empty value are all reported as the FLAG
    itself, because that is the field the operator has to fix. An unrecognized token is
    reported by :func:`_offender_name`.
    """
    values: dict[str, str] = {}
    offending: list[str] = []
    position = 0
    while position < len(arguments):
        token = arguments[position]
        if token not in _FIELD_BY_FLAG:
            offending.append(_offender_name(token=token, position=position))
            position += 1
            continue
        if position + 1 >= len(arguments):
            offending.append(token)
            position += 1
            continue
        value = arguments[position + 1]
        if _FIELD_BY_FLAG[token] in values or not value:
            offending.append(token)
        else:
            values[_FIELD_BY_FLAG[token]] = value
        position += 2
    return values, offending


def _refusal(*, missing: list[str], offending: list[str]) -> ManagerError:
    parts: list[str] = []
    if missing:
        parts.append(f"missing: {', '.join(missing)}")
    if offending:
        parts.append(f"offending: {', '.join(offending)}")
    return invalid_request(message=f"operator invocation rejected; {'; '.join(parts)}")


def operator_request(*, arguments: Sequence[str]) -> Result[OperatorRequest, ManagerError]:
    """Resolve `arguments` to the one vector they authorize, or to a named refusal."""
    if not arguments:
        return Success(OperatorRequest(argv=ATTENTION_ARGV, stdin_bytes=None))

    values, offending = _scan(arguments=arguments)
    missing = [flag for flag in OPERATOR_FLAGS if _FIELD_BY_FLAG[flag] not in values]
    if missing or offending:
        return Failure(_refusal(missing=missing, offending=offending))

    # Every member below is a validated non-empty `str` or the literal integer `version`,
    # so the canonical encoder -- which refuses only floats, non-string object keys and
    # lone surrogates -- has no refusal to report here. An unwrap failure would be a bug
    # in the encoder rather than an operator-visible condition, and belongs on the bug
    # rail; this is the same reasoning `_lpm_audit._prepared_line` records.
    encoded = canonical_json_bytes(
        value={
            "version": ACQUISITION_VERSION,
            "provider": values["provider"],
            "account_id": values["account_id"],
            "kind": values["kind"],
            "purpose": values["purpose"],
        }
    ).unwrap()
    return Success(OperatorRequest(argv=ACQUIRE_ARGV, stdin_bytes=encoded))
