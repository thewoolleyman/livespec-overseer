"""Installed manager surfaces share one command dispatcher.

The package console and flattened plugin executable have different bootstrap
locations, but neither owns command behaviour.  This test pins the common
dispatcher before the later slices exercise recovery and process I/O.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib
import os
import pathlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import pytest

from overseer._lpm_config import ManagerConfig, default_config
from overseer._lpm_engine_context import EffectContext
from overseer._lpm_engine_records import RecordAction
from overseer._lpm_results import ManagerError, store_unavailable
from overseer._lpm_store import InMemorySecretStore, SecretStore
from overseer._vendor.returns.result import Failure, Result

__all__: list[str] = []


class _Invocation(Protocol):
    command: str


@dataclass(kw_only=True)
class _RecordingRuntime:
    commands: list[str] = field(default_factory=list)

    def run(self, *, invocation: _Invocation) -> str:
        self.commands.append(invocation.command)
        return invocation.command


@dataclass(frozen=True, kw_only=True)
class _TargetHost:
    state_dir: pathlib.Path
    owner_uid: int
    config: ManagerConfig
    store: SecretStore
    op_executable: str | None
    capture_time: Callable[[], str]
    new_operation_id: Callable[[], str]
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]


_NOW = "2026-10-11T04:00:00Z"
_EXPIRES = "2026-10-12T04:00:00Z"


def _target_host(*, state_dir: pathlib.Path, reference: str, now: str = _NOW) -> _TargetHost:
    return _TargetHost(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        config=default_config(),
        store=InMemorySecretStore(),
        op_executable="/usr/bin/op",
        capture_time=lambda: now,
        new_operation_id=lambda: reference,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )


def _registration_path(*, state_dir: pathlib.Path, run_id: str) -> pathlib.Path:
    from overseer._lpm_paths import local_record_path

    return local_record_path(
        state_dir=state_dir,
        family="run-registration",
        identity=(run_id,),
    ).unwrap()


def _register(
    *,
    state_dir: pathlib.Path,
    run_id: str,
    root: pathlib.Path,
    target: pathlib.Path,
    expires_at: str = _EXPIRES,
    create_directories: bool = True,
) -> pathlib.Path:
    from overseer._lpm_localstate import write_local_record

    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_dir.chmod(0o700)
    if create_directories:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        target.parent.chmod(0o700)
    path = _registration_path(state_dir=state_dir, run_id=run_id)
    write_local_record(
        path=path,
        value={
            "version": 1,
            "consumer_run_id": run_id,
            "isolated_root": str(root),
            "target_path": str(target),
            "created_at": _NOW,
            "expires_at": expires_at,
        },
        owner_uid=os.getuid(),
    ).unwrap()
    return path


def _target_request(*, run_id: str) -> dict[str, object]:
    return {"version": 1, "consumer_run_id": run_id, "adapter": "isolated-run"}


def _assert_registration_refused(
    *, tmp_path: pathlib.Path, suffix: str, root: pathlib.Path, target: pathlib.Path
) -> None:
    import overseer._lpm_runtime_target_registration as registration

    state = tmp_path / f"state-{suffix}"
    _register(state_dir=state, run_id=f"run-{suffix}", root=root, target=target)
    result = registration.registered_destination(
        host=_target_host(state_dir=state, reference=f"reference-{suffix}"),
        consumer_run_id=f"run-{suffix}",
    )
    assert isinstance(result, Failure)
    assert result.failure().error_type == "invalid-request"


def _install_destination_lock_observer(
    *,
    monkeypatch: pytest.MonkeyPatch,
    lock_path: pathlib.Path,
) -> list[str]:
    from overseer._lpm_locks import release_lock, try_lock

    target_effects = importlib.import_module("_lpm_effects_target")
    real_settle = target_effects.settle_record
    observed: list[str] = []

    def observe_lock(
        *,
        context: EffectContext,
        family: str,
        identity: tuple[str, ...],
        decide: Callable[[object | None], Result[RecordAction, ManagerError]],
    ) -> Result[str, ManagerError]:
        if family in {"issuance", "run-registration"}:
            contender = try_lock(path=lock_path, owner_uid=os.getuid()).unwrap()
            if family == "issuance":
                assert contender is None
                observed.append("held-for-issuance")
            else:
                assert contender is not None
                release_lock(held=contender)
                observed.append("released-before-registration-removal")
        return real_settle(context=context, family=family, identity=identity, decide=decide)

    monkeypatch.setattr(target_effects, "settle_record", observe_lock)
    return observed


def test_both_installed_surfaces_delegate_target_provision_and_report_to_one_runtime(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = pathlib.Path(__file__).parents[1]
    module_path = root / "overseer" / "_lpm_commands.py"
    assert module_path.is_file(), "the shared manager command dispatcher must exist"
    commands = importlib.import_module("_lpm_commands")
    runtime = _RecordingRuntime()

    assert [
        commands.run_manager_command(arguments=(command, flag, "-"), runtime=runtime)
        for command, flag in (
            ("target", "--target-json"),
            ("provision", "--request-json"),
            ("report", "--report-json"),
        )
    ] == ["target", "provision", "report"]
    assert runtime.commands == ["target", "provision", "report"]

    metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'llm-provider-manager = "overseer.manager_bootstrap:main"' in metadata
    launcher = root / ".claude-plugin" / "bin" / "llm-provider-manager"
    assert launcher.is_file()
    assert launcher.stat().st_mode & 0o111
    assert "overseer/manager_bootstrap.py" in launcher.read_text(encoding="utf-8")
    assert (root / ".claude-plugin" / "overseer" / "_lpm_commands.py").read_bytes() == (
        module_path.read_bytes()
    )

    bootstrap = importlib.import_module("manager_bootstrap")
    inherited = {
        "PATH": "/usr/bin",
        "ANTHROPIC_API_KEY": "must-not-be-read",
        "op_service_account_token": "must-not-be-read",
    }
    assert bootstrap.scrub_credential_overrides(environ=inherited) == (
        "ANTHROPIC_API_KEY",
        "op_service_account_token",
    )
    assert inherited == {"PATH": "/usr/bin"}

    invoked: list[tuple[str, ...]] = []

    def record_exec(_program: str, argv: list[str]) -> None:
        invoked.append(tuple(argv))

    monkeypatch.setattr(bootstrap, "execv", record_exec)
    monkeypatch.setattr(bootstrap.sys, "argv", ["llm-provider-manager", "target"])
    assert bootstrap.main() == 70
    assert invoked[0][1:3] == ("-I", "-S")
    assert capsys.readouterr().out.startswith('{"version":1,"status":"error"')

    monkeypatch.setattr(bootstrap.sys, "argv", ["llm-provider-manager", "--help"])
    assert bootstrap.main() == 70
    assert invoked[-1][-1] == "--help"
    assert capsys.readouterr().out == f"{bootstrap.INTERNAL_BUG_LINE}\n"


def test_isolated_run_registration_validation_owns_the_destination_lock_and_conflicts(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from overseer._lpm_canonical import length_prefixed_digest
    from overseer._lpm_runtime_issuance import issuance_for_run
    from overseer._lpm_runtime_target import run_target
    from overseer._vendor.returns.result import Success

    state_dir = tmp_path / "shared-state"
    root = tmp_path / "isolated"
    target = root / "credentials" / ".credentials.json"
    first_registration = _register(
        state_dir=state_dir,
        run_id="run-first",
        root=root,
        target=target,
    )
    canonical = str(target.resolve(strict=False))
    digest = length_prefixed_digest(values=(canonical,))
    destination_lock = state_dir / "locks" / "destination" / f"{digest}.lock"
    observed = _install_destination_lock_observer(
        monkeypatch=monkeypatch,
        lock_path=destination_lock,
    )
    first = run_target(
        host=_target_host(
            state_dir=state_dir,
            reference="10000000-0000-4000-8000-000000000001",
        ),
        normalized_input=_target_request(run_id="run-first"),
    )
    assert isinstance(first, Success)
    assert observed == ["held-for-issuance", "released-before-registration-removal"]
    assert not first_registration.exists()

    second_registration = _register(
        state_dir=state_dir,
        run_id="run-second",
        root=root,
        target=target,
    )
    second = run_target(
        host=_target_host(
            state_dir=state_dir,
            reference="20000000-0000-4000-8000-000000000002",
        ),
        normalized_input=_target_request(run_id="run-second"),
    )
    assert isinstance(second, Failure)
    assert second.failure().error_type == "invalid-request"
    assert (
        issuance_for_run(
            host=_target_host(state_dir=state_dir, reference="unused"),
            consumer_run_id="run-second",
        ).unwrap()
        is None
    )
    assert second_registration.exists()


def test_destination_conflict_scan_returns_its_typed_inventory_failure(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_runtime_issuance as issuance

    monkeypatch.setattr(
        issuance,
        "_issuance_inventory",
        lambda **_kwargs: Failure(store_unavailable(message="injected inventory failure")),
    )

    refused = issuance.refuse_destination_conflict(
        host=_target_host(state_dir=tmp_path / "state", reference="unused"),
        consumer_run_id="run-inventory-failure",
        destination=str(tmp_path / "target"),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"


def test_registration_removal_requires_the_locked_target_inputs(*, tmp_path: pathlib.Path) -> None:
    context_module = importlib.import_module("_lpm_engine_context")
    operation_module = importlib.import_module("_lpm_operation")
    identity_module = importlib.import_module("_lpm_operation_identity")
    target_effects = importlib.import_module("_lpm_effects_target")
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    context = context_module.EffectContext(
        engine=context_module.OperationEngine(
            state_dir=state_dir,
            owner_uid=os.getuid(),
            store=InMemorySecretStore(),
        ),
        operation=operation_module.OperationRecord(
            operation_id="50000000-0000-4000-8000-000000000005",
            command="target",
            phase="issue",
            idempotency_key="a" * 64,
            accepted_at=_NOW,
            normalized_input={"consumer_run_id": "run-missing-target-inputs"},
            terminal_result=None,
            ordered_effects=("registration-remove",),
            completed_step=-1,
        ),
        inputs=context_module.EffectInputs(),
        position=identity_module.EffectPosition(
            index=0,
            effect="registration-remove",
            effect_id="b" * 64,
        ),
    )

    refused = target_effects.registration_remove(context=context)

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "internal-bug"


def test_isolated_run_registration_refuses_missing_broad_and_symlinked_directories(
    *, tmp_path: pathlib.Path
) -> None:
    import overseer._lpm_runtime_target_registration as registration

    missing_root = tmp_path / "missing-root"
    state = tmp_path / "state-missing"
    _register(
        state_dir=state,
        run_id="run-missing",
        root=missing_root,
        target=missing_root / "child" / "credential",
        create_directories=False,
    )
    missing = registration.registered_destination(
        host=_target_host(state_dir=state, reference="reference-missing"),
        consumer_run_id="run-missing",
    )
    assert isinstance(missing, Failure)
    assert missing.failure().error_type == "invalid-request"

    broad_root = tmp_path / "broad-root"
    broad_target = broad_root / "child" / "credential"
    broad_target.parent.mkdir(mode=0o700, parents=True)
    state = tmp_path / "state-broad"
    _register(
        state_dir=state,
        run_id="run-broad",
        root=broad_root,
        target=broad_target,
    )
    broad_root.chmod(0o755)
    broad = registration.registered_destination(
        host=_target_host(state_dir=state, reference="reference-broad"),
        consumer_run_id="run-broad",
    )
    assert isinstance(broad, Failure)
    assert broad.failure().error_type == "invalid-request"

    real_root = tmp_path / "real-root"
    real_target = real_root / "child" / "credential"
    real_target.parent.mkdir(mode=0o700, parents=True)
    symlink_root = tmp_path / "symlink-root"
    symlink_root.symlink_to(real_root, target_is_directory=True)
    _assert_registration_refused(
        tmp_path=tmp_path,
        suffix="symlink",
        root=symlink_root,
        target=symlink_root / "child" / "credential",
    )


def test_isolated_run_registration_refuses_wrongly_owned_directory(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_runtime_target_registration as registration

    owner_root = tmp_path / "owner-root"
    owner_target = owner_root / "child" / "credential"
    _register(
        state_dir=tmp_path / "state-owner",
        run_id="run-owner",
        root=owner_root,
        target=owner_target,
    )
    real_lstat = pathlib.Path.lstat

    def wrong_owner(self: pathlib.Path):
        status = real_lstat(self)
        if self == owner_root:
            fields = list(status)
            fields[4] = os.getuid() + 1
            return os.stat_result(fields)
        return status

    with monkeypatch.context() as context:
        context.setattr(pathlib.Path, "lstat", wrong_owner)
        wrong = registration.registered_destination(
            host=_target_host(state_dir=tmp_path / "state-owner", reference="reference-owner"),
            consumer_run_id="run-owner",
        )
    assert isinstance(wrong, Failure)
    assert wrong.failure().error_type == "invalid-request"


def test_isolated_run_registration_refuses_protected_or_unresolvable_home(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_runtime_target_registration as registration

    protected_home = tmp_path / "account-home"
    protected = protected_home / ".claude" / ".credentials.json"
    protected.parent.mkdir(mode=0o700, parents=True)
    protected_home.chmod(0o700)
    protected.parent.chmod(0o700)
    _register(
        state_dir=tmp_path / "state-protected",
        run_id="run-protected",
        root=protected_home,
        target=protected,
    )
    with monkeypatch.context() as context:
        context.setattr(registration, "account_database_home", lambda **_kwargs: protected_home)
        protected_result = registration.registered_destination(
            host=_target_host(
                state_dir=tmp_path / "state-protected", reference="reference-protected"
            ),
            consumer_run_id="run-protected",
        )
    assert isinstance(protected_result, Failure)
    assert protected_result.failure().error_type == "invalid-request"

    no_home_root = tmp_path / "no-home-root"
    no_home_target = no_home_root / "child" / "credential"
    _register(
        state_dir=tmp_path / "state-no-home",
        run_id="run-no-home",
        root=no_home_root,
        target=no_home_target,
    )
    with monkeypatch.context() as context:
        context.setattr(registration, "account_database_home", lambda **_kwargs: None)
        no_home = registration.registered_destination(
            host=_target_host(state_dir=tmp_path / "state-no-home", reference="reference-no-home"),
            consumer_run_id="run-no-home",
        )
    assert isinstance(no_home, Failure)
    assert no_home.failure().error_type == "invalid-request"


def test_isolated_run_registration_removes_expiry_and_types_lock_failure(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_runtime_target_registration as registration

    expired_state = tmp_path / "state-expired"
    expired_path = _register(
        state_dir=expired_state,
        run_id="run-expired",
        root=tmp_path / "expired-root",
        target=tmp_path / "expired-root" / "child" / "credential",
        expires_at=_EXPIRES,
    )
    expired = registration.registered_destination(
        host=_target_host(
            state_dir=expired_state,
            reference="reference-expired",
            now=_EXPIRES,
        ),
        consumer_run_id="run-expired",
    )
    assert isinstance(expired, Failure)
    assert expired.failure().error_type == "invalid-request"
    assert not expired_path.exists()

    failed_cleanup_state = tmp_path / "state-expired-cleanup-failure"
    failed_cleanup_path = _register(
        state_dir=failed_cleanup_state,
        run_id="run-expired-cleanup-failure",
        root=tmp_path / "expired-cleanup-failure-root",
        target=tmp_path / "expired-cleanup-failure-root" / "child" / "credential",
        expires_at=_EXPIRES,
    )
    with monkeypatch.context() as context:
        context.setattr(
            registration,
            "remove_local_record",
            lambda **_kwargs: Failure(store_unavailable(message="injected cleanup failure")),
        )
        failed_cleanup = registration.registered_destination(
            host=_target_host(
                state_dir=failed_cleanup_state,
                reference="reference-expired-cleanup-failure",
                now=_EXPIRES,
            ),
            consumer_run_id="run-expired-cleanup-failure",
        )
    assert isinstance(failed_cleanup, Failure)
    assert failed_cleanup.failure().error_type == "store-unavailable"
    assert failed_cleanup_path.exists()

    blocked_state = tmp_path / "state-blocked-lock"
    blocked_root = tmp_path / "blocked-root"
    blocked_target = blocked_root / "child" / "credential"
    _register(
        state_dir=blocked_state,
        run_id="run-blocked-lock",
        root=blocked_root,
        target=blocked_target,
    )
    (blocked_state / "locks").mkdir(mode=0o700)
    _ = (blocked_state / "locks" / "destination").write_text("not a directory", encoding="utf-8")
    blocked = registration.registered_destination(
        host=_target_host(state_dir=blocked_state, reference="reference-blocked"),
        consumer_run_id="run-blocked-lock",
    )
    assert isinstance(blocked, Failure)
    assert blocked.failure().error_type == "store-unavailable"


def test_armed_target_mismatch_removes_staged_secret_bytes_before_uncommitted(
    *, tmp_path: pathlib.Path
) -> None:
    from overseer._lpm_localstate import write_local_record
    from overseer._lpm_paths import local_record_path
    from overseer._lpm_target import UNCOMMITTED
    from overseer._lpm_target_evidence import TargetEvidenceBinding, target_status_with_evidence

    binding = TargetEvidenceBinding(
        state_dir=tmp_path / "state",
        destination=str(tmp_path / "target" / "credential"),
        owner_uid=os.getuid(),
        target_ref="30000000-0000-4000-8000-000000000003",
        consumer_run_id="run-armed-mismatch",
        value_generation="40000000-0000-4000-8000-000000000004",
    )
    destination = pathlib.Path(binding.destination)
    destination.parent.mkdir(mode=0o700, parents=True)
    destination.write_bytes(b"prior-target")
    destination.chmod(0o600)
    staged = destination.with_name(f".{destination.name}.lpm-prepared")
    secret = b"secret-that-must-not-survive-uncommitted"
    staged.write_bytes(secret)
    staged.chmod(0o600)
    evidence_path = local_record_path(
        state_dir=binding.state_dir,
        family="target-commit",
        identity=(binding.target_ref,),
    ).unwrap()
    write_local_record(
        path=evidence_path,
        value={
            "version": 1,
            "status": "armed",
            "target_ref": binding.target_ref,
            "consumer_run_id": binding.consumer_run_id,
            "value_generation": binding.value_generation,
            "target_sha256": hashlib.sha256(secret).hexdigest(),
            "prepared_at": _NOW,
            "committed_at": "2026-10-11T04:00:01Z",
        },
        owner_uid=binding.owner_uid,
    ).unwrap()

    recovered = target_status_with_evidence(binding=binding).unwrap()

    assert recovered.status == UNCOMMITTED
    assert destination.read_bytes() == b"prior-target"
    assert not staged.exists()
    assert not evidence_path.exists()


def test_role_companion_maps_only_explicitly_inheritable_descriptors(
    *, tmp_path: pathlib.Path
) -> None:
    companion = importlib.import_module("_lpm_companion")
    assert hasattr(
        companion, "inherited_descriptor_mapping"
    ), "the role companion must distinguish explicit inheritance from its own open files"
    allowed = os.open(tmp_path / "target.lock", os.O_RDWR | os.O_CREAT, 0o600)
    internal = os.open(tmp_path / "runtime-internal", os.O_RDWR | os.O_CREAT, 0o600)
    flags = fcntl.fcntl(allowed, fcntl.F_GETFD)
    _ = fcntl.fcntl(allowed, fcntl.F_SETFD, flags & ~fcntl.FD_CLOEXEC)
    try:
        assert os.get_inheritable(internal) is False
        assert companion.inherited_descriptor_mapping(names=("target-reference-lock",)) == {
            "target-reference-lock": allowed
        }
    finally:
        os.close(internal)
        os.close(allowed)
