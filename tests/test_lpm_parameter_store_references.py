"""Parameter Store reference entries are validated before anything is opened or read.

Proposed in SPECIFICATION/proposed_changes/lpm-parameter-store-reference-records.md
(the configuration-and-state contract in
SPECIFICATION/contracts.md): each `parameter_store_references` entry names
one canonical Parameter Store slot by reference, never by value. An entry with a missing
or extra member, an empty or wrongly-typed field, a malformed account, a relative
parameter name or manifest path, an unregistered provider-and-kind row or a duplicated
identity is an invalid configuration. So is any non-empty list under a backend other
than `parameter-store-reference`. Every such refusal is `invalid-request`, raised before
any lock, worker, store or target action.

The reference string these entries produce is the record's `value_ref`. It names where
the value lives, so it must be stable for one slot and distinct between slots.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_BACKEND = "parameter-store-reference"
_SLOT_PREFIX = "/gitops/v1/shared/providers/anthropic/claude-code/setup-token/"


def _module():
    path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_parameter_store_references.py"
    assert path.is_file(), "overseer/_lpm_parameter_store_references.py must exist"
    return importlib.import_module("_lpm_parameter_store_references")


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "provider": "anthropic",
        "account_id": "anthropic-4",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "source_account": "672283019497",
        "region": "us-west-2",
        "parameter_name": _SLOT_PREFIX + "anthropic-4",
        "reader_manifest": "/etc/hetzner-xubuntu-credentials/hxi-hetzner.json",
        "reader_consumer": "anthropic-setup-token-4",
    }
    entry.update(overrides)
    return entry


def _refusal(*, value: object, backend: str = _BACKEND) -> str:
    failure = _module().references_from_object(value=value, backend=backend).failure()
    assert failure.error_type == "invalid-request"
    return failure.message


def test_the_backend_name_is_the_proposal_s_spelling():
    assert _module().PARAMETER_STORE_REFERENCE_BACKEND == _BACKEND


def test_an_absent_or_empty_list_is_accepted_under_any_backend():
    module = _module()

    assert module.references_from_object(value=[], backend="onepassword").unwrap() == ()
    assert module.references_from_object(value=[], backend=_BACKEND).unwrap() == ()


def test_a_well_formed_entry_is_accepted_with_every_member_carried():
    accepted = _module().references_from_object(value=[_entry()], backend=_BACKEND).unwrap()

    assert len(accepted) == 1
    reference = accepted[0]
    assert reference.provider == "anthropic"
    assert reference.account_id == "anthropic-4"
    assert reference.kind == "claude-code-oauth"
    assert reference.purpose == "factory"
    assert reference.source_account == "672283019497"
    assert reference.region == "us-west-2"
    assert reference.parameter_name.endswith("/anthropic-4")
    assert reference.reader_manifest.startswith("/")
    assert reference.reader_consumer == "anthropic-setup-token-4"


def test_the_value_ref_names_the_slot_and_differs_between_slots():
    module = _module()
    four, five = module.references_from_object(
        value=[
            _entry(),
            _entry(
                account_id="anthropic-5",
                parameter_name=_SLOT_PREFIX + "anthropic-5",
                reader_consumer="anthropic-setup-token-5",
            ),
        ],
        backend=_BACKEND,
    ).unwrap()

    assert module.value_ref_for(reference=four) == (
        "parameter-store:672283019497:us-west-2:"
        "/gitops/v1/shared/providers/anthropic/claude-code/setup-token/anthropic-4"
    )
    assert module.value_ref_for(reference=four) != module.value_ref_for(reference=five)


def test_a_non_empty_list_under_another_backend_is_refused():
    assert _refusal(value=[_entry()], backend="onepassword") == (
        "parameter_store_references requires secret_store_backend parameter-store-reference"
    )


def test_a_non_list_value_is_refused():
    assert _refusal(value={"provider": "anthropic"}) == (
        "parameter_store_references must be an array"
    )


def test_a_non_object_entry_is_refused():
    assert _refusal(value=["anthropic-4"]) == ("parameter_store_references[0] must be an object")


def test_a_missing_member_is_refused_by_name():
    entry = _entry()
    del entry["reader_consumer"]

    assert _refusal(value=[entry]) == (
        "parameter_store_references[0] is missing member: reader_consumer"
    )


def test_an_extra_member_is_refused_by_name():
    assert _refusal(value=[_entry(value="sk-ant-never")]) == (
        "parameter_store_references[0] has unknown member: value"
    )


def test_an_empty_or_non_string_field_is_refused():
    assert _refusal(value=[_entry(region="")]) == (
        "parameter_store_references[0].region must be a non-empty string"
    )
    assert _refusal(value=[_entry(purpose=7)]) == (
        "parameter_store_references[0].purpose must be a non-empty string"
    )


def test_a_malformed_source_account_is_refused():
    assert _refusal(value=[_entry(source_account="67228301949")]) == (
        "parameter_store_references[0].source_account must be a 12-digit AWS account id"
    )


def test_a_relative_parameter_name_or_manifest_is_refused():
    assert _refusal(value=[_entry(parameter_name="gitops/v1/x")]) == (
        "parameter_store_references[0].parameter_name must be absolute"
    )
    assert _refusal(value=[_entry(reader_manifest="etc/manifest.json")]) == (
        "parameter_store_references[0].reader_manifest must be absolute"
    )


def test_an_unregistered_provider_and_kind_row_is_refused():
    assert _refusal(value=[_entry(kind="api-key")]) == (
        "parameter_store_references[0] names an unregistered provider and kind: "
        "anthropic api-key"
    )


def test_a_duplicate_identity_is_refused():
    second = _entry(parameter_name=_SLOT_PREFIX + "other")

    assert _refusal(value=[_entry(), second]) == (
        "parameter_store_references[1] duplicates the identity of an earlier entry"
    )
