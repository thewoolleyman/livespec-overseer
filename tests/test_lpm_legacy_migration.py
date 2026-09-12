"""Legacy-pool migration: injected enumeration, real validation, and a printable report.

SPECIFICATION/spec.md defines the legacy credential pool as the manually maintained
`CLAUDE_CODE_OAUTH_TOKEN*` entries in the factory consumer's credential environment, and
makes a production consumer's attestation that this pool was ABSENT one of the four proofs
gating `caam-anthropic-loop`'s deprecation. contracts.md fixes the Anthropic validation
outcomes this migration classifies by, and fixes the credential record every accepted
candidate is written as.

THE WHOLE INPUT IS SECRETS, SO THE REPORT IS ASSERTED TO BE PRINTABLE. The test below does
not merely check that the right slots were written — it renders the entire report and
asserts no token value appears anywhere in it. A report that is safe only when read
carefully is not safe.

THE RUN IS HERMETIC BY CONSTRUCTION, AND THAT IS ALSO ASSERTED. Enumeration, the validation
probe and the store are all injected, so this exercise reads no 1Password value, mutates no
host store and mints nothing. The acquisition handoff is DESCRIBED and refused without
authorization; nothing here can spawn the terminal that would actually mint a credential.
Its refusal ORDER is asserted too — an unauthorized caller receives no description at all,
because a description returned beside a refusal is one a caller can act on anyway.

NOTHING IS DELETED. The source is asked for names and values and is never told to remove
one: retiring the legacy pool is a separate, separately-authorized act, and a migration that
deleted as it wrote would destroy the only surviving copy the moment a later step failed.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_NOW = "2026-09-12T10:00:00Z"
_ONE = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_TWO = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_THREE = "9c858901-8a57-4791-81fe-4c455b099bc9"

_TOKENS = {
    "CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat0-good",
    "CLAUDE_CODE_OAUTH_TOKEN_2": "sk-ant-oat0-dead",
    "CLAUDE_CODE_OAUTH_TOKEN_3": "sk-ant-oat0-flaky",
}
_ACCOUNTS = {
    "CLAUDE_CODE_OAUTH_TOKEN": "one@example.test",
    "CLAUDE_CODE_OAUTH_TOKEN_2": "two@example.test",
    "CLAUDE_CODE_OAUTH_TOKEN_3": "three@example.test",
}
_OUTCOMES = {
    "sk-ant-oat0-good": (True, 200),
    "sk-ant-oat0-dead": (True, 401),
    "sk-ant-oat0-flaky": (True, 529),
}


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_migration.py"
    assert module_path.is_file(), "overseer/_lpm_migration.py must exist"
    handoff_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_handoff.py"
    assert handoff_path.is_file(), "overseer/_lpm_acquisition_handoff.py must exist"
    return (
        importlib.import_module("_lpm_migration"),
        importlib.import_module("_lpm_anthropic"),
        importlib.import_module("_lpm_store"),
        importlib.import_module("_lpm_acquisition_handoff"),
    )


class _Source:
    """The injected legacy pool. It exposes no removal, because nothing may remove one."""

    def __init__(self, *, names: tuple[str, ...], values=None, accounts=None) -> None:
        self.names = names
        self.values = _TOKENS if values is None else values
        self.accounts = _ACCOUNTS if accounts is None else accounts

    def slot_names(self) -> tuple[str, ...]:
        return self.names

    def account_for(self, *, name: str):
        return self.accounts.get(name)

    def value_for(self, *, name: str):
        return self.values.get(name)


def _probe(anthropic):
    def probe(*, request):
        credential = dict(request.headers)["Authorization"].removeprefix("Bearer ")
        reached, status = _OUTCOMES.get(credential, (False, 0))
        body = {
            "id": "msg_01",
            "type": "message",
            "role": "assistant",
            "usage": {"input_tokens": 8, "output_tokens": 1},
        }
        return anthropic.ProbeResponse(reached=reached, status=status, body=body)

    return probe


def _plan(migration, **changes):
    fields = {
        "purpose": "factory",
        "expected_accounts": ("one@example.test", "two@example.test", "three@example.test"),
        "identities": {
            "one@example.test": migration.RecordIdentity(
                record_id=_ONE, value_generation="11111111-1111-4111-8111-111111111111"
            ),
            "two@example.test": migration.RecordIdentity(
                record_id=_TWO, value_generation="22222222-2222-4222-8222-222222222222"
            ),
            "three@example.test": migration.RecordIdentity(
                record_id=_THREE, value_generation="33333333-3333-4333-8333-333333333333"
            ),
        },
        "now": _NOW,
    }
    fields.update(changes)
    return migration.MigrationPlan(**fields)


def test_enumeration_takes_the_whole_token_family_and_nothing_else():
    migration, *_ = _modules()

    names = migration.legacy_slot_names(
        names=(
            "PATH",
            "CLAUDE_CODE_OAUTH_TOKEN_2",
            "ANTHROPIC_API_KEY_LIVESPEC_E2E",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN_SPARE",
        )
    )

    assert names == (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN_2",
        "CLAUDE_CODE_OAUTH_TOKEN_SPARE",
    )
    assert migration.LEGACY_VARIABLE_PREFIX == "CLAUDE_CODE_OAUTH_TOKEN"


def test_a_migration_writes_only_the_credentials_the_provider_actually_accepts():
    migration, anthropic, store_module, _handoffs = _modules()
    store = store_module.InMemorySecretStore()

    report = migration.migrate_legacy_tokens(
        source=_Source(names=tuple(_TOKENS)),
        probe=_probe(anthropic),
        store=store,
        plan=_plan(migration),
    ).unwrap()

    assert report.written == ("CLAUDE_CODE_OAUTH_TOKEN",)
    dispositions = {outcome.name: outcome.disposition for outcome in report.outcomes}
    assert dispositions == {
        "CLAUDE_CODE_OAUTH_TOKEN": migration.WRITTEN_SLOT,
        # A definitive 401 is evidence about the credential …
        "CLAUDE_CODE_OAUTH_TOKEN_2": migration.REJECTED_SLOT,
        # … while a 529 is evidence about nothing, and must never become rejection.
        "CLAUDE_CODE_OAUTH_TOKEN_3": migration.INCONCLUSIVE_SLOT,
    }
    stored = store.metadata_get(record_id=_ONE)
    assert stored["status"] == "ok"
    assert stored["item"] is not None


def test_the_written_record_is_the_ratified_schema_and_carries_a_reference_not_a_value():
    migration, anthropic, store_module, _handoffs = _modules()
    store = store_module.InMemorySecretStore()
    canonical = importlib.import_module("_lpm_canonical")
    records = importlib.import_module("_lpm_record")

    _ = migration.migrate_legacy_tokens(
        source=_Source(names=("CLAUDE_CODE_OAUTH_TOKEN",)),
        probe=_probe(anthropic),
        store=store,
        plan=_plan(migration),
    ).unwrap()

    envelope = store.metadata_get(record_id=_ONE)["item"]
    assert isinstance(envelope, dict)
    parsed = canonical.parse_canonical_json(text=str(envelope["record"])).unwrap()
    record = records.credential_record_from_object(parsed=parsed).unwrap()

    assert record.provider == migration.LEGACY_PROVIDER
    assert record.kind == migration.LEGACY_KIND
    assert (record.account_id, record.purpose, record.status) == (
        "one@example.test",
        "factory",
        "valid",
    )
    assert record.last_validated == _NOW
    assert record.value_ref is not None and record.value_ref.startswith("op://")
    assert "sk-ant-oat0" not in str(envelope["record"])


def test_the_report_names_the_missing_accounts_and_prints_no_token_value():
    migration, anthropic, store_module, _handoffs = _modules()

    report = migration.migrate_legacy_tokens(
        source=_Source(names=tuple(_TOKENS)),
        probe=_probe(anthropic),
        store=store_module.InMemorySecretStore(),
        plan=_plan(migration),
    ).unwrap()

    assert report.missing_accounts == ("two@example.test", "three@example.test")
    rendered = repr(report)
    for token in _TOKENS.values():
        assert token not in rendered, token
    assert "sk-ant-oat0" not in rendered


def test_a_slot_nobody_can_attribute_is_reported_rather_than_guessed_at():
    migration, anthropic, store_module, _handoffs = _modules()
    source = _Source(
        names=("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN_2"),
        values={"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat0-good", "CLAUDE_CODE_OAUTH_TOKEN_2": ""},
        accounts={"CLAUDE_CODE_OAUTH_TOKEN": "", "CLAUDE_CODE_OAUTH_TOKEN_2": "two@example.test"},
    )

    report = migration.migrate_legacy_tokens(
        source=source,
        probe=_probe(anthropic),
        store=store_module.InMemorySecretStore(),
        plan=_plan(migration),
    ).unwrap()

    assert report.written == ()
    assert all(outcome.disposition == migration.UNATTRIBUTED_SLOT for outcome in report.outcomes)
    assert all(outcome.account_id is None for outcome in report.outcomes)


def test_an_unknown_account_and_an_empty_purpose_refuse_the_run_deterministically():
    migration, anthropic, store_module, _handoffs = _modules()

    unplanned = migration.migrate_legacy_tokens(
        source=_Source(names=("CLAUDE_CODE_OAUTH_TOKEN",)),
        probe=_probe(anthropic),
        store=store_module.InMemorySecretStore(),
        plan=_plan(migration, identities={}),
    ).failure()
    assert unplanned.error_type == "invalid-request"
    assert "one@example.test" in unplanned.message

    empty = migration.migrate_legacy_tokens(
        source=_Source(names=("CLAUDE_CODE_OAUTH_TOKEN",)),
        probe=_probe(anthropic),
        store=store_module.InMemorySecretStore(),
        plan=_plan(migration, purpose=""),
    ).failure()
    assert empty.error_type == "invalid-request"


def test_a_store_that_refuses_or_disappears_is_distinguished_from_a_bad_credential():
    migration, anthropic, store_module, _handoffs = _modules()
    revisions = importlib.import_module("_lpm_revisions")

    unavailable = migration.migrate_legacy_tokens(
        source=_Source(names=("CLAUDE_CODE_OAUTH_TOKEN",)),
        probe=_probe(anthropic),
        store=store_module.InMemorySecretStore(available=False),
        plan=_plan(migration),
    ).failure()
    assert unavailable.error_type == "store-unavailable"

    # A chain already holding a different revision fails the genesis condition: the
    # credential is fine, the record simply was not written by this run.
    occupied = store_module.InMemorySecretStore(
        items={
            _ONE: [
                revisions.RevisionItem(
                    title=revisions.revision_title(
                        record_id=_ONE, revision=revisions.FIRST_REVISION, effect_id="a" * 64
                    ),
                    predecessor_sha256=revisions.predecessor_digest(record=None),
                    record='{"already":"here"}',
                )
            ]
        }
    )
    report = migration.migrate_legacy_tokens(
        source=_Source(names=("CLAUDE_CODE_OAUTH_TOKEN",)),
        probe=_probe(anthropic),
        store=occupied,
        plan=_plan(migration),
    ).unwrap()
    assert report.outcomes[0].disposition == migration.UNWRITTEN_SLOT
    assert report.written == ()


def test_the_acquisition_handoff_describes_the_mint_and_refuses_without_authorization():
    migration, _anthropic, _store, handoffs = _modules()
    # The migration tooling's own surface still offers the handoff, re-exported from the
    # module that owns minting as a separate concern with its own authorization.
    assert migration.acquisition_handoff is handoffs.acquisition_handoff
    assert migration.AcquisitionHandoff is handoffs.AcquisitionHandoff

    fields = {
        "provider": migration.LEGACY_PROVIDER,
        "kind": migration.LEGACY_KIND,
        "account_id": "two@example.test",
        "purpose": "factory",
    }
    refused = migration.acquisition_handoff(**fields, authorized=False).failure()
    assert refused.error_type == "invalid-request"
    assert "separate operator authorization" in refused.message

    for bad in ({"account_id": ""}, {"purpose": ""}, {"kind": "unregistered-kind"}):
        broken = dict(fields)
        broken.update(bad)
        assert (
            migration.acquisition_handoff(**broken, authorized=True).failure().error_type
            == "invalid-request"
        )

    handoff = migration.acquisition_handoff(**fields, authorized=True).unwrap()
    assert handoff.terminal == "claude setup-token"
    assert (handoff.provider, handoff.kind) == ("anthropic", "claude-code-oauth")
    assert handoff.account_id == "two@example.test"


def test_the_migration_holds_no_transport_no_environment_read_and_no_deletion():
    migration, _anthropic, _store, handoffs = _modules()
    ast = importlib.import_module("ast")
    sources = "".join(
        pathlib.Path(module.__file__).read_text(encoding="utf-8")
        for module in (migration, handoffs)
    )
    tree = ast.parse(sources)

    # Parsed rather than grepped: this module's own docstring NAMES the things it refuses
    # to do, so a substring scan would fail on the prose explaining the discipline while
    # proving nothing about the code.
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called.add(ast.unparse(node.func).rsplit(".", maxsplit=1)[-1])

    assert imported.isdisjoint({"os", "socket", "ssl", "urllib", "http", "subprocess", "requests"})
    assert called.isdisjoint({"unlink", "remove", "rmtree", "metadata_delete", "getenv", "run"})


def test_an_unencodable_record_is_an_internal_bug_rather_than_a_quietly_skipped_slot(
    monkeypatch,
):
    migration, anthropic, store_module, _handoffs = _modules()

    # A record the canonical encoder refuses is a manager bug, never a slot quietly
    # skipped: the credential validated, so failing to record it must be loud.
    monkeypatch.setattr(migration, "record_object", lambda *, record: {7: "not-a-string-key"})
    unencodable = migration.migrate_legacy_tokens(
        source=_Source(names=("CLAUDE_CODE_OAUTH_TOKEN",)),
        probe=_probe(anthropic),
        store=store_module.InMemorySecretStore(),
        plan=_plan(migration),
    ).failure()
    assert unencodable.error_type == "internal-bug"


def test_the_disposition_vocabulary_is_closed_and_every_word_is_distinct():
    migration, *_ = _modules()

    assert migration.SLOT_DISPOSITIONS == (
        migration.WRITTEN_SLOT,
        migration.REJECTED_SLOT,
        migration.INCONCLUSIVE_SLOT,
        migration.UNATTRIBUTED_SLOT,
        migration.UNWRITTEN_SLOT,
    )
    assert len(set(migration.SLOT_DISPOSITIONS)) == len(migration.SLOT_DISPOSITIONS)
