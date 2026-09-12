"""Three vaults, one namespace binding, and create as the only mutation verb.

SPECIFICATION/contracts.md binds the three initial vaults to EXACTLY ONE manager state
namespace — one host identity, effective uid and canonical state path — and requires every
role to validate that binding before any SecretStore read or create, with absence,
duplicates, mismatch or an unsafe machine-id source returning `store-unavailable` before
credential data is read or mutated.

A forgeable host identity is no identity at all, which is why the `machine_id_sha256` field
is derived from a strictly-shaped value: one newline-trimmed lowercase 32-hex string, or
nothing. An uppercase spelling or a second line is refused rather than hashed.

The create-only rule is pinned here as an ARGV shape because that is where it is actually
enforceable: `op item create --vault <vault> -`, streaming the item JSON over the child's
standard input. No `op item edit` exists in this backend's vocabulary, and no assignment
argument, template file or environment field may carry a credential, because all three are
readable from outside the process.
"""

from __future__ import annotations

import hashlib
import importlib
import pathlib

__all__: list[str] = []

_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _onepassword():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_onepassword.py"
    assert module_path.is_file(), "overseer/_lpm_onepassword.py must exist"
    return importlib.import_module("_lpm_onepassword")


def test_the_three_vaults_keep_their_declared_names_and_separate_concerns():
    module = _onepassword()

    assert module.ACQUISITION_VAULT == "llm-provider-manager-acquisition"
    assert module.METADATA_VAULT == "llm-provider-manager-token-metadata"
    assert module.VALUES_VAULT == "llm-provider-manager-token-values"
    assert module.NAMESPACE_ITEM_TITLE == "llm-provider-manager-namespace"


def test_a_machine_id_is_hashed_only_when_it_is_exactly_one_lowercase_32_hex_value():
    module = _onepassword()
    machine_id = "0123456789abcdef0123456789abcdef"

    assert module.machine_id_digest(machine_id=f"{machine_id}\n") == (
        hashlib.sha256(machine_id.encode("ascii")).hexdigest()
    )
    assert module.machine_id_digest(machine_id=machine_id.upper()) is None
    assert module.machine_id_digest(machine_id="0123") is None
    assert module.machine_id_digest(machine_id=f"{machine_id}\nsecond") is None


def test_the_namespace_item_carries_exactly_its_four_identity_fields():
    module = _onepassword()

    fields = module.namespace_item_fields(
        machine_id_sha256="d" * 64, effective_uid=1000, manager_state="/home/o/.local/state/lpm/"
    )

    assert fields == {
        "version": "1",
        "machine_id_sha256": "d" * 64,
        "effective_uid": "1000",
        "manager_state": "/home/o/.local/state/lpm",
    }
    assert (
        module.namespace_item_fields(
            machine_id_sha256="d" * 64, effective_uid=0, manager_state="/"
        )["effective_uid"]
        == "0"
    )


def test_a_namespace_item_from_another_host_uid_or_state_path_is_refused():
    module = _onepassword()
    expected = module.namespace_item_fields(
        machine_id_sha256="d" * 64, effective_uid=1000, manager_state="/state"
    )

    assert module.namespace_mismatch(stored=expected, expected=expected) is None
    assert module.namespace_mismatch(stored=[], expected=expected) == (
        "namespace item is not an object"
    )
    assert module.namespace_mismatch(stored={"version": "1"}, expected=expected) == (
        "namespace item has the wrong application fields"
    )
    assert (
        module.namespace_mismatch(
            stored={**expected, "machine_id_sha256": "e" * 64}, expected=expected
        )
        == "namespace item machine_id_sha256 names another manager namespace"
    )
    assert (
        module.namespace_mismatch(stored={**expected, "effective_uid": "1001"}, expected=expected)
        == "namespace item effective_uid names another manager namespace"
    )


def test_the_value_reference_keeps_its_literal_wire_syntax_and_rejects_every_other_shape():
    module = _onepassword()

    reference = module.value_ref(record_id=_RECORD, value_generation=_GENERATION)

    assert reference == (
        f"op://llm-provider-manager-token-values/{_RECORD}-{_GENERATION}/credential"
    )
    assert module.previous_value_ref(record_id=_RECORD, prior_generation=_GENERATION) == reference
    assert module.values_item_title(record_id=_RECORD, value_generation=_GENERATION) == (
        f"{_RECORD}-{_GENERATION}"
    )
    assert module.value_ref_is_registered(reference=reference)
    assert not module.value_ref_is_registered(
        reference=f"op://llm-provider-manager-token-metadata/{_RECORD}-{_GENERATION}/credential"
    )
    assert not module.value_ref_is_registered(reference=f"{reference}/extra")
    assert not module.value_ref_is_registered(reference="op://vault/item/field")


def test_create_is_the_only_mutation_verb_and_the_item_rides_on_standard_input():
    module = _onepassword()

    argv = module.op_item_create_argv(op_executable="/usr/bin/op", vault=module.VALUES_VAULT)

    assert argv == (
        "/usr/bin/op",
        "item",
        "create",
        "--vault",
        "llm-provider-manager-token-values",
        "-",
    )
    # The credential never appears as an argument: `-` is the standard-input marker, and
    # there is no `edit` verb anywhere in this backend's vocabulary.
    assert "edit" not in argv
    assert not any(part.startswith("credential=") for part in argv)
