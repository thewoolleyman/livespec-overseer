"""The parameter-store-reference backend keeps record METADATA in an owner-only local store.

Proposed in SPECIFICATION/proposed_changes/lpm-parameter-store-reference-records.md: this
backend has no values vault and no value writer. Its metadata lives under
`<manager-state>/parameter-store-reference/` and uses the same append-only logical-revision
protocol as every other SecretStore. That means the same committed, condition-failed and
unavailable distinctions, the same already-committed recognition of a fenced retry, and the
same owner-only file rules.

The store must survive the process. Every manager invocation is a fresh process, so a
revision committed by one invocation has to be the authoritative predecessor the next
invocation's conditional set is compared against.

An unsafe store file is reported, never repaired. A broader-permission or malformed file
makes every operation `unavailable` and leaves the file exactly as found, because
rewriting it would turn "I cannot read the record history" into "there is no history".
"""

from __future__ import annotations

import importlib
import os
import pathlib
import uuid

__all__: list[str] = []

_RECORD = str(uuid.UUID("2f9a1c4e-8b7d-4e21-9c3a-5d6e7f8a9b0c"))
_EFFECT_ONE = str(uuid.UUID("0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"))
_EFFECT_TWO = str(uuid.UUID("1b2c3d4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e"))


def _module():
    path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_reference_metadata_store.py"
    assert path.is_file(), "overseer/_lpm_reference_metadata_store.py must exist"
    return importlib.import_module("_lpm_reference_metadata_store")


def _store(*, state_dir: pathlib.Path):
    return _module().LocalReferenceMetadataStore(
        state_dir=state_dir, owner_uid=os.geteuid(), lock_timeout_seconds=5.0
    )


def _set(*, expected: str | None, desired: str, effect: str = _EFFECT_ONE):
    store_module = importlib.import_module("_lpm_store")
    return store_module.ConditionalSet(
        record_id=_RECORD, effect_id=effect, expected_record=expected, desired_record=desired
    )


def test_an_absent_store_reports_authoritative_absence(tmp_path):
    store = _store(state_dir=tmp_path / "state")

    assert store.metadata_get(record_id=_RECORD) == {"version": 1, "status": "ok", "item": None}
    assert store.metadata_list() == {"version": 1, "status": "ok", "items": [], "invalid": []}


def test_a_committed_genesis_survives_into_a_fresh_store_instance(tmp_path):
    state_dir = tmp_path / "state"

    committed = _store(state_dir=state_dir).credential_conditional_set(
        request=_set(expected=None, desired='{"r":1}')
    )
    reread = _store(state_dir=state_dir).metadata_get(record_id=_RECORD)

    assert committed == {"version": 1, "status": "committed"}
    assert reread["status"] == "ok"
    item = reread["item"]
    assert isinstance(item, dict)
    assert item["record"] == '{"r":1}'
    assert str(item["item_id"]).startswith(_RECORD)


def test_a_stale_expectation_is_condition_failed_and_changes_nothing(tmp_path):
    state_dir = tmp_path / "state"
    _store(state_dir=state_dir).credential_conditional_set(
        request=_set(expected=None, desired='{"r":1}')
    )
    before = (state_dir / "parameter-store-reference" / "metadata.json").read_bytes()

    refused = _store(state_dir=state_dir).credential_conditional_set(
        request=_set(expected='{"r":0}', desired='{"r":2}', effect=_EFFECT_TWO)
    )

    assert refused == {"version": 1, "status": "condition-failed"}
    assert (state_dir / "parameter-store-reference" / "metadata.json").read_bytes() == before


def test_a_fenced_retry_of_the_same_effect_is_already_committed(tmp_path):
    state_dir = tmp_path / "state"
    request = _set(expected=None, desired='{"r":1}')
    _store(state_dir=state_dir).credential_conditional_set(request=request)
    before = (state_dir / "parameter-store-reference" / "metadata.json").read_bytes()

    retried = _store(state_dir=state_dir).credential_conditional_set(request=request)

    assert retried == {"version": 1, "status": "committed"}
    assert (state_dir / "parameter-store-reference" / "metadata.json").read_bytes() == before


def test_the_store_file_is_owner_only_beneath_an_owner_only_directory(tmp_path):
    state_dir = tmp_path / "state"
    _store(state_dir=state_dir).credential_conditional_set(
        request=_set(expected=None, desired='{"r":1}')
    )
    directory = state_dir / "parameter-store-reference"

    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / "metadata.json").stat().st_mode & 0o777 == 0o600


def test_a_broader_permission_store_file_is_unavailable_and_left_untouched(tmp_path):
    state_dir = tmp_path / "state"
    _store(state_dir=state_dir).credential_conditional_set(
        request=_set(expected=None, desired='{"r":1}')
    )
    path = state_dir / "parameter-store-reference" / "metadata.json"
    path.chmod(0o644)
    before = path.read_bytes()
    store = _store(state_dir=state_dir)

    assert store.metadata_get(record_id=_RECORD) == {"version": 1, "status": "unavailable"}
    assert store.metadata_list() == {"version": 1, "status": "unavailable"}
    assert store.credential_conditional_set(
        request=_set(expected='{"r":1}', desired='{"r":2}', effect=_EFFECT_TWO)
    ) == {"version": 1, "status": "unavailable"}
    assert path.read_bytes() == before
    assert path.stat().st_mode & 0o777 == 0o644


def test_a_malformed_store_file_is_unavailable_and_left_untouched(tmp_path):
    directory = tmp_path / "state" / "parameter-store-reference"
    directory.mkdir(parents=True, mode=0o700)
    path = directory / "metadata.json"
    path.write_bytes(b'{"version":1,"chains":[]}')
    path.chmod(0o600)
    store = _store(state_dir=tmp_path / "state")

    assert store.metadata_get(record_id=_RECORD) == {"version": 1, "status": "unavailable"}
    assert store.credential_conditional_set(request=_set(expected=None, desired='{"r":1}')) == {
        "version": 1,
        "status": "unavailable",
    }
    assert path.read_bytes() == b'{"version":1,"chains":[]}'


def _write_raw(*, state_dir: pathlib.Path, payload: bytes) -> pathlib.Path:
    directory = state_dir / "parameter-store-reference"
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = directory / "metadata.json"
    path.write_bytes(payload)
    path.chmod(0o600)
    return path


def test_every_unreadable_shape_is_unavailable(tmp_path):
    shapes = [
        b"[]",
        b'{"version":2,"chains":{}}',
        b'{"chains":{},"version":1,"x":1}',
        b'{"chains":{"a":{}},"version":1}',
        b'{"chains":{"a":[1]},"version":1}',
        b'{"chains":{"a":[{"title":"t"}]},"version":1}',
        b'{"chains":{"a":[{"predecessor_sha256":"p","record":"r","title":7}]},"version":1}',
    ]
    for index, payload in enumerate(shapes):
        state_dir = tmp_path / f"state{index}"
        path = _write_raw(state_dir=state_dir, payload=payload)

        assert _store(state_dir=state_dir).metadata_list() == {
            "version": 1,
            "status": "unavailable",
        }, payload
        assert path.read_bytes() == payload


def test_an_empty_chain_on_disk_reads_as_absence(tmp_path):
    state_dir = tmp_path / "state"
    _write_raw(state_dir=state_dir, payload=b'{"chains":{"%s":[]},"version":1}' % _RECORD.encode())

    assert _store(state_dir=state_dir).metadata_get(record_id=_RECORD) == {
        "version": 1,
        "status": "ok",
        "item": None,
    }


def test_an_unusable_lock_makes_a_conditional_set_unavailable(tmp_path):
    directory = tmp_path / "state" / "parameter-store-reference"
    directory.mkdir(parents=True, mode=0o700)
    (directory / "metadata.lock").symlink_to(tmp_path / "elsewhere")

    assert _store(state_dir=tmp_path / "state").credential_conditional_set(
        request=_set(expected=None, desired='{"r":1}')
    ) == {"version": 1, "status": "unavailable"}
    assert not (directory / "metadata.json").exists()


def test_a_failed_write_reports_unavailable_rather_than_committed(tmp_path):
    results = importlib.import_module("_lpm_results")
    returns = importlib.import_module("overseer._vendor.returns.result")

    def refuse(**_kwargs: object):
        return returns.Failure(results.store_unavailable(message="disk full"))

    store = _module().LocalReferenceMetadataStore(
        state_dir=tmp_path / "state",
        owner_uid=os.geteuid(),
        lock_timeout_seconds=5.0,
        write_record=refuse,
    )

    assert store.credential_conditional_set(request=_set(expected=None, desired='{"r":1}')) == {
        "version": 1,
        "status": "unavailable",
    }
