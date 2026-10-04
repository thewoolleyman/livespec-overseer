"""Final provisioning: the value exists only inside this child, and the brain never sees it.

SPECIFICATION/contracts.md makes this boundary the ONE place in the operation that
legitimately holds a provisionable credential, and then closes every edge of it.

THE VALUE NEVER CROSSES THE BOUNDARY. "only after validation may it validate the
values-vault namespace item, resolve the exact `value_ref`, keep the raw bytes confined there
and pass them directly to the target adapter's write call. It MUST return either the target
adapter's secret-free commit-status shape or exactly
`{"version":1,"status":"store-unavailable"}` and MUST destroy its in-memory byte buffer when
the call ends; raw bytes MUST NOT cross its input or output boundary." So the assertions
below read what the TARGET was handed, and then assert the result object is closed — the two
halves of "it arrived where it was supposed to and nowhere else".

THE SELECTION BRAIN IS NOT AUTHORIZED TO READ ONE. "The selection brain ... MUST have
read-only metadata access, MUST NOT be authorized to read raw token values ... the selection
brain itself MUST NOT receive either value-reader token." Its refusal is structural rather
than careful: a `metadata-reader` addressing the values vault is refused by its registry row
before any child is spawned, which the recorded call list pins.

THE TARGET BINDING IS VALIDATED FIRST. "after successful role exec it MUST validate the
target binding before reading that variable or accessing the values vault" — and the
read-only validation "is not the write call", so its failure is still the pre-write
`store-unavailable`. A binding that does not validate must therefore leave no backend call
behind at all.

AN ABSENT, DOUBLED OR MALFORMED GENERATION ITEM IS `store-unavailable`, never an empty
value. "a values-vault outage, missing or malformed value, refused permission or SecretStore
deadline MUST return that `store-unavailable` shape before invoking the target adapter's
write call."

ONE CASE CANNOT GO THROUGH THE FIXTURE and uses a scripted `OpRunner` instead: a refusal
that arrives after the namespace get has already succeeded. Both calls are `item get`, and
the fixture refuses by VERB, so a verb-keyed refusal would fail the binding check and never
reach the branch under test.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import pathlib

__all__: list[str] = []

_VALUES_VAULT = "llm-provider-manager-token-values"
_METADATA_VAULT = "llm-provider-manager-token-metadata"

_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_OTHER_GENERATION = "9f1b3c2d-5e6a-4b7c-8d9e-0f1a2b3c4d5e"
_EFFECT = "a" * 64
_GENESIS = "0" * 64

_SENTINEL = "sk-ant-oat01-fixture-credential-value-never-logged"
_TOKEN = "fixture-value-reader-token-5e1b"
_VALUE_READER_VARIABLE = "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN"

_MACHINE_ID = "d" * 64
_STATE = "/home/operator/.local/state/livespec-overseer/llm-provider-manager"
_STORE_UNAVAILABLE = {"version": 1, "status": "store-unavailable"}
_COMMITTED_AT = "2026-09-13T09:00:00Z"


def _module(*, name):
    """Import one product module, asserting first that the module file is even there."""
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _namespace_fields():
    onepassword = importlib.import_module("_lpm_onepassword")
    return onepassword.namespace_item_fields(
        machine_id_sha256=_MACHINE_ID, effective_uid=1000, manager_state=_STATE
    )


def _namespace_item(*, vault=_VALUES_VAULT, item_id="namespace-1"):
    onepassword = importlib.import_module("_lpm_onepassword")
    return {
        "id": item_id,
        "title": onepassword.NAMESPACE_ITEM_TITLE,
        "vault": vault,
        "fields": _namespace_fields(),
    }


def _generation_title(*, value_generation=_GENERATION):
    onepassword = importlib.import_module("_lpm_onepassword")
    return onepassword.values_item_title(record_id=_RECORD, value_generation=value_generation)


def _generation_item(*, item_id="generation-1", credential=_SENTINEL):
    return {
        "id": item_id,
        "title": _generation_title(),
        "vault": _VALUES_VAULT,
        "fields": {"credential": credential},
    }


def _value_ref(*, value_generation=_GENERATION):
    onepassword = importlib.import_module("_lpm_onepassword")
    return onepassword.value_ref(record_id=_RECORD, value_generation=value_generation)


def _reference(*, value_generation=_GENERATION, reference=None):
    values = _module(name="_lpm_op_values")
    return values.ValueReference(
        record_id=_RECORD,
        value_generation=value_generation,
        value_ref=_value_ref(value_generation=value_generation) if reference is None else reference,
    )


def _entry(*, op_fixture, role_name="final-provisioning", op_executable=None):
    """One role process's own view of itself the moment the launcher's exec lands."""
    entrypoints = _module(name="_lpm_op_entrypoints")
    role = importlib.import_module("_lpm_roles").credential_role(name=role_name)
    variable = _VALUE_READER_VARIABLE if role is None or role.variable is None else role.variable
    return entrypoints.RoleEntry(
        role_name=role_name,
        op_executable=op_fixture.executable if op_executable is None else op_executable,
        retained_executable=op_fixture.executable,
        environ={"PATH": "/usr/bin:/bin", variable: _TOKEN},
        namespace=_namespace_fields(),
        timeout_seconds=30.0,
    )


def _outcome(*, status="committed", committed_at=_COMMITTED_AT):
    target = importlib.import_module("_lpm_target")
    return target.CommitOutcome(status=status, committed_at=committed_at)


@dataclasses.dataclass(kw_only=True)
class _RecordingTarget:
    """The registered target's write, recording exactly which bytes it was handed."""

    outcome: object
    seen: list = dataclasses.field(default_factory=list)

    def __call__(self, *, value):
        self.seen.append(value)
        return self.outcome


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ScriptedRunner:
    """Answers the enumeration and ONE named get, refusing every other get.

    The one case the per-verb fixture cannot express: a refusal arriving after the namespace
    binding has already been proved, when both calls are `item get`.
    """

    summaries: bytes
    namespace: bytes
    namespace_id: str

    def __call__(self, *, argv, stdin_bytes):
        op = importlib.import_module("_lpm_op")
        assert stdin_bytes is None, "a read vector streams nothing to the child"
        if argv[1:3] == ("item", "list"):
            return op.OpOutcome(exit_status=0, stdout=self.summaries)
        if argv[3] == self.namespace_id:
            return op.OpOutcome(exit_status=0, stdout=self.namespace)
        return op.OpOutcome(exit_status=1, stdout=b"")


def _summary_bytes(*, items):
    listing = [
        {"id": item["id"], "title": item["title"], "vault": {"name": item["vault"]}}
        for item in items
    ]
    return json.dumps(listing).encode("utf-8")


def _fields_bytes(*, item):
    return json.dumps(
        {
            "id": item["id"],
            "title": item["title"],
            "vault": {"name": item["vault"]},
            "fields": [
                {"id": label, "label": label, "type": "CONCEALED", "value": value}
                for label, value in item["fields"].items()
            ],
        }
    ).encode("utf-8")


def _provisioned(*, entry, reference=None, target=None, binding=None):
    entrypoints = _module(name="_lpm_op_entrypoints")
    return entrypoints.provisioning_result(
        entry=entry,
        reference=_reference() if reference is None else reference,
        binding=(lambda: None) if binding is None else binding,
        write=_RecordingTarget(outcome=_outcome()) if target is None else target,
    )


def test_the_value_is_read_inside_the_child_and_handed_only_to_the_target(op_fixture):
    """The target gets the bytes; the result object carries a status and nothing else."""
    role_results = importlib.import_module("_lpm_role_results")
    op_fixture.seed(items=[_namespace_item(), _generation_item()])
    target = _RecordingTarget(outcome=_outcome())

    answer = _provisioned(entry=_entry(op_fixture=op_fixture), target=target)

    assert target.seen == [_SENTINEL.encode("utf-8")]
    assert answer == {"version": 1, "status": "committed", "committed_at": _COMMITTED_AT}
    # The closed shape, asked of the module that owns the vocabulary rather than restated:
    # "no extra fields" is a LEAK control, and this is the one boundary that holds a value.
    assert (
        role_results.closed_result_defect(role_name="final-provisioning", mode=None, members=answer)
        is None
    )
    assert _SENTINEL not in json.dumps(answer)
    verbs = [tuple(argv[:2]) for argv in op_fixture.argvs()]
    assert set(verbs) == {("item", "list"), ("item", "get")}, "a read role never creates"
    # The role's WHOLE values-vault scope: one enumeration, the namespace get, and the one
    # referenced-value get. A fourth call would be a read its registry row does not grant.
    assert len(verbs) == 3
    assert {tuple(call["credential_names"]) for call in op_fixture.calls()} == {
        ("OP_SERVICE_ACCOUNT_TOKEN",)
    }


def test_the_metadata_brain_is_refused_the_values_vault_before_any_child(op_fixture):
    """The selection brain's reader is not authorized to read a raw value, structurally.

    Its refusal is the READER's own closed failure word, not final provisioning's. Each role
    has exactly one secret-free failure shape, and the refusing role here is the reader whose
    registry row does not reach the values vault — so a `store-unavailable` would be a word
    out of another role's vocabulary.
    """
    op_fixture.seed(items=[_namespace_item(), _generation_item()])
    target = _RecordingTarget(outcome=_outcome())

    answer = _provisioned(
        entry=_entry(op_fixture=op_fixture, role_name="metadata-reader"), target=target
    )

    assert answer == {"version": 1, "status": "unavailable"}
    assert target.seen == []
    assert op_fixture.calls() == [], "the registry row refuses before a token is ever used"


def test_a_reference_outside_this_record_s_registered_generation_is_store_unavailable(
    op_fixture,
):
    """An unregistered shape and a registered one naming another generation both refuse."""
    op_fixture.seed(items=[_namespace_item(), _generation_item()])
    unregistered = _provisioned(
        entry=_entry(op_fixture=op_fixture), reference=_reference(reference="op://elsewhere/x")
    )

    op_fixture.seed(items=[_namespace_item(), _generation_item()])
    foreign = _provisioned(
        entry=_entry(op_fixture=op_fixture),
        reference=_reference(reference=_value_ref(value_generation=_OTHER_GENERATION)),
    )

    assert unregistered == _STORE_UNAVAILABLE
    assert foreign == _STORE_UNAVAILABLE
    assert op_fixture.calls() == [], "a reference is judged before the vault is opened"


def test_an_absent_or_duplicated_generation_item_is_store_unavailable(op_fixture):
    """Neither is resolved: absence is not an empty value and a duplicate is not chosen."""
    op_fixture.seed(items=[_namespace_item()])
    absent_target = _RecordingTarget(outcome=_outcome())
    absent = _provisioned(entry=_entry(op_fixture=op_fixture), target=absent_target)

    op_fixture.seed(
        items=[_namespace_item(), _generation_item(), _generation_item(item_id="generation-2")]
    )
    duplicated = _provisioned(entry=_entry(op_fixture=op_fixture))

    assert absent == _STORE_UNAVAILABLE
    assert duplicated == _STORE_UNAVAILABLE
    assert absent_target.seen == []


def test_a_generation_item_that_is_not_one_non_empty_credential_field_is_store_unavailable(
    op_fixture,
):
    """An empty value and an extra field are both a malformed value, never a short one."""
    op_fixture.seed(items=[_namespace_item(), _generation_item(credential="")])
    empty = _provisioned(entry=_entry(op_fixture=op_fixture))

    extra = dict(_generation_item(), fields={"credential": _SENTINEL, "note": "x"})
    op_fixture.seed(items=[_namespace_item(), extra])
    widened = _provisioned(entry=_entry(op_fixture=op_fixture))

    assert empty == _STORE_UNAVAILABLE
    assert widened == _STORE_UNAVAILABLE


def test_a_refusing_values_vault_is_store_unavailable_before_the_target_write(op_fixture):
    """A refused enumeration, and a refused get of the generation item itself."""
    op_fixture.seed(items=[_namespace_item(), _generation_item()], refuse=("item list",))
    refused_list = _provisioned(entry=_entry(op_fixture=op_fixture))

    namespace = _namespace_item()
    values = _module(name="_lpm_op_values")
    vault = _module(name="_lpm_op_vault")
    roles = importlib.import_module("_lpm_roles")
    target = _RecordingTarget(outcome=_outcome())
    refused_get = values.provisioned_credential_result(
        access=vault.VaultAccess(
            runner=_ScriptedRunner(
                summaries=_summary_bytes(items=[namespace, _generation_item()]),
                namespace=_fields_bytes(item=namespace),
                namespace_id=namespace["id"],
            ),
            op_executable="/usr/bin/op",
            retained_executable="/usr/bin/op",
            role=roles.credential_role(name="final-provisioning"),
        ),
        namespace=_namespace_fields(),
        reference=_reference(),
        write=target,
    )

    assert refused_list == _STORE_UNAVAILABLE
    assert refused_get == _STORE_UNAVAILABLE
    assert target.seen == []


def test_a_commit_status_other_than_committed_is_reported_exactly_as_the_adapter_said(
    op_fixture,
):
    """`in-progress` is an AMBIGUOUS write and `uncommitted` a definitive one; both pass through."""
    op_fixture.seed(items=[_namespace_item(), _generation_item()])
    ambiguous = _provisioned(
        entry=_entry(op_fixture=op_fixture),
        target=_RecordingTarget(outcome=_outcome(status="in-progress", committed_at=None)),
    )

    op_fixture.seed(items=[_namespace_item(), _generation_item()])
    definitive = _provisioned(
        entry=_entry(op_fixture=op_fixture),
        target=_RecordingTarget(outcome=_outcome(status="uncommitted", committed_at=None)),
    )

    assert ambiguous == {"version": 1, "status": "in-progress", "committed_at": None}
    assert definitive == {"version": 1, "status": "uncommitted", "committed_at": None}


def test_a_target_binding_that_does_not_validate_stops_before_the_values_vault(op_fixture):
    """The read-only binding validation is not the write call, so its failure is pre-write."""
    op_fixture.seed(items=[_namespace_item(), _generation_item()])
    target = _RecordingTarget(outcome=_outcome())

    answer = _provisioned(
        entry=_entry(op_fixture=op_fixture),
        target=target,
        binding=lambda: "target_ref is bound to a different consumer run",
    )

    assert answer == _STORE_UNAVAILABLE
    assert target.seen == []
    assert op_fixture.calls() == [], "no values-vault access precedes a validated binding"


def test_an_unregistered_or_tokenless_role_never_reaches_a_backend_call(op_fixture):
    """A role the registry does not grant a token has no fallback, on any entrypoint."""
    entrypoints = _module(name="_lpm_op_entrypoints")
    store = _module(name="_lpm_store")
    op_fixture.seed(items=[_namespace_item(), _generation_item()])

    unregistered = _provisioned(entry=_entry(op_fixture=op_fixture, role_name="not-a-role"))
    tokenless = entrypoints.metadata_read_result(
        entry=_entry(op_fixture=op_fixture, role_name="target-status"),
        mode="get",
        record_id=_RECORD,
    )
    written = entrypoints.metadata_write_result(
        entry=_entry(op_fixture=op_fixture, role_name="target-status"),
        request=store.ConditionalSet(
            record_id=_RECORD,
            effect_id=_EFFECT,
            expected_record=None,
            desired_record='{"v":1}',
        ),
    )

    assert unregistered == _STORE_UNAVAILABLE
    assert tokenless == _STORE_UNAVAILABLE
    assert written == _STORE_UNAVAILABLE
    assert op_fixture.calls() == []


def test_the_reader_entrypoint_accepts_exactly_its_two_declared_input_shapes(op_fixture):
    """`get` with a record and `list` without one; every other pairing is refused.

    The relation is part of the shape, not a convenience: the contract gives the reader two
    whole objects rather than one object with an optional member, so a `get` with nothing to
    get and a `list` carrying a record are both inputs it never defined.
    """
    entrypoints = _module(name="_lpm_op_entrypoints")
    op_fixture.seed(items=[_namespace_item(vault=_METADATA_VAULT)])
    entry = _entry(op_fixture=op_fixture, role_name="metadata-reader")

    got = entrypoints.metadata_read_result(entry=entry, mode="get", record_id=_RECORD)
    listed = entrypoints.metadata_read_result(entry=entry, mode="list", record_id=None)
    unknown = entrypoints.metadata_read_result(entry=entry, mode="edit", record_id=_RECORD)
    recordless = entrypoints.metadata_read_result(entry=entry, mode="get", record_id=None)
    overspecified = entrypoints.metadata_read_result(entry=entry, mode="list", record_id=_RECORD)

    assert got == {"version": 1, "status": "ok", "item": None}
    assert listed == {"version": 1, "status": "ok", "items": [], "invalid": []}
    assert unknown == {"version": 1, "status": "unavailable"}
    assert recordless == {"version": 1, "status": "unavailable"}
    assert overspecified == {"version": 1, "status": "unavailable"}


def test_the_writer_entrypoint_appends_through_that_role_s_own_authority(op_fixture):
    """One entrypoint, one registry role, one create — the same store every reader uses."""
    entrypoints = _module(name="_lpm_op_entrypoints")
    store = _module(name="_lpm_store")
    revisions = importlib.import_module("_lpm_revisions")
    op_fixture.seed(items=[_namespace_item(vault=_METADATA_VAULT)])

    answer = entrypoints.metadata_write_result(
        entry=_entry(op_fixture=op_fixture, role_name="acquisition-writer"),
        request=store.ConditionalSet(
            record_id=_RECORD,
            effect_id=_EFFECT,
            expected_record=None,
            desired_record='{"v":1}',
        ),
    )

    assert answer == {"version": 1, "status": "committed"}
    appended = op_fixture.items(vault=_METADATA_VAULT)
    assert [item["title"] for item in appended if item["id"].startswith("fixture-")] == [
        revisions.revision_title(record_id=_RECORD, revision=1, effect_id=_EFFECT)
    ]
    assert appended[-1]["fields"]["predecessor_sha256"] == _GENESIS
