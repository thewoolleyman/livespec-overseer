"""The two launchers' shared machinery: the scrubbing bootstrap, the isolated companion, the host.

SPECIFICATION/contracts.md and non-functional-requirements.md between them fix this layer almost
line by line, and three of those requirements have an easy wrong implementation that only a test
at this level can catch:

* THE SCRUB HAPPENS BEFORE THE HAND-OVER, AND BY NAME. The bootstrap "MUST remove every inherited
  entry in the complete closed credential-override set by ASCII-uppercased name without reading its
  value" as "its first manager-owned action". A bootstrap that scrubbed after re-executing, or that
  inspected values to decide, would look identical from the outside.
* THE CLOSED SET MUST NOT DRIFT. `_lpm_env` owns it, and the bootstrap may not import `_lpm_env` --
  every product import in that file would run with the credentials still in the environment. So the
  set is duplicated, and `test_the_bootstraps_closed_set_matches_the_one_lpm_env_owns` is the only
  thing standing between that duplication and silent divergence.
* THE RE-EXEC VECTOR IS EXACTLY `-I -S <absolute companion> <original arguments>`. Drop `-S` and
  site-packages discovery comes back, so a consumer's environment can repoint the manager at
  another plugin's code; drop the absolute path and the same is true of the script resolution.

THE REFUSAL A STORE-LESS HOST GIVES IS MEASURED, WHICH IS WHY THE FIXTURE ROOT EXISTS. The
prerequisite closure is root-injectable precisely so it can be exercised against a tree rather than
against whatever machine the suite runs on, and the two legs below are both driven that way: a root
MISSING `/usr/bin/keyctl` must name that, and a root that SATISFIES every listed prerequisite must
get past it and name the privileged role child instead. Without the second leg, "fail closed" would
be indistinguishable from "never tried".
"""

from __future__ import annotations

import importlib
import os
import pathlib
import sys
from typing import Any

import pytest

__all__: list[str] = []

BOOTSTRAP_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "manager_bootstrap.py"
COMPANION_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_companion.py"
HOST_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_manager_host.py"

_MACHINE_ID = "0123456789abcdef0123456789abcdef"


def _bootstrap() -> Any:
    assert BOOTSTRAP_PATH.is_file(), "overseer/manager_bootstrap.py must exist"
    return importlib.import_module("manager_bootstrap")


def _companion() -> Any:
    assert COMPANION_PATH.is_file(), "overseer/_lpm_companion.py must exist"
    return importlib.import_module("_lpm_companion")


def _host_module() -> Any:
    assert HOST_PATH.is_file(), "overseer/_lpm_manager_host.py must exist"
    return importlib.import_module("_lpm_manager_host")


def _failure_type() -> Any:
    from overseer._vendor.returns.result import Failure

    return Failure


# --------------------------------------------------------------------------------------
# manager_bootstrap — scrub, then re-exec.
# --------------------------------------------------------------------------------------


def test_the_bootstraps_closed_set_matches_the_one_lpm_env_owns() -> None:
    """The anti-drift control on a duplication the contract forces."""
    import _lpm_env

    module = _bootstrap()

    assert set(module.EXACT_CREDENTIAL_OVERRIDES) == set(_lpm_env.EXACT_CREDENTIAL_OVERRIDES)
    assert set(module.CREDENTIAL_OVERRIDE_PREFIXES) == set(_lpm_env.CREDENTIAL_OVERRIDE_PREFIXES)


@pytest.mark.parametrize(
    "name",
    [
        "CLAUDECODE",
        "claudecode",
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "OP_SERVICE_ACCOUNT_TOKEN",
        "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN",
    ],
)
def test_every_credential_override_name_is_recognized(*, name: str) -> None:
    assert _bootstrap().is_credential_override(name=name)


@pytest.mark.parametrize("name", ["PATH", "HOME", "ANTHROPIC", "CLAUDE", "OPERATOR"])
def test_an_unrelated_name_is_not_an_override(*, name: str) -> None:
    assert not _bootstrap().is_credential_override(name=name)


def test_the_scrub_deletes_exactly_the_override_entries() -> None:
    environ = {
        "PATH": "/usr/bin",
        "ANTHROPIC_API_KEY": "secret",
        "CLAUDECODE": "1",
        "HOME": "/root",
    }

    removed = _bootstrap().scrub_credential_overrides(environ=environ)

    assert removed == ("ANTHROPIC_API_KEY", "CLAUDECODE")
    assert environ == {"PATH": "/usr/bin", "HOME": "/root"}


def test_the_bootstrap_scrubs_then_re_execs_with_the_isolated_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _bootstrap()
    calls: list[tuple[str, list[str]]] = []
    seen: list[bool] = []

    def _execv(executable: str, argv: list[str]) -> None:
        seen.append("ANTHROPIC_API_KEY" in os.environ)
        calls.append((executable, argv))

    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setattr(sys, "argv", ["llm-provider-manager", "attention"])
    monkeypatch.setattr(module, "execv", _execv)

    status = module.main()

    assert len(calls) == 1
    executable, argv = calls[0]
    assert executable == sys.executable
    assert argv == [sys.executable, "-I", "-S", str(module.companion_path()), "attention"]
    assert seen == [False], "the scrub must happen BEFORE the hand-over, not after"
    assert status == module.INTERNAL_BUG_STATUS


def test_a_returning_exec_reports_the_internal_bug_line(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A successful exec never returns, so reaching the tail means it could not be established."""
    import json

    module = _bootstrap()
    monkeypatch.setattr(sys, "argv", ["llm-provider-manager"])
    monkeypatch.setattr(module, "execv", lambda *_args: None)

    status = module.main()

    body = json.loads(capsys.readouterr().out.strip())
    assert body["error_type"] == "internal-bug"
    assert status == 70


def test_an_exec_that_fails_reports_the_internal_bug_line(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _bootstrap()

    def _explode(*_args: object) -> None:
        raise OSError("exec is unavailable")

    monkeypatch.setattr(sys, "argv", ["llm-provider-manager"])
    monkeypatch.setattr(module, "execv", _explode)

    status = module.main()

    assert '"internal-bug"' in capsys.readouterr().out
    assert status == 70


def test_an_absent_companion_is_reported_without_attempting_an_exec(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _bootstrap()

    def _forbidden(*_args: object) -> None:
        raise AssertionError("an absent companion must not be exec'd")

    monkeypatch.setattr(sys, "argv", ["llm-provider-manager"])
    monkeypatch.setattr(module, "execv", _forbidden)
    monkeypatch.setattr(module, "companion_path", lambda: pathlib.Path("/nonexistent/companion.py"))

    status = module.main()

    assert '"internal-bug"' in capsys.readouterr().out
    assert status == 70


def test_the_companion_path_sits_beside_the_bootstrap() -> None:
    module = _bootstrap()

    assert module.companion_path() == BOOTSTRAP_PATH.parent / module.COMPANION_MODULE_NAME
    assert module.companion_path().is_file()


# --------------------------------------------------------------------------------------
# _lpm_companion — load the package by absolute path, then dispatch.
# --------------------------------------------------------------------------------------


def test_the_companion_loads_the_package_beside_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _companion()
    monkeypatch.setitem(sys.modules, module.PACKAGE_NAME, sys.modules[module.PACKAGE_NAME])

    loaded = module.load_product_package(root=module.package_root())

    assert loaded is not None
    assert loaded.__name__ == "overseer"
    assert loaded.__path__ == [str(module.package_root())]


def test_a_package_with_no_loadable_spec_is_an_internal_bug(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A rail no real tree reaches, driven through the attribute that builds the spec."""
    module = _companion()
    monkeypatch.setattr(module, "spec_from_file_location", lambda *_args, **_kwargs: None)

    status = module.run(arguments=["attention"], root=module.package_root())

    assert '"internal-bug"' in capsys.readouterr().out
    assert status == 70


def test_the_companion_dispatches_one_command_and_propagates_its_exit_status(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown subcommand is refused before configuration, so this touches no host state."""
    import json

    module = _companion()
    monkeypatch.setitem(sys.modules, module.PACKAGE_NAME, sys.modules[module.PACKAGE_NAME])

    status = module.run(arguments=["nonsense"], root=module.package_root())

    body = json.loads(capsys.readouterr().out.strip())
    assert body["error_type"] == "invalid-request"
    assert status == 2


def test_a_host_that_cannot_be_resolved_is_presented_as_its_own_refusal(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    import _lpm_manager_host

    module = _companion()
    monkeypatch.setitem(sys.modules, module.PACKAGE_NAME, sys.modules[module.PACKAGE_NAME])
    monkeypatch.setattr(_lpm_manager_host, "account_database_home", lambda *, uid: None)

    status = module.run(arguments=["attention"], root=module.package_root())

    body = json.loads(capsys.readouterr().out.strip())
    assert body["error_type"] == "store-unavailable"
    assert status == 4


def test_the_companion_main_reads_real_argv(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _companion()
    monkeypatch.setitem(sys.modules, module.PACKAGE_NAME, sys.modules[module.PACKAGE_NAME])
    monkeypatch.setattr(sys, "argv", ["_lpm_companion.py", "nonsense"])

    status = module.main()

    assert '"invalid-request"' in capsys.readouterr().out
    assert status == 2


# --------------------------------------------------------------------------------------
# _lpm_manager_host — the measured prerequisite closure behind every store port.
# --------------------------------------------------------------------------------------


def _satisfied_root(*, tmp_path: pathlib.Path) -> pathlib.Path:
    """A fixture tree that satisfies every base prerequisite the contract lists."""
    root = tmp_path / "root"
    for relative in ("proc/self/stat", "usr/bin/keyctl"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("fixture\n", encoding="utf-8")
    machine_id = root / "etc" / "machine-id"
    machine_id.parent.mkdir(parents=True, exist_ok=True)
    _ = machine_id.write_text(f"{_MACHINE_ID}\n", encoding="utf-8")
    machine_id.chmod(0o444)
    return root


def _backend_executable(*, tmp_path: pathlib.Path) -> pathlib.Path:
    directory = tmp_path / "bin"
    directory.mkdir(parents=True, exist_ok=True)
    executable = directory / "op"
    _ = executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    return directory


def _ports(*, root: pathlib.Path, path_entries: tuple[pathlib.Path, ...]) -> Any:
    from _lpm_config import default_config

    return _host_module().BackendPorts(
        config=default_config(), root=root, path_entries=path_entries
    )


def test_the_search_path_is_the_inherited_path_in_order() -> None:
    module = _host_module()

    assert module.search_path(environ={"PATH": "/a::/b"}) == (
        pathlib.Path("/a"),
        pathlib.Path("/b"),
    )
    assert module.search_path(environ={}) == ()


def test_a_missing_prerequisite_is_named_by_the_refusal(tmp_path: pathlib.Path) -> None:
    """The measured leg: this tree has procfs but no `/usr/bin/keyctl`, and the message says so.

    The keyring is the prerequisite that makes this sandbox -- and any CI runner -- unable to reach
    the privileged role child at all, so it is the one worth naming explicitly.
    """
    root = _satisfied_root(tmp_path=tmp_path)
    (root / "usr" / "bin" / "keyctl").unlink()
    ports = _ports(root=root, path_entries=())

    outcome = ports.records()

    assert isinstance(outcome, _failure_type())
    error = outcome.failure()
    assert error.error_type == "store-unavailable"
    assert "keyctl" in error.message


def test_a_missing_backend_executable_is_named_by_the_refusal(tmp_path: pathlib.Path) -> None:
    ports = _ports(root=_satisfied_root(tmp_path=tmp_path), path_entries=())

    error = ports.records().failure()

    assert error.error_type == "store-unavailable"
    assert "op is not on the manager's PATH" in error.message


@pytest.mark.parametrize(
    ("port", "role"),
    [
        ("records", "metadata-reader"),
        ("read_value", "final-provisioning"),
        ("write_status", "lifecycle-writer"),
    ],
)
def test_a_satisfied_prerequisite_closure_reaches_the_named_role_child(
    *, tmp_path: pathlib.Path, port: str, role: str
) -> None:
    """The second leg: every listed prerequisite PASSED, so the refusal names what is unwritten."""
    from _lpm_record import CredentialRecord

    ports = _ports(
        root=_satisfied_root(tmp_path=tmp_path),
        path_entries=(_backend_executable(tmp_path=tmp_path),),
    )
    record = CredentialRecord(
        record_id="d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69",
        provider="anthropic",
        account_id="acct-1",
        kind="claude-code-oauth",
        purpose="factory",
        status="valid",
        acquired_at="2026-09-30T20:00:00Z",
        expires_at=None,
        last_validated="2026-09-30T20:00:00Z",
        value_generation="9b3e7c51-0a2d-4f68-b1c4-7e5a2d9f06b8",
        value_ref="op://values/x/credential",
        previous_value_ref=None,
    )
    arguments: dict[str, dict[str, object]] = {
        "records": {},
        "read_value": {"value_ref": "op://values/x/credential"},
        "write_status": {"record": record, "next_status": "suspect", "now": "2026-09-30T20:00:00Z"},
    }

    error = getattr(ports, port)(**arguments[port]).failure()

    assert error.error_type == "store-unavailable"
    assert error.message == f"the {role} credential-role child is not composed in this build"


def test_the_backend_closure_resolves_the_configured_executable(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_config import default_config

    module = _host_module()
    resolved = module.credential_backend(
        config=default_config(),
        root=_satisfied_root(tmp_path=tmp_path),
        path_entries=(_backend_executable(tmp_path=tmp_path),),
    )

    assert not isinstance(resolved, _failure_type())
    assert resolved.unwrap().op_executable.endswith("/op")
    assert module.BACKEND_EXECUTABLES == {"onepassword": "op"}


def test_a_uid_with_no_account_database_home_is_store_unavailable(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    module = _host_module()
    monkeypatch.setattr(module, "account_database_home", lambda *, uid: None)

    outcome = module.real_host(environ={}, uid=1, root=tmp_path, now="2026-09-30T20:00:00Z")

    assert isinstance(outcome, _failure_type())
    assert outcome.failure().error_type == "store-unavailable"


def test_an_unusable_configuration_file_refuses_before_any_command_runs(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    from _lpm_paths import config_file

    module = _host_module()
    path = config_file(home=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text('{"version": 9}', encoding="utf-8")
    monkeypatch.setattr(module, "account_database_home", lambda *, uid: tmp_path)

    outcome = module.real_host(environ={}, uid=1, root=tmp_path, now="2026-09-30T20:00:00Z")

    assert isinstance(outcome, _failure_type())
    assert outcome.failure().error_type == "invalid-request"


def test_a_resolved_host_carries_the_state_directory_and_every_port(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    from _lpm_paths import manager_state_dir

    module = _host_module()
    monkeypatch.setattr(module, "account_database_home", lambda *, uid: tmp_path)

    host = module.real_host(
        environ={"PATH": "/usr/bin"}, uid=4242, root=tmp_path, now="2026-09-30T20:00:00Z"
    ).unwrap()

    assert host.state_dir == manager_state_dir(home=tmp_path)
    assert host.owner_uid == 4242
    assert host.now == "2026-09-30T20:00:00Z"
    assert isinstance(host.records(), _failure_type())


def test_an_issued_reference_is_unguessable_and_never_repeats() -> None:
    module = _host_module()

    references = {module.issued_reference() for _ in range(8)}

    assert len(references) == 8
    assert all(len(reference) >= module.REFERENCE_ENTROPY_BYTES for reference in references)


def test_the_manager_clock_is_the_canonical_spelling() -> None:
    from _lpm_time import is_canonical_timestamp

    assert is_canonical_timestamp(text=_host_module().manager_now())


def test_standard_input_is_read_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO('{"version":1}\n'))

    assert _host_module().stdin_text() == '{"version":1}\n'


def test_the_real_lock_clock_is_the_system_clock() -> None:
    host = (
        _host_module()
        .real_host(environ={}, uid=os.geteuid(), root=pathlib.Path("/"), now="2026-09-30T20:00:00Z")
        .unwrap()
    )

    first = host.monotonic()
    host.sleep(0.0)

    assert host.monotonic() >= first
