"""The metadata cache is five minutes by default, revision-gated, and invalidated by event.

SPECIFICATION/contracts.md bounds each entry's age by the configured
`backend_cache_interval_seconds`, keys entries by `record_id` AND the current logical revision's
`item_id`, and admits a hit only after an UNCACHED revision-title read agrees. These tests pin the
`item_id` half in particular: a same-generation status revision must not be able to hit an older
`valid` entry, which is exactly the stale read a record-keyed or generation-keyed cache could not
see.

Every miss — absent, stale-by-age, superseded-by-revision — is the contract's prescribed
degradation to a store read rather than an error, and nothing here can make a record
eligible.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_cache.py"
    assert module_path.is_file(), "overseer/_lpm_cache.py must exist"
    return (
        importlib.import_module("_lpm_cache"),
        importlib.import_module("_lpm_record"),
    )


def _record(records, **changes):
    fields = {
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": "one@example.test",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-09-12T09:00:00Z",
        "expires_at": None,
        "last_validated": "2026-09-12T10:00:00Z",
        "value_generation": _GENERATION,
        "value_ref": f"op://provisionable/{_RECORD_ID}/value#{_GENERATION}",
        "previous_value_ref": None,
    }
    fields.update(changes)
    return records.CredentialRecord(**fields)


def test_the_default_maximum_entry_age_is_five_minutes_from_the_configured_field():
    cache_module, _ = _modules()

    assert cache_module.DEFAULT_CACHE_INTERVAL_SECONDS == 300
    assert cache_module.CACHE_INTERVAL_FIELD == "backend_cache_interval_seconds"
    assert cache_module.MetadataCache().interval_seconds == 300


def test_a_stored_reading_is_returned_only_at_the_revision_title_it_was_read_at():
    cache_module, records = _modules()
    cache = cache_module.MetadataCache()
    stored = cache.store(item_id="rev-1", record=_record(records), now="2026-09-12T10:00:00Z")

    hit = cache.lookup(record_id=_RECORD_ID, current_item_id="rev-1", now="2026-09-12T10:04:59Z")

    assert hit == stored
    assert hit.record.status == "valid"
    assert (
        cache.lookup(record_id=_RECORD_ID, current_item_id="rev-2", now="2026-09-12T10:00:01Z")
        is None
    )
    assert (
        cache.lookup(record_id=_GENERATION, current_item_id="rev-1", now="2026-09-12T10:00:01Z")
        is None
    )


def test_an_entry_exactly_at_its_maximum_age_is_stale_and_is_dropped_as_it_is_found():
    cache_module, records = _modules()
    cache = cache_module.MetadataCache(interval_seconds=300)
    entry = cache.store(item_id="rev-1", record=_record(records), now="2026-09-12T10:00:00Z")

    assert (
        cache_module.entry_is_stale(entry=entry, interval_seconds=300, now="2026-09-12T10:04:59Z")
        is False
    )
    assert (
        cache_module.entry_is_stale(entry=entry, interval_seconds=300, now="2026-09-12T10:05:00Z")
        is True
    )
    assert (
        cache.lookup(record_id=_RECORD_ID, current_item_id="rev-1", now="2026-09-12T10:05:00Z")
        is None
    )
    assert cache.entries == {}


def test_an_entry_whose_stored_time_cannot_be_dated_is_stale_rather_than_trusted():
    cache_module, records = _modules()
    entry = cache_module.CachedRecord(
        record_id=_RECORD_ID, item_id="rev-1", record=_record(records), stored_at="just now"
    )

    assert (
        cache_module.entry_is_stale(entry=entry, interval_seconds=300, now="2026-09-12T10:00:00Z")
        is True
    )
    assert cache_module.entry_is_stale(entry=entry, interval_seconds=300, now="whenever") is True


def test_invalidation_drops_every_revision_of_one_record_and_leaves_its_neighbours():
    cache_module, records = _modules()
    cache = cache_module.MetadataCache()
    neighbour = _record(records, record_id=_GENERATION)
    for item_id in ("rev-1", "rev-2"):
        _ = cache.store(item_id=item_id, record=_record(records), now="2026-09-12T10:00:00Z")
    _ = cache.store(item_id="rev-1", record=neighbour, now="2026-09-12T10:00:00Z")

    dropped = cache.invalidate(
        record_id=_RECORD_ID, event=cache_module.AUTHENTICATION_REPORT_INVALIDATION
    )

    assert dropped.unwrap() == 2
    assert list(cache.entries) == [(_GENERATION, "rev-1")]
    assert cache.invalidate(record_id=_RECORD_ID, event="metadata-write").unwrap() == 0


def test_every_required_invalidation_event_is_registered_and_a_typo_is_a_caller_bug():
    cache_module, _ = _modules()

    assert set(cache_module.CACHE_INVALIDATION_EVENTS) == {
        "metadata-write",
        "metadata-delete",
        "failed-validation",
        "authentication-report",
    }
    refusal = cache_module.MetadataCache().invalidate(
        record_id=_RECORD_ID, event="authentication_report"
    )
    assert refusal.failure().error_type == "internal-bug"
    assert refusal.failure().message == (
        "unregistered cache-invalidation event: authentication_report"
    )
