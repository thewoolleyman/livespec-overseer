"""The OnePassword metadata reads: one namespace-bound enumeration, then the whole chain.

SPECIFICATION/contracts.md puts three separate requirements on every metadata read this
backend performs, and they are only meaningful together because each one is about the SAME
enumeration.

THE NAMESPACE BINDING IS CHECKED BEFORE CREDENTIAL DATA IS READ. "Before every SecretStore
read or create, the role MUST enumerate the namespace title in each vault that call will
access and require exactly one well-formed item whose three identity fields equal the
current manager namespace; absence, duplicates, mismatch or an unsafe machine-id source MUST
return `store-unavailable` before reading credential data or mutating." So a vault whose
namespace item is absent, doubled or bound to another manager must produce NO credential
get at all — which is what the recorded call list below is asserted against, rather than
merely the answer that came back.

THE RESERVED TITLE IS EXCLUDED FROM THE RECORD GRAMMAR. "Every metadata-vault enumeration
MUST reserve exactly that one title: the namespace-binding check MUST validate it
independently, while credential metadata get, list and chain reconciliation MUST exclude
exactly that title before applying revision-title or application-field validation." A
namespace item read as a record would be a chain with a title no revision grammar accepts.

A FAILURE IS NEVER ABSENCE. "The parent MUST map reader `unavailable`, a deadline, abnormal
exit or any nonconforming output to `store-unavailable`, never to absence", and `item:null`
"asserts authoritative absence only after the backend call and complete applicable chain
validation found no valid or invalid chain for that requested record". Every refusal below
is therefore asserted to be `unavailable` rather than an empty answer, because absence is
what licenses a genesis create.

THE ASSERTIONS GO THROUGH A REAL `op` CHILD. The fixture `op` is a real subprocess whose
vaults are a JSON file the harness owns, so these reads exercise the production argv
builders, the production spawn and the production output parse. One case cannot be
expressed that way — a refusal that arrives AFTER the namespace get has already succeeded,
since the fixture refuses by VERB and both calls are `item get` — so that single case uses a
scripted `OpRunner` instead. The fixture proves the real path; the script proves the
sequence.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import pathlib

__all__: list[str] = []

_TOKEN = "fixture-metadata-reader-token-9c2d"
_READER_VARIABLE = "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN"
_METADATA_VAULT = "llm-provider-manager-token-metadata"
_VALUES_VAULT = "llm-provider-manager-token-values"

_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OTHER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_EFFECT = "a" * 64
_NEXT_EFFECT = "b" * 64
_GENESIS = "0" * 64

_MACHINE_ID = "d" * 64
_STATE = "/home/operator/.local/state/livespec-overseer/llm-provider-manager"
_UNAVAILABLE = {"version": 1, "status": "unavailable"}


def _module(*, name):
    """Import one product module, asserting first that the module file is even there.

    The `is_file()` assertion is what makes an unimplemented slice fail as a genuine
    assertion rather than as a collection-time import error, which would prove only
    unimportability.
    """
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _namespace_fields():
    onepassword = importlib.import_module("_lpm_onepassword")
    return onepassword.namespace_item_fields(
        machine_id_sha256=_MACHINE_ID, effective_uid=1000, manager_state=_STATE
    )


def _namespace_item(*, item_id="namespace-1", vault=_METADATA_VAULT, fields=None):
    onepassword = importlib.import_module("_lpm_onepassword")
    return {
        "id": item_id,
        "title": onepassword.NAMESPACE_ITEM_TITLE,
        "vault": vault,
        "fields": _namespace_fields() if fields is None else fields,
    }


def _title(*, record_id=_RECORD, revision=1, effect_id=_EFFECT):
    revisions = importlib.import_module("_lpm_revisions")
    return revisions.revision_title(record_id=record_id, revision=revision, effect_id=effect_id)


def _revision(
    *, record_id=_RECORD, revision=1, effect_id=_EFFECT, predecessor=_GENESIS, record='{"v":1}'
):
    """One well-formed revision item; a malformed variant is a `dict(...)` override of it."""
    item_title = _title(record_id=record_id, revision=revision, effect_id=effect_id)
    return {
        "id": f"item-{item_title}",
        "title": item_title,
        "vault": _METADATA_VAULT,
        "fields": {"predecessor_sha256": predecessor, "record": record},
    }


def _digest_of(*, record):
    return importlib.import_module("_lpm_revisions").predecessor_digest(record=record)


def _access(*, op_fixture, role_name="metadata-reader", op_executable=None, retained=None):
    """A production `op` child bound to the fixture, under one registry role's authority."""
    vault = _module(name="_lpm_op_vault")
    op = importlib.import_module("_lpm_op")
    roles = importlib.import_module("_lpm_roles")
    return vault.VaultAccess(
        runner=op.HostOpChild(
            environ={"PATH": "/usr/bin:/bin", _READER_VARIABLE: _TOKEN},
            variable=_READER_VARIABLE,
            timeout_seconds=30.0,
        ),
        op_executable=op_fixture.executable if op_executable is None else op_executable,
        retained_executable=op_fixture.executable if retained is None else retained,
        role=roles.credential_role(name=role_name),
    )


def _get(*, access, record_id=_RECORD):
    return _module(name="_lpm_op_metadata").metadata_get_answer(
        access=access, namespace=_namespace_fields(), record_id=record_id
    )


def _listed(*, access):
    return _module(name="_lpm_op_metadata").metadata_list_answer(
        access=access, namespace=_namespace_fields()
    )


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
                {"id": label, "label": label, "type": "STRING", "value": value}
                for label, value in item["fields"].items()
            ],
        }
    ).encode("utf-8")


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ScriptedRunner:
    """An `OpRunner` that answers the enumeration and ONE named get, refusing every other.

    It exists for exactly one case the per-verb fixture cannot express: a backend refusal
    that arrives after the namespace binding has already been proved. Both calls are
    `item get`, so a verb-keyed refusal would fail the namespace check instead and never
    reach the branch under test.
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


def test_a_metadata_get_reads_one_chain_and_decodes_its_current_logical_revision(op_fixture):
    """The highest contiguous revision, by its own title, carrying the DECODED record.

    The contract fixes the envelope's `record` as "whatever canonical JSON value decoded
    from that item's canonical `record` field", so the stored text is decoded here rather
    than forwarded — a reader handed the text would have to parse it a second time, at a
    boundary the contract has already closed.
    """
    op_fixture.seed(
        items=[
            _namespace_item(),
            _revision(),
            _revision(
                revision=2,
                effect_id=_NEXT_EFFECT,
                predecessor=_digest_of(record='{"v":1}'),
                record='{"v":2}',
            ),
        ]
    )

    answer = _get(access=_access(op_fixture=op_fixture))

    assert answer["status"] == "ok"
    assert answer["item"]["item_id"] == _title(revision=2, effect_id=_NEXT_EFFECT)
    assert answer["item"]["record"] == {"v": 2}
    verbs = [argv[:2] for argv in op_fixture.argvs()]
    assert verbs.count(["item", "list"]) == 1, "one enumeration serves the binding and the chain"
    assert {tuple(verb) for verb in verbs} == {("item", "list"), ("item", "get")}


def test_a_metadata_list_answers_every_chain_in_order_and_reserves_the_namespace_title(
    op_fixture,
):
    """Envelopes ordered by lexical `item_id`, with the reserved title excluded as a record."""
    op_fixture.seed(
        items=[_revision(record_id=_OTHER, record='{"v":7}'), _namespace_item(), _revision()]
    )

    answer = _listed(access=_access(op_fixture=op_fixture))

    assert answer["status"] == "ok"
    assert answer["invalid"] == []
    assert [envelope["item_id"] for envelope in answer["items"]] == [
        _title(),
        _title(record_id=_OTHER),
    ]
    assert [envelope["record"] for envelope in answer["items"]] == [{"v": 1}, {"v": 7}]


def test_an_unwritten_record_is_authoritative_absence_only_after_a_whole_enumeration(
    op_fixture,
):
    """A namespace-bound vault holding no revision for this record IS absence."""
    op_fixture.seed(items=[_namespace_item()])
    access = _access(op_fixture=op_fixture)

    assert _get(access=access) == {"version": 1, "status": "ok", "item": None}
    assert _listed(access=access) == {"version": 1, "status": "ok", "items": [], "invalid": []}


def test_an_invalid_chain_is_a_secret_free_descriptor_rather_than_absence(op_fixture):
    """A gap makes that one record ineligible; `item:null` would license a genesis create."""
    op_fixture.seed(
        items=[
            _namespace_item(),
            _revision(revision=2, predecessor=_digest_of(record='{"v":1}'), record='{"v":2}'),
            _revision(record_id=_OTHER, record='{"v":7}'),
        ]
    )

    answer = _get(access=_access(op_fixture=op_fixture))
    listed = _listed(access=_access(op_fixture=op_fixture))

    assert answer == {
        "version": 1,
        "status": "invalid",
        "invalid": {"record_id": _RECORD, "reason": "gap"},
    }
    assert listed["invalid"] == [{"record_id": _RECORD, "reason": "gap"}]
    assert [envelope["record"] for envelope in listed["items"]] == [{"v": 7}]


def test_a_refusing_or_garbling_backend_is_unavailable_and_never_absence(op_fixture):
    """A non-zero exit and nonconforming output both make the OUTCOME unknown."""
    op_fixture.seed(items=[_namespace_item(), _revision()], refuse=("item list",))
    refused_get = _get(access=_access(op_fixture=op_fixture))
    refused_list = _listed(access=_access(op_fixture=op_fixture))

    op_fixture.seed(items=[_namespace_item(), _revision()], garble=("item list",))
    garbled = _get(access=_access(op_fixture=op_fixture))

    op_fixture.seed(items=[_namespace_item(), _revision()], refuse=("item get",))
    refused_namespace = _get(access=_access(op_fixture=op_fixture))

    assert refused_get == _UNAVAILABLE
    assert refused_list == _UNAVAILABLE
    assert garbled == _UNAVAILABLE
    assert refused_namespace == _UNAVAILABLE


def test_a_refusal_after_the_namespace_binding_held_is_still_unavailable():
    """The credential get's own refusal is not softened by a namespace check that passed."""
    vault = _module(name="_lpm_op_vault")
    roles = importlib.import_module("_lpm_roles")
    namespace = _namespace_item()
    access = vault.VaultAccess(
        runner=_ScriptedRunner(
            summaries=_summary_bytes(items=[namespace, _revision()]),
            namespace=_fields_bytes(item=namespace),
            namespace_id=namespace["id"],
        ),
        op_executable="/usr/bin/op",
        retained_executable="/usr/bin/op",
        role=roles.credential_role(name="metadata-reader"),
    )

    assert _get(access=access) == _UNAVAILABLE
    assert _listed(access=access) == _UNAVAILABLE


def test_an_absent_duplicated_or_foreign_namespace_item_refuses_before_a_credential_get(
    op_fixture,
):
    """All three namespace defects refuse, and none of them reads a revision item.

    The recorded call list is the assertion that matters: an answer of `unavailable` would
    look identical whether the binding was checked first or merely reported afterwards.
    """
    foreign = dict(_namespace_fields(), manager_state="/home/other/.local/state")

    op_fixture.seed(items=[_revision()])
    absent = _get(access=_access(op_fixture=op_fixture))
    absent_calls = [argv[:2] for argv in op_fixture.argvs()]

    op_fixture.seed(items=[_namespace_item(), _namespace_item(item_id="namespace-2"), _revision()])
    duplicated = _get(access=_access(op_fixture=op_fixture))
    duplicated_calls = [argv[:2] for argv in op_fixture.argvs()]

    op_fixture.seed(items=[_namespace_item(fields=foreign), _revision()])
    mismatched = _get(access=_access(op_fixture=op_fixture))

    assert absent == _UNAVAILABLE
    assert duplicated == _UNAVAILABLE
    assert mismatched == _UNAVAILABLE
    assert absent_calls == [["item", "list"]], "absence is decided without any get"
    assert duplicated_calls == [["item", "list"]], "a duplicate is never chosen between"


def test_a_role_off_the_retained_path_or_outside_its_vault_scope_never_spawns_op(op_fixture):
    """Both authorization refusals happen before the first child, so nothing is read."""
    op_fixture.seed(items=[_namespace_item(), _revision()])

    substituted = _get(access=_access(op_fixture=op_fixture, op_executable="/usr/local/bin/op"))
    unscoped = _module(name="_lpm_op_vault").namespace_bound_summaries(
        access=_access(op_fixture=op_fixture), vault=_VALUES_VAULT, expected=_namespace_fields()
    )

    assert substituted == _UNAVAILABLE
    assert unscoped.failure() == "metadata-reader is not scoped to that vault"
    assert op_fixture.calls() == [], "authorization is decided before any backend call"


def test_an_item_outside_the_metadata_grammar_or_field_envelope_is_unavailable(op_fixture):
    """A title no revision grammar accepts, and a revision item with the wrong fields."""
    foreign = dict(_revision(), title="login-not-a-revision")
    op_fixture.seed(items=[_namespace_item(), foreign])
    foreign_title = _listed(access=_access(op_fixture=op_fixture))

    wrong_fields = dict(_revision(), fields={"record": '{"v":1}', "e": "x"})
    op_fixture.seed(items=[_namespace_item(), wrong_fields])
    foreign_fields = _get(access=_access(op_fixture=op_fixture))

    assert foreign_title == _UNAVAILABLE
    assert foreign_fields == _UNAVAILABLE


def test_a_record_field_that_is_unparseable_or_non_canonical_is_unavailable(op_fixture):
    """Both are the contract's `store-unavailable`, and neither may be read as absence.

    Non-canonical matters as much as unparseable because the predecessor digest is taken
    over the canonical `record` bytes: a stored spelling that no second encoder reproduces
    would make every later comparison fail for a reason nobody introduced.
    """
    op_fixture.seed(items=[_namespace_item(), _revision(record="{not json")])
    unparseable = _get(access=_access(op_fixture=op_fixture))

    op_fixture.seed(items=[_namespace_item(), _revision(record='{"v": 1}')])
    non_canonical = _get(access=_access(op_fixture=op_fixture))

    assert unparseable == _UNAVAILABLE
    assert non_canonical == _UNAVAILABLE


def test_the_enumeration_answer_is_closed_to_exactly_an_item_id_and_a_title():
    """Every other `op item list` shape is a defect naming no value it was handed."""
    items = _module(name="_lpm_op_items")

    assert items.parse_item_summaries(stdout=b'[{"id":"a","title":"t"}]').unwrap() == (
        items.OpItem(item_id="a", title="t"),
    )
    assert items.parse_item_summaries(stdout=b"\xff").failure() == "output that is not UTF-8"
    assert items.parse_item_summaries(stdout=b"not json").failure() == (
        "output that is not one JSON value"
    )
    assert items.parse_item_summaries(stdout=b'{"id":"a"}').failure() == (
        "an enumeration that is not a JSON array"
    )
    assert items.parse_item_summaries(stdout=b"[1]").failure() == (
        "an enumerated entry that is not an object"
    )
    assert items.parse_item_summaries(stdout=b'[{"id":"a","title":""}]').failure() == (
        "an enumerated entry whose id and title are not both non-empty strings"
    )


def test_one_item_s_application_fields_are_closed_to_unique_labelled_text():
    """A duplicate label is refused rather than collapsed: JSON arrays permit repetition."""
    items = _module(name="_lpm_op_items")
    labelled = b'{"fields":[{"label":"record","value":"{}"}]}'

    assert items.parse_item_fields(stdout=labelled).unwrap() == {"record": "{}"}
    assert items.parse_item_fields(stdout=b"[]").failure() == "an item that is not an object"
    assert items.parse_item_fields(stdout=b'{"fields":{}}').failure() == (
        "an item whose application fields are not an array"
    )
    assert items.parse_item_fields(stdout=b'{"fields":[1]}').failure() == (
        "an application field that is not an object"
    )
    assert items.parse_item_fields(stdout=b'{"fields":[{"label":"a","value":1}]}').failure() == (
        "an application field whose label and value are not both text"
    )
    doubled = b'{"fields":[{"label":"a","value":"1"},{"label":"a","value":"2"}]}'
    assert items.parse_item_fields(stdout=doubled).failure() == (
        "an item carrying one application-field label twice"
    )


def test_a_revision_title_is_recognized_only_in_the_operation_s_closed_grammar():
    """A lowercase UUIDv4 record, a 20-digit revision from one, and a lowercase digest.

    The enumerator has no record id to anchor on, so it decides GRAMMAR membership for the
    whole vault; `resolve_chain` then decides CHAIN membership against the record it was
    actually asked about. Both answers have to hold, which is why each is complete on its
    own terms rather than one deferring to the other.
    """
    revisions = importlib.import_module("_lpm_revisions")
    assert "revision_title_parts" in revisions.__all__, "the title grammar must be public"

    parts = revisions.revision_title_parts(title=_title(revision=12))

    assert parts == revisions.RevisionTitle(record_id=_RECORD, revision=12, effect_id=_EFFECT)
    # Revision zero, a short revision, an uppercase record id and a non-digest effect id.
    assert revisions.revision_title_parts(title=f"{_RECORD}-m{'0' * 20}-{_EFFECT}") is None
    assert revisions.revision_title_parts(title=f"{_RECORD}-m1-{_EFFECT}") is None
    assert revisions.revision_title_parts(title=_title().upper()) is None
    assert revisions.revision_title_parts(title=f"{_RECORD}-m{'0' * 19}1-nope") is None
