"""The SecretStore wire shapes, and an in-memory backend that really enforces them.

SPECIFICATION/contracts.md fixes every result crossing the credential-role launcher
boundary as exactly one JSON object with no extra fields, and requires `item:null` to
assert AUTHORITATIVE ABSENCE only after the backend call and complete chain validation
found no valid or invalid chain. A reader `unavailable`, a deadline, an abnormal exit or
any nonconforming output maps to `store-unavailable` and NEVER to absence — because absence
is what permits a genesis create, and a create against an unknown store is how two
managers end up believing they each created the first revision.

The in-memory backend exists so a dependent slice can test recovery hermetically, which
only works if it makes the same distinctions the real backend does: a fenced
byte-identical retry reads as `committed`, a defeated writer reads as `condition-failed`,
and an invalid chain refuses every mutation while leaving other records usable.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OTHER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_EFFECT = "a" * 64
_NEXT_EFFECT = "b" * 64


def _store_module():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_store.py"
    assert module_path.is_file(), "overseer/_lpm_store.py must exist"
    return importlib.import_module("_lpm_store")


def _set(*, store, module, record_id=_RECORD, expected=None, desired='{"v":1}', effect=_EFFECT):
    return store.credential_conditional_set(
        request=module.ConditionalSet(
            record_id=record_id,
            effect_id=effect,
            expected_record=expected,
            desired_record=desired,
        )
    )


def test_the_closed_result_shapes_have_exactly_their_declared_members():
    module = _store_module()

    assert module.metadata_get_result(status="ok") == {"version": 1, "status": "ok", "item": None}
    assert module.metadata_get_result(
        status="invalid",
        payload=module.invalid_chain_descriptor(record_id=_RECORD, reason="gap"),
    ) == {
        "version": 1,
        "status": "invalid",
        "invalid": {"record_id": _RECORD, "reason": "gap"},
    }
    assert module.metadata_get_result(status="unavailable") == {
        "version": 1,
        "status": "unavailable",
    }
    assert module.metadata_list_result(status="ok") == {
        "version": 1,
        "status": "ok",
        "items": [],
        "invalid": [],
    }
    assert module.metadata_list_result(status="unavailable") == {
        "version": 1,
        "status": "unavailable",
    }
    assert module.set_result(status="condition-failed") == {
        "version": 1,
        "status": "condition-failed",
    }
    assert module.metadata_item_envelope(item_id="t", record='{"v":1}') == {
        "item_id": "t",
        "record": '{"v":1}',
    }


def test_an_unwritten_record_is_authoritative_absence_and_a_genesis_create_commits():
    module = _store_module()
    store = module.InMemorySecretStore()

    assert store.metadata_get(record_id=_RECORD)["item"] is None
    assert _set(store=store, module=module)["status"] == "committed"
    envelope = store.metadata_get(record_id=_RECORD)["item"]
    assert envelope["record"] == '{"v":1}'
    assert envelope["item_id"] == f"{_RECORD}-m00000000000000000001-{_EFFECT}"


def test_a_byte_identical_fenced_retry_reads_as_committed_without_a_second_revision():
    module = _store_module()
    store = module.InMemorySecretStore()
    _ = _set(store=store, module=module)

    retry = _set(store=store, module=module)

    assert retry["status"] == "committed"
    assert len(store.items[_RECORD]) == 1, "a late duplicate cannot outrank a later revision"


def test_a_defeated_writer_is_condition_failed_rather_than_unavailable():
    module = _store_module()
    store = module.InMemorySecretStore()
    _ = _set(store=store, module=module)

    stale = _set(store=store, module=module, expected=None, desired='{"v":9}', effect=_NEXT_EFFECT)
    advanced = _set(
        store=store,
        module=module,
        expected='{"v":1}',
        desired='{"v":2}',
        effect=_NEXT_EFFECT,
    )

    # `condition-failed` definitively says no change was made BECAUSE the comparison
    # failed; it is not a synonym for "the store could not be reached".
    assert stale["status"] == "condition-failed"
    assert advanced["status"] == "committed"
    assert store.metadata_get(record_id=_RECORD)["item"]["record"] == '{"v":2}'


def test_an_invalid_chain_refuses_its_own_mutations_while_other_records_stay_usable():
    module = _store_module()
    revisions = importlib.import_module("_lpm_revisions")
    store = module.InMemorySecretStore()
    _ = _set(store=store, module=module)
    _ = _set(store=store, module=module, record_id=_OTHER, desired='{"v":7}')
    store.items[_RECORD].append(
        revisions.RevisionItem(
            title=revisions.revision_title(record_id=_RECORD, revision=1, effect_id=_NEXT_EFFECT),
            predecessor_sha256="0" * 64,
            record='{"v":5}',
        )
    )

    broken = store.metadata_get(record_id=_RECORD)
    listed = store.metadata_list()
    mutation = _set(store=store, module=module, expected='{"v":1}', desired='{"v":2}')

    assert broken["status"] == "invalid"
    assert broken["invalid"] == {"record_id": _RECORD, "reason": "conflict"}
    assert mutation["status"] == "unavailable"
    assert listed["invalid"] == [{"record_id": _RECORD, "reason": "conflict"}]
    assert [envelope["record"] for envelope in listed["items"]] == ['{"v":7}']


def test_a_list_orders_envelopes_by_item_id_and_descriptors_by_record_id():
    module = _store_module()
    store = module.InMemorySecretStore()
    _ = _set(store=store, module=module, record_id=_OTHER, desired='{"v":2}')
    _ = _set(store=store, module=module, record_id=_RECORD, desired='{"v":1}')

    # A record whose chain is present but EMPTY is absent, not an item and not a defect;
    # it must appear in neither list rather than as an envelope with a null record.
    store.items["c0ffee00-0000-4000-8000-000000000000"] = []

    listed = store.metadata_list()

    assert len(listed["items"]) == 2
    assert listed["invalid"] == []
    assert [envelope["item_id"] for envelope in listed["items"]] == sorted(
        envelope["item_id"] for envelope in listed["items"]
    )
    assert listed["items"][0]["item_id"].startswith(_RECORD)


def test_an_unavailable_backend_never_answers_absence_or_a_definitive_no_change():
    module = _store_module()
    store = module.InMemorySecretStore(available=False)

    assert store.metadata_get(record_id=_RECORD) == {"version": 1, "status": "unavailable"}
    assert store.metadata_list() == {"version": 1, "status": "unavailable"}
    assert _set(store=store, module=module) == {"version": 1, "status": "unavailable"}
