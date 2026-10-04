"""Create as the only mutation verb, and the field boundary a lifecycle role writes inside.

SPECIFICATION/contracts.md states this backend's whole mutation story as one rule seen from
several sides, and every side of it is asserted here against a real `op` child.

CREATE ONLY. "Its metadata conditional-set adapter MUST implement the append-only
logical-revision protocol below using `op item create`, and MUST NOT use `op item edit`,
delete a metadata revision or rely on 1Password item-title uniqueness." The three are one
rule: the conditional comparison is carried by the append-only chain, so any of them would
reintroduce last-writer-wins on a record whose entire safety story is that "a stale
writer's create cannot be the next revision". The recorded argv list below is what pins it
— an adapter that edited would return `committed` just as happily.

THE FOUR WORDS MEAN DIFFERENT THINGS. "`uncommitted` definitively says an attempted
unconditional mutation made no change; `condition-failed` definitively says a conditional
mutation made no change because its predecessor comparison failed. `unavailable` ... instead
makes a mutation outcome unknown and requires the authoritative reconciliation defined
below." So a defeated writer is `condition-failed`, a refused create is `unavailable`, and a
write the adapter itself declined to attempt is `uncommitted`. Collapsing any pair of those
is how a write whose fate nobody knows gets reported as a write that did not happen.

A BYTE-IDENTICAL RETRY IS ALREADY COMMITTED. "A conditional-set whose current logical
record equals the desired record in the exact next revision carrying that effect_id is
already committed." The retry must therefore make NO second create — a late duplicate is
harmless, but a retry that appends one has stopped being a retry.

THE FIELD BOUNDARY IS BEHAVIOURAL, NOT A VAULT PERMISSION. "A lifecycle-role request that
changes any field other than `status` or `last_validated` MUST be refused, enforcing the
externally observable field boundary independently of 1Password vault permissions." The
three lifecycle roles share one metadata-writer token that CAN write anything in that
vault, so the only place this rule can live is in the adapter's own behaviour. A genesis
create is refused for the same reason read from the other end: a record that does not exist
yet has no `status` to transition, and creating one is the acquisition writer's act.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_METADATA_VAULT = "llm-provider-manager-token-metadata"
_VALUES_VAULT = "llm-provider-manager-token-values"

_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_EFFECT = "a" * 64
_NEXT_EFFECT = "b" * 64
_GENESIS = "0" * 64

_MACHINE_ID = "d" * 64
_STATE = "/home/operator/.local/state/livespec-overseer/llm-provider-manager"
_UNAVAILABLE = {"version": 1, "status": "unavailable"}
_UNCOMMITTED = {"version": 1, "status": "uncommitted"}


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


def _namespace_item():
    onepassword = importlib.import_module("_lpm_onepassword")
    return {
        "id": "namespace-1",
        "title": onepassword.NAMESPACE_ITEM_TITLE,
        "vault": _METADATA_VAULT,
        "fields": _namespace_fields(),
    }


def _title(*, revision=1, effect_id=_EFFECT):
    revisions = importlib.import_module("_lpm_revisions")
    return revisions.revision_title(record_id=_RECORD, revision=revision, effect_id=effect_id)


def _revision(*, revision=1, effect_id=_EFFECT, predecessor=_GENESIS, record='{"v":1}'):
    item_title = _title(revision=revision, effect_id=effect_id)
    return {
        "id": f"item-{item_title}",
        "title": item_title,
        "vault": _METADATA_VAULT,
        "fields": {"predecessor_sha256": predecessor, "record": record},
    }


def _record(*, status="valid", purpose="factory", last_validated="2026-09-02T00:00:00Z"):
    """One complete canonical credential record, so a field-boundary test has two to compare."""
    canonical = importlib.import_module("_lpm_canonical")
    return canonical.canonical_json_text(
        value={
            "version": 1,
            "record_id": _RECORD,
            "provider": "anthropic",
            "account_id": "account-1",
            "kind": "claude-code-oauth",
            "purpose": purpose,
            "status": status,
            "acquired_at": "2026-09-01T00:00:00Z",
            "expires_at": None,
            "last_validated": last_validated,
            "value_generation": _GENERATION,
            "value_ref": f"op://{_VALUES_VAULT}/{_RECORD}-{_GENERATION}/credential",
            "previous_value_ref": None,
        }
    ).unwrap()


def _store(*, op_fixture, role_name="acquisition-writer"):
    """The real `OnePasswordSecretStore`, bound to the fixture under one registry role."""
    store = _module(name="_lpm_op_store")
    vault = _module(name="_lpm_op_vault")
    op = importlib.import_module("_lpm_op")
    role = importlib.import_module("_lpm_roles").credential_role(name=role_name)
    return store.OnePasswordSecretStore(
        access=vault.VaultAccess(
            runner=op.HostOpChild(
                environ={"PATH": "/usr/bin:/bin", role.variable: f"fixture-token-{role.name}"},
                variable=role.variable,
                timeout_seconds=30.0,
            ),
            op_executable=op_fixture.executable,
            retained_executable=op_fixture.executable,
            role=role,
        ),
        namespace=_namespace_fields(),
    )


def _set(*, store, expected=None, desired='{"v":1}', effect=_EFFECT):
    module = _module(name="_lpm_store")
    return store.credential_conditional_set(
        request=module.ConditionalSet(
            record_id=_RECORD, effect_id=effect, expected_record=expected, desired_record=desired
        )
    )


def _verbs(*, op_fixture):
    return [tuple(argv[:2]) for argv in op_fixture.argvs()]


def _created(*, op_fixture):
    """Only the items the fixture itself appended, which are the ones a create made."""
    appended = op_fixture.items(vault=_METADATA_VAULT)
    return [item for item in appended if item["id"].startswith("fixture-")]


def test_a_genesis_create_appends_revision_one_through_create_and_never_an_edit(op_fixture):
    """The one mutation verb, with the two declared text fields streamed over stdin."""
    op_fixture.seed(items=[_namespace_item()])

    answer = _set(store=_store(op_fixture=op_fixture))

    assert answer == {"version": 1, "status": "committed"}
    appended = _created(op_fixture=op_fixture)
    assert [item["title"] for item in appended] == [_title()]
    assert appended[0]["fields"] == {"predecessor_sha256": _GENESIS, "record": '{"v":1}'}
    assert set(_verbs(op_fixture=op_fixture)) <= {
        ("item", "list"),
        ("item", "get"),
        ("item", "create"),
    }
    assert all("edit" not in argv for argv in op_fixture.argvs()), "create is the only verb"
    create = next(argv for argv in op_fixture.argvs() if argv[1] == "create")
    assert create == ["item", "create", "--vault", _METADATA_VAULT, "-"]


def test_a_byte_identical_fenced_retry_is_committed_without_a_second_create(op_fixture):
    """Already-committed is read off the chain, so a retry appends nothing at all."""
    op_fixture.seed(items=[_namespace_item(), _revision()])

    answer = _set(store=_store(op_fixture=op_fixture))

    assert answer == {"version": 1, "status": "committed"}
    assert _created(op_fixture=op_fixture) == [], "a retry that appends has stopped being one"


def test_a_defeated_writer_is_condition_failed_and_an_advanced_one_commits(op_fixture):
    """The predecessor comparison is carried by the chain, never by title uniqueness."""
    revisions = importlib.import_module("_lpm_revisions")
    op_fixture.seed(items=[_namespace_item(), _revision()])
    stale = _set(store=_store(op_fixture=op_fixture), desired='{"v":9}', effect=_NEXT_EFFECT)

    op_fixture.seed(items=[_namespace_item(), _revision()])
    advanced = _set(
        store=_store(op_fixture=op_fixture),
        expected='{"v":1}',
        desired='{"v":2}',
        effect=_NEXT_EFFECT,
    )
    appended = _created(op_fixture=op_fixture)

    assert stale == {"version": 1, "status": "condition-failed"}
    assert advanced == {"version": 1, "status": "committed"}
    assert [item["title"] for item in appended] == [_title(revision=2, effect_id=_NEXT_EFFECT)]
    assert appended[0]["fields"]["predecessor_sha256"] == revisions.predecessor_digest(
        record='{"v":1}'
    )


def test_an_invalid_chain_refuses_its_own_mutation_as_unavailable(op_fixture):
    """A record whose chain cannot be read refuses every mutation and appends nothing."""
    revisions = importlib.import_module("_lpm_revisions")
    op_fixture.seed(
        items=[
            _namespace_item(),
            _revision(revision=2, predecessor=revisions.predecessor_digest(record='{"v":1}')),
        ]
    )

    answer = _set(store=_store(op_fixture=op_fixture), expected='{"v":1}', desired='{"v":2}')

    assert answer == _UNAVAILABLE
    assert ("item", "create") not in _verbs(op_fixture=op_fixture)


def test_a_refused_create_leaves_the_outcome_unknown_rather_than_unchanged(op_fixture):
    """`unavailable`, never `uncommitted`: the create may have landed and said nothing."""
    op_fixture.seed(items=[_namespace_item()], refuse=("item create",))

    answer = _set(store=_store(op_fixture=op_fixture))

    assert answer == _UNAVAILABLE
    assert ("item", "create") in _verbs(op_fixture=op_fixture), "the create was attempted"


def test_a_namespace_defect_refuses_the_write_before_any_create(op_fixture):
    """The binding is proved before a mutation, not merely reported after one."""
    op_fixture.seed(items=[])

    answer = _set(store=_store(op_fixture=op_fixture))

    assert answer == _UNAVAILABLE
    assert _verbs(op_fixture=op_fixture) == [("item", "list")]


def test_a_lifecycle_role_may_change_only_status_and_last_validated(op_fixture):
    """Two permitted transitions commit; one touch of any other field is refused."""
    op_fixture.seed(items=[_namespace_item(), _revision(record=_record())])
    transitioned = _set(
        store=_store(op_fixture=op_fixture, role_name="lifecycle-writer"),
        expected=_record(),
        desired=_record(status="suspect"),
        effect=_NEXT_EFFECT,
    )

    op_fixture.seed(items=[_namespace_item(), _revision(record=_record())])
    revalidated = _set(
        store=_store(op_fixture=op_fixture, role_name="report-writer"),
        expected=_record(),
        desired=_record(last_validated="2026-09-03T00:00:00Z"),
        effect=_NEXT_EFFECT,
    )

    op_fixture.seed(items=[_namespace_item(), _revision(record=_record())])
    repurposed = _set(
        store=_store(op_fixture=op_fixture, role_name="recovery-writer"),
        expected=_record(),
        desired=_record(purpose="something-else"),
        effect=_NEXT_EFFECT,
    )
    refused_verbs = _verbs(op_fixture=op_fixture)

    assert transitioned == {"version": 1, "status": "committed"}
    assert revalidated == {"version": 1, "status": "committed"}
    assert repurposed == _UNCOMMITTED
    assert ("item", "create") not in refused_verbs, "the boundary refuses before the create"


def test_a_lifecycle_role_may_not_create_a_record_out_of_absence(op_fixture):
    """A record that does not exist has no `status` to transition; genesis is not theirs."""
    op_fixture.seed(items=[_namespace_item()])

    answer = _set(
        store=_store(op_fixture=op_fixture, role_name="lifecycle-writer"), desired=_record()
    )

    assert answer == _UNCOMMITTED
    assert ("item", "create") not in _verbs(op_fixture=op_fixture)


def test_a_lifecycle_write_that_is_not_two_complete_records_is_refused(op_fixture):
    """The boundary compares FIELDS, so it cannot be applied to something that has none."""
    op_fixture.seed(items=[_namespace_item(), _revision(record=_record())])
    unparseable = _set(
        store=_store(op_fixture=op_fixture, role_name="lifecycle-writer"),
        expected=_record(),
        desired="{not json",
        effect=_NEXT_EFFECT,
    )

    op_fixture.seed(items=[_namespace_item(), _revision(record=_record())])
    not_a_record = _set(
        store=_store(op_fixture=op_fixture, role_name="lifecycle-writer"),
        expected=_record(),
        desired='{"v":1}',
        effect=_NEXT_EFFECT,
    )

    assert unparseable == _UNCOMMITTED
    assert not_a_record == _UNCOMMITTED


def test_a_desired_record_no_encoder_can_reproduce_is_a_definitive_no_change(op_fixture):
    """A lone surrogate has no UTF-8 encoding, so the template was never streamable.

    `uncommitted` rather than `unavailable`, because nothing was attempted: the outcome is
    definitively no change, and reporting it unknown would send a reconciler after a create
    that never reached a child.
    """
    op_fixture.seed(items=[_namespace_item()])

    answer = _set(store=_store(op_fixture=op_fixture), desired="\ud800")

    assert answer == _UNCOMMITTED
    assert ("item", "create") not in _verbs(op_fixture=op_fixture)


def test_the_create_template_streams_exactly_the_declared_labelled_text_fields():
    """No assignment argument, template file or environment field — one stdin object."""
    items = _module(name="_lpm_op_items")

    template = items.item_create_template(
        title="t", fields={"record": '{"v":1}', "predecessor_sha256": _GENESIS}
    )

    assert template["title"] == "t"
    assert [field["label"] for field in template["fields"]] == [
        "predecessor_sha256",
        "record",
    ], "a byte-identical retry needs a deterministic field order"
    assert {field["type"] for field in template["fields"]} == {"STRING"}
    assert [field["value"] for field in template["fields"]] == [_GENESIS, '{"v":1}']


def test_the_backend_answers_the_whole_secret_store_port_under_one_namespace(op_fixture):
    """Get, list and conditional set are one object's three methods, as the port declares."""
    protocol = importlib.import_module("_lpm_store").SecretStore
    declared = sorted(name for name in vars(protocol) if not name.startswith("_"))
    op_fixture.seed(items=[_namespace_item()])
    store = _store(op_fixture=op_fixture)

    assert declared == ["credential_conditional_set", "metadata_get", "metadata_list"]
    assert all(callable(getattr(store, name)) for name in declared)
    assert store.metadata_get(record_id=_RECORD) == {"version": 1, "status": "ok", "item": None}
    assert _set(store=store) == {"version": 1, "status": "committed"}
    listed = store.metadata_list()
    assert [envelope["item_id"] for envelope in listed["items"]] == [_title()]
    assert [envelope["record"] for envelope in listed["items"]] == [{"v": 1}]
