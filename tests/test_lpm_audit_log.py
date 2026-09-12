"""The audit log only ever grows, and an effect is recorded exactly once.

SPECIFICATION/contracts.md requires every provisionable-token store mutation to FIRST
append a secret-free entry naming the record, actor, attempted operation and time, and
requires the store mutation NOT to be attempted when that append fails.

The append is idempotent by `effect_id` and DELIBERATELY IGNORES the stored
`attempted_at` when matching: a retry after an unknown outcome cannot reproduce the
original attempt instant, so comparing it would append a second line every time and turn
the idempotency scan into a duplicate generator. The log is append-only — a
definitively-uncommitted mutation leaves its entry behind, because the entry attests an
ATTEMPT, while the store remains authoritative for whether that attempt committed.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_FIRST = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_EFFECT = "a" * 64


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_audit.py"
    assert module_path.is_file(), "overseer/_lpm_audit.py must exist"
    return (importlib.import_module("_lpm_audit"),)


def _uid() -> int:
    return os.geteuid()


def _entry(*, audit, effect: str = _EFFECT, **changes: object):
    fields: dict[str, object] = {
        "record_id": _FIRST,
        "effect_id": effect,
        "actor": "lifecycle-writer",
        "operation": "credential-conditional-set",
        "attempted_at": "2026-09-12T10:00:00Z",
    }
    fields.update(changes)
    return audit.AuditEntry(**fields)


def test_an_absent_audit_file_is_an_empty_history_and_an_append_adds_one_line(tmp_path):
    (audit,) = _modules()
    path = tmp_path / "audit.jsonl"

    assert audit.read_audit_log(path=path, owner_uid=_uid()).unwrap() == ()
    appended = audit.append_audit_entry(path=path, entry=_entry(audit=audit), owner_uid=_uid())

    assert appended.unwrap().appended is True
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert audit.read_audit_log(path=path, owner_uid=_uid()).unwrap()[0].actor == (
        "lifecycle-writer"
    )


def test_a_retry_with_a_different_attempt_time_is_a_completed_append_not_a_duplicate(tmp_path):
    (audit,) = _modules()
    path = tmp_path / "audit.jsonl"
    first = audit.append_audit_entry(path=path, entry=_entry(audit=audit), owner_uid=_uid())
    retry = audit.append_audit_entry(
        path=path,
        entry=_entry(audit=audit, attempted_at="2026-09-12T10:05:00Z"),
        owner_uid=_uid(),
    )

    assert first.unwrap().appended is True
    assert retry.unwrap().appended is False, "the stored attempt instant is deliberately ignored"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_a_second_distinct_effect_appends_after_the_first_without_rewriting_it(tmp_path):
    (audit,) = _modules()
    path = tmp_path / "audit.jsonl"
    _ = audit.append_audit_entry(path=path, entry=_entry(audit=audit), owner_uid=_uid())
    before = path.read_text(encoding="utf-8")
    _ = audit.append_audit_entry(
        path=path, entry=_entry(audit=audit, effect="b" * 64), owner_uid=_uid()
    )

    after = path.read_text(encoding="utf-8")

    assert after.startswith(before), "the append is prefix-preserving; nothing is rewritten"
    assert len(after.splitlines()) == 2


def test_a_same_effect_id_recorded_differently_or_twice_fails_closed(tmp_path):
    (audit,) = _modules()
    conflicting = tmp_path / "conflicting.jsonl"
    _ = audit.append_audit_entry(path=conflicting, entry=_entry(audit=audit), owner_uid=_uid())
    changed = audit.append_audit_entry(
        path=conflicting,
        entry=_entry(audit=audit, actor="recovery-writer"),
        owner_uid=_uid(),
    )
    doubled = tmp_path / "doubled.jsonl"
    line = audit.read_audit_log(path=conflicting, owner_uid=_uid())
    _ = line
    stored = conflicting.read_text(encoding="utf-8").splitlines()[0]
    doubled.write_text(f"{stored}\n{stored}\n", encoding="utf-8")
    doubled.chmod(0o600)
    repeated = audit.append_audit_entry(path=doubled, entry=_entry(audit=audit), owner_uid=_uid())

    assert changed.failure().message == "audit log records this effect_id differently"
    assert repeated.failure().message == "audit log records this effect more than once"


def test_a_malformed_log_line_fails_closed_without_being_rewritten(tmp_path):
    (audit,) = _modules()
    path = tmp_path / "audit.jsonl"
    path.write_text('{"version":1,"record_id":"x"}\n', encoding="utf-8")
    path.chmod(0o600)
    broken = tmp_path / "broken.jsonl"
    broken.write_text("{\n", encoding="utf-8")
    broken.chmod(0o600)
    wrong_version = tmp_path / "version.jsonl"
    wrong_version.write_text(
        '{"actor":"a","attempted_at":"2026-09-12T10:00:00Z","effect_id":"e",'
        '"operation":"o","record_id":"r","version":2}\n',
        encoding="utf-8",
    )
    wrong_version.chmod(0o600)
    empty_member = tmp_path / "empty.jsonl"
    empty_member.write_text(
        '{"actor":"","attempted_at":"2026-09-12T10:00:00Z","effect_id":"e",'
        '"operation":"o","record_id":"r","version":1}\n',
        encoding="utf-8",
    )
    empty_member.chmod(0o600)
    not_object = tmp_path / "array.jsonl"
    not_object.write_text("[]\n", encoding="utf-8")
    not_object.chmod(0o600)

    assert audit.read_audit_log(path=path, owner_uid=_uid()).failure().message == (
        "audit log line has the wrong members"
    )
    assert audit.read_audit_log(path=broken, owner_uid=_uid()).failure().message == (
        "audit log line is malformed JSON"
    )
    assert audit.read_audit_log(path=wrong_version, owner_uid=_uid()).failure().message == (
        "audit log line version must be the integer 1"
    )
    assert audit.read_audit_log(path=empty_member, owner_uid=_uid()).failure().message == (
        "audit log actor must be non-empty"
    )
    assert audit.read_audit_log(path=not_object, owner_uid=_uid()).failure().message == (
        "audit log line is not a JSON object"
    )
    assert path.read_text(encoding="utf-8") == '{"version":1,"record_id":"x"}\n'
    # An append must refuse for the same reason a read does, rather than start a fresh log
    # on top of evidence it could not validate.
    assert (
        audit.append_audit_entry(path=broken, entry=_entry(audit=audit), owner_uid=_uid())
        .failure()
        .message
        == "audit log line is malformed JSON"
    )
    linked = tmp_path / "linked.jsonl"
    linked.symlink_to(path)
    assert audit.read_audit_log(path=linked, owner_uid=_uid()).failure().message == (
        "linked.jsonl is a symlink"
    )


def test_an_unrepresentable_or_unwritable_append_is_refused_before_the_store_mutation(tmp_path):
    (audit,) = _modules()
    broad = tmp_path / "state"
    broad.mkdir(mode=0o755)

    bad_time = audit.append_audit_entry(
        path=tmp_path / "audit.jsonl",
        entry=_entry(audit=audit, attempted_at="whenever"),
        owner_uid=_uid(),
    )
    unwritable = audit.append_audit_entry(
        path=broad / "audit.jsonl", entry=_entry(audit=audit), owner_uid=_uid()
    )

    # The contract's ordering: if the append fails, the credential-store mutation MUST NOT
    # be attempted — so the append has to report its own failure rather than degrade.
    assert bad_time.failure().error_type == "internal-bug"
    assert unwritable.failure().error_type == "store-unavailable"
