"""Runtime prerequisites fail closed BEFORE the first dependent action.

SPECIFICATION/contracts.md requires a command that first needs Linux procfs,
`/usr/bin/keyctl`, its user keyring or the configured SecretStore executable and finds it
unavailable to return `store-unavailable` with exit `4` before that dependent action or any
substantive mutation, and adds the safe `/etc/machine-id` source to that base set for the
initial `onepassword` backend.

"Before" is the whole value of the rule. Once a role has been launched, a token has left
the user keyring and an `op` child has been spawned — a prerequisite refusal at that point
has already paid the cost it exists to prevent. So every check here runs against the
filesystem and the inherited path and touches nothing else.

MACHINE-ID IS CHECKED AS A FILE, not merely as a string, because it is the host half of the
namespace the three vaults are bound to. A replaceable one can be forged, and a forged host
identity lets a manager on another host read and mutate credentials that are not its own.

The root and the search path are injected so the whole closure is exercised against a
fixture tree instead of against whichever host happens to run this suite.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_MACHINE_ID = "0123456789abcdef0123456789abcdef"


def _prereq():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_prereq.py"
    assert module_path.is_file(), "overseer/_lpm_prereq.py must exist"
    return importlib.import_module("_lpm_prereq")


def _host(*, root: pathlib.Path, machine_id: str = f"{_MACHINE_ID}\n", mode: int = 0o444):
    (root / "proc/self").mkdir(parents=True)
    (root / "proc/self/stat").write_text("1 (init) S", encoding="utf-8")
    (root / "usr/bin").mkdir(parents=True)
    (root / "usr/bin/keyctl").write_text("", encoding="utf-8")
    (root / "etc").mkdir()
    identity = root / "etc/machine-id"
    identity.write_text(machine_id, encoding="utf-8")
    identity.chmod(mode)
    return identity


def _bin(*, root: pathlib.Path, name: str = "op") -> pathlib.Path:
    directory = root / "path"
    directory.mkdir(exist_ok=True)
    executable = directory / name
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    return directory


def test_every_base_prerequisite_present_yields_the_digest_and_the_retained_executable(tmp_path):
    module = _prereq()
    _host(root=tmp_path)
    directory = _bin(root=tmp_path)

    checked = module.runtime_prerequisites(
        root=tmp_path, search_path=(directory,), executable_name="op"
    ).unwrap()

    assert (
        checked.machine_id_sha256
        == module.machine_id_defect(path=tmp_path / "etc/machine-id").unwrap()
    )
    assert checked.op_executable == str(directory / "op")


def test_an_absent_procfs_or_keyctl_refuses_before_anything_else_is_inspected(tmp_path):
    module = _prereq()

    empty = module.runtime_prerequisites(root=tmp_path, search_path=(), executable_name="op")

    assert empty.failure().error_type == "store-unavailable"
    assert empty.failure().message == "/proc/self/stat is unavailable"
    (tmp_path / "proc/self").mkdir(parents=True)
    (tmp_path / "proc/self/stat").write_text("1", encoding="utf-8")
    assert (
        module.runtime_prerequisites(root=tmp_path, search_path=(), executable_name="op")
        .failure()
        .message
        == "/usr/bin/keyctl is unavailable"
    )


def test_an_unsafe_machine_id_source_is_store_unavailable_by_type_owner_mode_or_content(tmp_path):
    module = _prereq()

    def _refusal(*, machine_id: str = f"{_MACHINE_ID}\n", mode: int = 0o444) -> str:
        root = tmp_path / f"host-{machine_id[:4]}-{mode}"
        root.mkdir()
        _host(root=root, machine_id=machine_id, mode=mode)
        return (
            module.runtime_prerequisites(root=root, search_path=(), executable_name="op")
            .failure()
            .message
        )

    assert _refusal(mode=0o644) == "/etc/machine-id is not mode 0444"
    assert _refusal(machine_id="not-a-machine-id\n") == (
        "/etc/machine-id content is not a machine id"
    )
    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "proc/self").mkdir(parents=True)
    (missing / "proc/self/stat").write_text("1", encoding="utf-8")
    (missing / "usr/bin").mkdir(parents=True)
    (missing / "usr/bin/keyctl").write_text("", encoding="utf-8")
    assert (
        module.runtime_prerequisites(root=missing, search_path=(), executable_name="op")
        .failure()
        .message.startswith("/etc/machine-id is unusable: ")
    )


def test_a_present_host_with_no_backend_executable_still_refuses(tmp_path):
    module = _prereq()
    _host(root=tmp_path)
    binary = tmp_path / "etc/machine-id-binary"
    binary.write_bytes(b"\xff\xfe")
    binary.chmod(0o444)

    assert (
        module.runtime_prerequisites(root=tmp_path, search_path=(), executable_name="op")
        .failure()
        .message
        == "op is not on the manager's PATH"
    )
    assert (
        module.machine_id_defect(path=binary)
        .failure()
        .message.startswith("/etc/machine-id is unreadable: ")
    )


def test_an_earlier_path_entry_without_the_executable_is_skipped_not_refused(tmp_path):
    module = _prereq()
    empty = tmp_path / "empty"
    empty.mkdir()
    directory = _bin(root=tmp_path)

    resolved = module.resolve_backend_executable(search_path=(empty, directory), name="op")

    assert resolved.unwrap() == str(directory / "op")


def test_a_symlinked_directory_or_non_root_owned_machine_id_is_refused(tmp_path):
    module = _prereq()
    real = tmp_path / "machine-id"
    real.write_text(f"{_MACHINE_ID}\n", encoding="utf-8")
    real.chmod(0o444)
    linked = tmp_path / "linked"
    linked.symlink_to(real)
    directory = tmp_path / "adir"
    directory.mkdir(mode=0o444)

    assert module.machine_id_defect(path=linked).failure().message == (
        "/etc/machine-id is a symlink"
    )
    assert module.machine_id_defect(path=directory).failure().message == (
        "/etc/machine-id is not a regular file"
    )
    if os.geteuid() == 0:
        os.chown(real, 1, 1)
        assert module.machine_id_defect(path=real).failure().message == (
            "/etc/machine-id is not root-owned"
        )


def test_the_backend_executable_is_the_first_on_the_path_resolved_through_its_symlinks(tmp_path):
    module = _prereq()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    target = second / "op-real"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    target.chmod(0o755)
    (first / "op").symlink_to(target)
    (second / "op").write_text("#!/bin/sh\n", encoding="utf-8")
    (second / "op").chmod(0o755)

    resolved = module.resolve_backend_executable(search_path=(first, second), name="op")

    assert resolved.unwrap() == str(target), "the symlink chain is resolved and retained"
    assert module.resolve_backend_executable(search_path=(), name="op").failure().message == (
        "op is not on the manager's PATH"
    )


def test_a_non_executable_or_non_regular_backend_path_is_refused_rather_than_skipped(tmp_path):
    module = _prereq()
    directory = tmp_path / "path"
    directory.mkdir()
    (directory / "op").write_text("", encoding="utf-8")
    (directory / "op").chmod(0o644)

    refusal = module.resolve_backend_executable(search_path=(directory,), name="op")

    # Skipping it and taking a LATER `op` would silently prefer a different binary than the
    # one the operator's PATH actually names first.
    assert refusal.failure().message == "op does not resolve to a regular executable"
