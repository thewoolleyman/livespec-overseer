"""Unsafe local state fails closed — and is never reset or rewritten.

SPECIFICATION/contracts.md requires that every filesystem-backed local store be mode
`0600` beneath a mode-`0700` manager state directory, that a malformed, non-regular,
symlinked, incorrectly owned or more broadly accessible record return `store-unavailable`
with exit `4`, and that the unsafe path be NEITHER RESET NOR MUTATED.

The last clause is what these tests are really about. The tempting repair for an
unreadable state file is to replace it with fresh initial state — and that is exactly the
forbidden move, because a corrupt lease, assignment or fence file is evidence of state
this manager may still be bound by. Every failing case below therefore asserts the bytes
on disk afterwards, not just the returned refusal.

The owner uid is passed in rather than read from the process, so the incorrectly-owned
case is exercised deterministically instead of requiring a test to run as root.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_localstate.py"
    assert module_path.is_file(), "overseer/_lpm_localstate.py must exist"
    return (importlib.import_module("_lpm_localstate"),)


def _uid() -> int:
    return os.geteuid()


def test_an_absent_record_is_an_answer_rather_than_a_defect(tmp_path):
    (localstate,) = _modules()

    assert localstate.read_local_record(
        path=tmp_path / "lease.json", owner_uid=_uid()
    ).unwrap() is (None)
    assert localstate.read_local_text(path=tmp_path / "audit.jsonl", owner_uid=_uid()).unwrap() is (
        None
    )


def test_a_written_record_is_owner_only_and_reads_back_through_the_canonical_encoder(tmp_path):
    (localstate,) = _modules()
    path = tmp_path / "state" / "selection-state.json"

    written = localstate.write_local_record(
        path=path, value={"version": 1, "b": [1, 2]}, owner_uid=_uid()
    )

    assert written.unwrap() is None
    assert path.read_bytes() == b'{"b":[1,2],"version":1}'
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert localstate.read_local_record(path=path, owner_uid=_uid()).unwrap() == {
        "version": 1,
        "b": [1, 2],
    }


def test_a_symlinked_record_is_refused_before_it_is_followed(tmp_path):
    (localstate,) = _modules()
    real = tmp_path / "elsewhere.json"
    real.write_text('{"version":1}', encoding="utf-8")
    link = tmp_path / "lease.json"
    link.symlink_to(real)

    refusal = localstate.read_local_record(path=link, owner_uid=_uid())

    assert refusal.failure().error_type == "store-unavailable"
    assert refusal.failure().message == "lease.json is a symlink"
    assert link.is_symlink(), "the unsafe path is left exactly as found"


def test_a_non_regular_wrongly_owned_or_broadly_accessible_record_fails_closed(tmp_path):
    (localstate,) = _modules()
    directory = tmp_path / "lease.json"
    directory.mkdir()
    broad = tmp_path / "broad.json"
    broad.write_text('{"version":1}', encoding="utf-8")
    broad.chmod(0o644)

    not_regular = localstate.read_local_record(path=directory, owner_uid=_uid())
    wrong_owner = localstate.read_local_record(path=broad, owner_uid=_uid() + 1)
    broader = localstate.read_local_record(path=broad, owner_uid=_uid())

    assert not_regular.failure().message == "lease.json is not a regular file"
    assert wrong_owner.failure().message == "broad.json is not owned by the manager"
    assert broader.failure().message == "broad.json is more broadly accessible"
    assert broad.stat().st_mode & 0o777 == 0o644, "the unsafe path is neither reset nor chmodded"


def test_malformed_and_non_utf8_records_fail_closed_without_being_rewritten(tmp_path):
    (localstate,) = _modules()
    malformed = tmp_path / "assignment.json"
    malformed.write_text("{", encoding="utf-8")
    malformed.chmod(0o600)
    duplicated = tmp_path / "tombstone.json"
    duplicated.write_text('{"status":"a","status":"b"}', encoding="utf-8")
    duplicated.chmod(0o600)
    binary = tmp_path / "issuance.json"
    binary.write_bytes(b"\xff\xfe")
    binary.chmod(0o600)

    assert localstate.read_local_record(path=malformed, owner_uid=_uid()).failure().message == (
        "assignment.json is malformed JSON"
    )
    assert localstate.read_local_record(path=duplicated, owner_uid=_uid()).failure().message == (
        "tombstone.json is duplicate member name: status"
    )
    assert localstate.read_local_record(path=binary, owner_uid=_uid()).failure().message == (
        "issuance.json is not valid UTF-8"
    )
    assert malformed.read_text(encoding="utf-8") == "{", "no reset, no mutation"


def test_an_unreadable_path_is_store_unavailable_rather_than_absent(tmp_path, monkeypatch):
    (localstate,) = _modules()
    blocked = tmp_path / "afile"
    blocked.write_text("", encoding="utf-8")
    readable = tmp_path / "lease.json"
    readable.write_text("{}", encoding="utf-8")
    readable.chmod(0o600)

    def _refuse(self) -> bytes:  # stands in for Path.read_bytes
        raise OSError(5, "simulated")

    nested = localstate.read_local_record(path=blocked / "nested.json", owner_uid=_uid())
    monkeypatch.setattr(localstate.Path, "read_bytes", _refuse)
    unreadable = localstate.read_local_record(path=readable, owner_uid=_uid())

    # "Absent" is a defined ANSWER in this operation; an unreadable path must never be
    # collapsed into it, or a live lease would read as no lease at all.
    assert nested.failure().message.startswith("nested.json is unreadable: ")
    assert unreadable.failure().message.startswith("lease.json is unreadable: ")


def test_a_record_under_an_unsafe_directory_is_refused_before_it_is_staged(tmp_path):
    (localstate,) = _modules()
    broad = tmp_path / "state"
    broad.mkdir(mode=0o755)

    refusal = localstate.write_local_record(
        path=broad / "lease.json", value={"version": 1}, owner_uid=_uid()
    )

    assert refusal.failure().message == "state is more broadly accessible"
    assert list(broad.iterdir()) == []


def test_writing_over_a_more_broadly_accessible_destination_is_refused(tmp_path):
    (localstate,) = _modules()
    path = tmp_path / "lease.json"
    path.write_text("prior", encoding="utf-8")
    path.chmod(0o666)

    refusal = localstate.write_local_record(path=path, value={"version": 1}, owner_uid=_uid())

    assert refusal.failure().message == "lease.json is more broadly accessible"
    assert path.read_text(encoding="utf-8") == "prior"


def test_an_unencodable_record_is_a_bug_rather_than_an_unavailable_store(tmp_path):
    (localstate,) = _modules()

    refusal = localstate.write_local_record(
        path=tmp_path / "lease.json", value={"ratio": 1.5}, owner_uid=_uid()
    )

    assert refusal.failure().error_type == "internal-bug"


def test_a_failed_rename_reports_store_unavailable_and_removes_its_staged_file(
    tmp_path, monkeypatch
):
    (localstate,) = _modules()
    path = tmp_path / "lease.json"

    def _refuse(self, target):  # stands in for Path.replace
        raise OSError(5, "simulated")

    monkeypatch.setattr(localstate.Path, "replace", _refuse)
    refusal = localstate.write_local_record(path=path, value={"version": 1}, owner_uid=_uid())

    assert refusal.failure().message.startswith("lease.json was not replaced: ")
    assert not path.exists()
    assert list(tmp_path.iterdir()) == [], "the staged replacement is cleaned up"


def test_an_unsafe_state_directory_is_refused_rather_than_repaired(tmp_path):
    (localstate,) = _modules()
    broad = tmp_path / "state"
    broad.mkdir(mode=0o755)
    linked = tmp_path / "linked"
    linked.symlink_to(broad)

    assert localstate.ensure_state_directory(path=broad, owner_uid=_uid()).failure().message == (
        "state is more broadly accessible"
    )
    assert localstate.ensure_state_directory(
        path=broad, owner_uid=_uid() + 1
    ).failure().message == ("state is not owned by the manager")
    assert localstate.ensure_state_directory(path=linked, owner_uid=_uid()).failure().message == (
        "linked is a symlink"
    )
    blocked = tmp_path / "afile"
    blocked.write_text("", encoding="utf-8")
    assert (
        localstate.ensure_state_directory(path=blocked / "leases", owner_uid=_uid())
        .failure()
        .message.startswith("leases is unusable: ")
    )
    assert broad.stat().st_mode & 0o777 == 0o755, "the unsafe directory is left as found"
