"""The pending metadata-effect fence: ten members whose relations are all derivable.

SPECIFICATION/contracts.md states the fence as an atomically replaced regular non-symlink
mode-`0600` file containing EXACTLY `version`, `record_id`, `effect_id`, `writer_role`,
`revision`, `item_title`, `predecessor_sha256`, nullable `expected_record`, `desired_record`
and nullable `owner_operation_id`; requires its revision, title and predecessor digest to
EQUAL the append-only logical-revision forms derived from those records and the effect id;
and requires its writer role to equal the semantic audit actor the actor table assigns to the
owning operation, phase and effect. A malformed, unsafe or relation-invalid fence — INCLUDING
a writer-role mismatch — returns `store-unavailable` without reset or mutation.

WHY A FENCE EXISTS AT ALL. A conditional metadata create whose adapter result is unknown
leaves nobody able to say whether the logical revision landed. The fence is what makes the
retry safe: because no DIFFERENT manager create may pass it, and byte-identical physical
duplicates collapse to one logical revision, either the original or the retry can only ever
create the one DESIRED revision — so a late duplicate cannot conflict with, overwrite or
outrank another manager's later revision.

EVERY RELATION IS RE-DERIVED RATHER THAN TRUSTED, and that is the point of validating at all.
The fence is read by a LATER process which must reconstruct the exact byte-identical revision
to retry; if the stored title or predecessor digest could disagree with the records beside
them, that retry would create a revision nobody authorized. So `fence_for_effect` derives the
three from the records and the effect id, and `fence_from_object` re-derives them on the way
back in — a fence can therefore never be half-trusted.

ABSENCE OF `owner_operation_id` IS NOT A GENERAL ALLOWANCE. The contract permits it only for
the operation-less lifecycle-expiry exception, which is also fixed at `recovery-writer`, so an
ownerless fence in any other writer role is relation-invalid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_text, is_sha256_hex
from _lpm_operation_plan import RECOVERY_WRITER, WRITER_ROLES
from _lpm_record import credential_record_from_object, is_uuid4
from _lpm_results import ManagerError, internal_bug, store_unavailable
from _lpm_revisions import FIRST_REVISION, GENESIS_PREDECESSOR, predecessor_digest, revision_title

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "FENCE_MEMBERS",
    "FENCE_VERSION",
    "MetadataFence",
    "fence_for_effect",
    "fence_from_object",
    "fence_object",
]

FENCE_VERSION: Final = 1
FENCE_MEMBERS: Final = (
    "version",
    "record_id",
    "effect_id",
    "writer_role",
    "revision",
    "item_title",
    "predecessor_sha256",
    "expected_record",
    "desired_record",
    "owner_operation_id",
)

_SUCCESSOR_REVISION: Final = FIRST_REVISION + 1
_UNENCODABLE_DIGEST: Final = ""


@dataclass(frozen=True, kw_only=True)
class MetadataFence:
    """One pending metadata-effect fence. Carries records, never a credential value."""

    record_id: str
    effect_id: str
    writer_role: str
    revision: int
    item_title: str
    predecessor_sha256: str
    expected_record: dict[str, object] | None
    desired_record: dict[str, object]
    owner_operation_id: str | None


def fence_object(*, fence: MetadataFence) -> dict[str, object]:
    """The exact ten-member mapping for `fence`, built from the declared member list."""
    values: dict[str, object] = {"version": FENCE_VERSION}
    for member in FENCE_MEMBERS[1:]:
        values[member] = getattr(fence, member)
    return values


def fence_for_effect(
    *,
    effect_id: str,
    writer_role: str,
    revision: int,
    expected_record: dict[str, object] | None,
    desired_record: dict[str, object],
    owner_operation_id: str | None,
) -> Result[MetadataFence, ManagerError]:
    """Build the one fence that `effect_id`'s conditional create may be guarded by.

    The title and predecessor digest are DERIVED here rather than accepted, so the fence a
    later process retries from cannot name a revision the records beside it do not imply. The
    result is then validated through the reader's own rules, so a caller cannot construct a
    fence that the next process to open it would refuse.
    """
    record_id = desired_record.get("record_id")
    if not isinstance(record_id, str):
        return Failure(internal_bug(message="a desired record must carry its record_id"))
    fence = MetadataFence(
        record_id=record_id,
        effect_id=effect_id,
        writer_role=writer_role,
        revision=revision,
        item_title=revision_title(record_id=record_id, revision=revision, effect_id=effect_id),
        predecessor_sha256=_record_digest(record=expected_record),
        expected_record=expected_record,
        desired_record=desired_record,
        owner_operation_id=owner_operation_id,
    )
    return fence_from_object(parsed=fence_object(fence=fence))


def fence_from_object(*, parsed: object) -> Result[MetadataFence, ManagerError]:
    """Validate one decoded fence against its shape AND every derivable relation."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a metadata fence must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    for inspect in (_membership_defect, _typed_defect, _record_defect, _relation_defect):
        reason = inspect(source=source)
        if reason is not None:
            return Failure(store_unavailable(message=reason))
    return Success(
        MetadataFence(
            record_id=str(source["record_id"]),
            effect_id=str(source["effect_id"]),
            writer_role=str(source["writer_role"]),
            revision=cast("int", source["revision"]),
            item_title=str(source["item_title"]),
            predecessor_sha256=str(source["predecessor_sha256"]),
            expected_record=cast("dict[str, object] | None", source["expected_record"]),
            desired_record=cast("dict[str, object]", source["desired_record"]),
            owner_operation_id=_optional_text(value=source["owner_operation_id"]),
        )
    )


def _membership_defect(*, source: dict[str, object]) -> str | None:
    missing = [member for member in FENCE_MEMBERS if member not in source]
    if missing:
        return f"a metadata fence is missing {missing[0]}"
    extra = sorted(set(source) - set(FENCE_MEMBERS))
    if extra:
        return f"a metadata fence has extra member {extra[0]}"
    version = source["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != FENCE_VERSION:
        return "a metadata fence version must be the integer 1"
    return None


def _typed_defect(*, source: dict[str, object]) -> str | None:
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return "a fence record_id must be a lowercase RFC 4122 UUIDv4"
    for member in ("effect_id", "predecessor_sha256"):
        value = source[member]
        if not isinstance(value, str) or not is_sha256_hex(value=value):
            return f"a fence {member} must be a lowercase SHA-256 hex digest"
    if source["writer_role"] not in WRITER_ROLES:
        return f"a fence writer_role must be one of {', '.join(WRITER_ROLES)}"
    revision = source["revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < FIRST_REVISION:
        return "a fence revision must be a positive integer"
    item_title = source["item_title"]
    if not isinstance(item_title, str) or item_title == "":
        return "a fence item_title must be a non-empty string"
    return _owner_defect(source=source)


def _owner_defect(*, source: dict[str, object]) -> str | None:
    owner = source["owner_operation_id"]
    if owner is None:
        if source["writer_role"] != RECOVERY_WRITER:
            return "only operation-less lifecycle expiry may omit owner_operation_id"
        return None
    if not isinstance(owner, str) or not is_uuid4(value=owner):
        return "a fence owner_operation_id must be null or a lowercase RFC 4122 UUIDv4"
    return None


def _record_defect(*, source: dict[str, object]) -> str | None:
    desired = credential_record_from_object(parsed=source["desired_record"])
    if isinstance(desired, Failure):
        return f"a fence desired_record is invalid: {desired.failure().reason}"
    expected = source["expected_record"]
    if expected is None:
        return None
    validated = credential_record_from_object(parsed=expected)
    if isinstance(validated, Failure):
        return f"a fence expected_record is invalid: {validated.failure().reason}"
    return None


def _relation_defect(*, source: dict[str, object]) -> str | None:
    record_id = str(source["record_id"])
    for member in ("desired_record", "expected_record"):
        stored = source[member]
        if isinstance(stored, dict) and cast("dict[str, object]", stored)["record_id"] != record_id:
            return f"a fence {member} must name the fence's own record_id"
    revision = cast("int", source["revision"])
    derived = revision_title(
        record_id=record_id, revision=revision, effect_id=str(source["effect_id"])
    )
    if source["item_title"] != derived:
        return "a fence item_title must be the derived append-only revision title"
    return _chain_defect(source=source, revision=revision)


def _chain_defect(*, source: dict[str, object], revision: int) -> str | None:
    expected = source["expected_record"]
    if expected is None:
        if revision != FIRST_REVISION:
            return "a fence creating from absence must be revision 1"
        if source["predecessor_sha256"] != GENESIS_PREDECESSOR:
            return "a fence creating from absence must carry the genesis predecessor digest"
        return None
    if revision < _SUCCESSOR_REVISION:
        return "a fence following an expected predecessor must be revision 2 or later"
    digest = _record_digest(record=cast("dict[str, object]", expected))
    if source["predecessor_sha256"] != digest:
        return "a fence predecessor_sha256 must digest its own expected_record"
    return None


def _record_digest(*, record: dict[str, object] | None) -> str:
    """The predecessor digest for a revision following `record`, or the genesis value.

    An unencodable record yields the empty string rather than a plausible digest: a value
    that is not canonical-JSON encodable has no reproducible byte form, so it cannot HAVE a
    predecessor digest, and the empty string is refused by the shape check above instead of
    being silently compared against something.
    """
    if record is None:
        return GENESIS_PREDECESSOR
    encoded = canonical_json_text(value=record)
    if isinstance(encoded, Failure):
        return _UNENCODABLE_DIGEST
    return predecessor_digest(record=encoded.unwrap())


def _optional_text(*, value: object) -> str | None:
    return None if value is None else str(value)
