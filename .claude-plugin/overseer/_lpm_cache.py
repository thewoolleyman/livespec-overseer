"""The bounded in-process metadata cache, and the events that must invalidate it.

SPECIFICATION/contracts.md requires metadata reads from every provisionable-token store backend to
use an in-process memory cache whose maximum entry age is the configured
`backend_cache_interval_seconds` (five minutes by default), keyed by `record_id` AND the current
logical revision's `item_id` rather than by `value_generation`, never outliving its command or
detached worker process. It further requires that a metadata write or a failed validation evict
matching entries in the writing process BEFORE acknowledgement, that a consumer authentication
report evict only when it actually transitions the credential to `suspect`, and that a cache
failure degrade to a store read and never make an unvalidated credential eligible.

THE `item_id` HALF OF THE KEY IS THE WHOLE SAFETY PROPERTY. Keying by `record_id` alone
would let a process hold a `valid` entry that a SIBLING process has since moved to
`suspect` in a new revision of the same value generation — the status changed, the
generation did not, and a generation-keyed or record-keyed cache cannot tell. So a hit is
admissible only after an UNCACHED revision-title read, which is why `lookup` demands the
caller pass the title it just observed rather than reading one itself: a cache that could
fetch its own validation could satisfy it from itself.

A MISS IS NEVER AN ERROR, and that asymmetry is deliberate. Absent, stale-by-age and
superseded-by-revision all answer "go to the store", which is the same degradation the
contract prescribes for a cache failure. Nothing here can make a record eligible; it can
only avoid a re-read of one the store already vouched for.

EVICTION IS BY `record_id`, ACROSS EVERY REVISION. An eviction happens because the record
CHANGED or became doubtful, so removing only the entry whose title the caller happens to
hold would leave an older revision's entry behind to be hit later by a reader that
observes that older title. The invalidation-event set is closed for the same reason the
lifecycle table is: an unregistered spelling is a caller bug, not a silent no-op that
leaves a suspect credential cached as `valid`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_config_fields import INTEGER_FIELDS
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, internal_bug
from _lpm_time import add_seconds, is_at_or_after

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AUTHENTICATION_REPORT_INVALIDATION",
    "CACHE_INTERVAL_FIELD",
    "CACHE_INVALIDATION_EVENTS",
    "DEFAULT_CACHE_INTERVAL_SECONDS",
    "CachedRecord",
    "MetadataCache",
    "entry_is_stale",
]

CACHE_INTERVAL_FIELD: Final = "backend_cache_interval_seconds"

DEFAULT_CACHE_INTERVAL_SECONDS: Final = next(
    field_row.default for field_row in INTEGER_FIELDS if field_row.name == CACHE_INTERVAL_FIELD
)

AUTHENTICATION_REPORT_INVALIDATION: Final = "authentication-report"

CACHE_INVALIDATION_EVENTS: Final = (
    "metadata-write",
    "metadata-delete",
    "failed-validation",
    AUTHENTICATION_REPORT_INVALIDATION,
)


@dataclass(frozen=True, kw_only=True)
class CachedRecord:
    """One cached metadata reading, bound to the revision title it was read at."""

    record_id: str
    item_id: str
    record: CredentialRecord
    stored_at: str


def entry_is_stale(*, entry: CachedRecord, interval_seconds: int, now: str) -> bool:
    """Whether `entry` has reached its maximum age at `now`.

    The boundary is INCLUSIVE, matching every other "at or after" boundary in this
    operation: an entry exactly at its maximum age is stale. An unparsable stored time
    is stale too, which is the fail-closed direction — a cache that cannot date an entry
    cannot vouch for its age.
    """
    limit = add_seconds(timestamp=entry.stored_at, seconds=interval_seconds)
    if limit is None:
        return True
    return is_at_or_after(moment=now, limit=limit) is not False


@dataclass(kw_only=True)
class MetadataCache:
    """A process-scoped, age-bounded metadata cache keyed by record and revision title."""

    interval_seconds: int = DEFAULT_CACHE_INTERVAL_SECONDS
    entries: dict[tuple[str, str], CachedRecord] = field(default_factory=dict)

    def store(self, *, item_id: str, record: CredentialRecord, now: str) -> CachedRecord:
        """Cache `record` as read at revision title `item_id`, replacing any prior entry."""
        entry = CachedRecord(
            record_id=record.record_id, item_id=item_id, record=record, stored_at=now
        )
        self.entries[(entry.record_id, item_id)] = entry
        return entry

    def lookup(self, *, record_id: str, current_item_id: str, now: str) -> CachedRecord | None:
        """The admissible entry for `record_id` at the caller's freshly-read title, or None.

        `current_item_id` MUST come from an uncached revision-title read. A stale-by-age
        entry is dropped as it is discovered, so one expired reading cannot be re-examined
        on every later lookup.
        """
        key = (record_id, current_item_id)
        entry = self.entries.get(key)
        if entry is None:
            return None
        if entry_is_stale(entry=entry, interval_seconds=self.interval_seconds, now=now):
            del self.entries[key]
            return None
        return entry

    def invalidate(self, *, record_id: str, event: str) -> Result[int, ManagerError]:
        """Drop every cached revision of `record_id`; returns how many entries went.

        An unregistered `event` is refused rather than treated as a plain eviction: the
        closed set is what makes "which events invalidate" reviewable, and a typo that
        silently evicted would pass while a typo that silently did NOT would leave a
        suspect credential cached as `valid`.
        """
        if event not in CACHE_INVALIDATION_EVENTS:
            return Failure(internal_bug(message=f"unregistered cache-invalidation event: {event}"))
        stale = [key for key in self.entries if key[0] == record_id]
        for key in stale:
            del self.entries[key]
        return Success(len(stale))
