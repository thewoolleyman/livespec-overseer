"""Shared concrete command runtime used by both installed executable surfaces."""

from __future__ import annotations

import datetime
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_attention import attention_item_object, attention_items
from _lpm_commands import ManagerInvocation
from _lpm_config import ManagerConfig, load_manager_config
from _lpm_operation_input import normalized_input_defect
from _lpm_paths import account_database_home, config_file, manager_state_dir
from _lpm_provision_request import provision_request_from_object
from _lpm_reports import report_from_object
from _lpm_results import (
    ManagerError,
    internal_bug,
    invalid_report,
    invalid_request,
    store_unavailable,
)
from _lpm_role_runner import subprocess_role_launch
from _lpm_runtime_backend import RolePorts
from _lpm_runtime_base import (
    FinalProvisioningPort,
    ProvisionRuntimeHost,
    RuntimeHost,
    TargetStatusPort,
)
from _lpm_runtime_provision import run_provision
from _lpm_runtime_report import run_report
from _lpm_runtime_target import run_target
from _lpm_store import SecretStore
from _lpm_time import capture_manager_time
from _lpm_wire import CommandOutcome, error_outcome, read_command_object, success_outcome

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ConcreteManagerRuntime",
    "runtime_for_host",
]


@dataclass(frozen=True, kw_only=True)
class ConcreteManagerRuntime:
    """Validated local host facts shared by both installed executable surfaces."""

    state_dir: Path
    owner_uid: int
    config: ManagerConfig
    read_input: Callable[[], str]
    store: SecretStore | None = None
    provision_target: FinalProvisioningPort | None = None
    op_executable: str | None = None
    capture_time: Callable[[], str] = lambda: capture_manager_time(
        now=datetime.datetime.now(tz=datetime.timezone.utc)
    )
    new_operation_id: Callable[[], str] = lambda: str(uuid.uuid4())
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    target_status: TargetStatusPort | None = None
    acquisition: Callable[..., Result[dict[str, object], ManagerError]] | None = None

    def run(self, *, invocation: ManagerInvocation) -> CommandOutcome:
        """Validate one invocation, then drive its concrete operation or attention query."""
        if invocation.command == "attention":
            return self._attention()
        source = invocation.source
        if source is None:
            return error_outcome(
                error=internal_bug(message="an object command reached the runtime without input")
            )
        refuse = invalid_report if invocation.command == "report" else invalid_request
        parsed = read_command_object(source=source, read_input=self.read_input, refuse=refuse)
        if isinstance(parsed, Failure):
            return error_outcome(error=parsed.failure())
        defect = self._input_defect(command=invocation.command, parsed=parsed.unwrap())
        if defect is not None:
            return error_outcome(error=defect)
        return self._run_object(command=invocation.command, parsed=parsed.unwrap())

    def _attention(self) -> CommandOutcome:
        listed = attention_items(state_dir=self.state_dir, owner_uid=self.owner_uid)
        if isinstance(listed, Failure):
            return error_outcome(error=listed.failure())
        return success_outcome(
            payload={
                "operation": "attention",
                "items": [attention_item_object(item=item) for item in listed.unwrap()],
            }
        )

    def _input_defect(self, *, command: str, parsed: object) -> ManagerError | None:
        if command == "acquire":
            return None
        if command == "target":
            defect = normalized_input_defect(command=command, normalized_input=parsed)
            if defect is not None:
                return invalid_request(message=defect)
            source = cast("dict[str, object]", parsed)
            if source["adapter"] not in self.config.enabled_target_adapters:
                return invalid_request(message="target adapter is not enabled")
            return None
        if command == "provision":
            accepted = provision_request_from_object(parsed=parsed)
            return accepted.failure() if isinstance(accepted, Failure) else None
        accepted_report = report_from_object(parsed=parsed)
        return accepted_report.failure() if isinstance(accepted_report, Failure) else None

    def _run_object(self, *, command: str, parsed: object) -> CommandOutcome:
        if command == "acquire":
            acquire = cast(
                "Callable[..., Result[dict[str, object], ManagerError]]", self.acquisition
            )
            return error_outcome(error=acquire(request=parsed).failure())
        bound = self.store is not None and (
            command != "provision" or self.provision_target is not None
        )
        if not bound:
            return error_outcome(
                error=internal_bug(message="object command runtime ports are not bound")
            )
        if command == "target":
            result = run_target(
                host=cast("RuntimeHost", self),
                normalized_input=cast("dict[str, object]", parsed),
            )
        elif command == "provision":
            result = run_provision(
                host=cast("ProvisionRuntimeHost", self),
                request=provision_request_from_object(parsed=parsed).unwrap(),
            )
        else:
            result = run_report(
                host=cast("RuntimeHost", self), report=report_from_object(parsed=parsed).unwrap()
            )
        if isinstance(result, Failure):
            return error_outcome(error=result.failure())
        return success_outcome(payload=result.unwrap())


def runtime_for_host() -> Result[ConcreteManagerRuntime, ManagerError]:
    """Resolve the local namespace without reading any credential value."""
    uid = os.geteuid()
    home = account_database_home(uid=uid)
    if home is None:
        return Failure(store_unavailable(message="the effective user has no account home"))
    configured = load_manager_config(path=config_file(home=home))
    if isinstance(configured, Failure):
        return Failure(configured.failure())
    state_dir = manager_state_dir(home=home)
    ports = RolePorts(
        config=configured.unwrap(),
        owner_uid=uid,
        state_dir=state_dir,
        environ=os.environ,
        launch=subprocess_role_launch,
        python_executable=str(Path(sys.executable).resolve()),
        packaged_companion=str(Path(__file__).with_name("_lpm_companion.py").resolve()),
    )
    return Success(
        ConcreteManagerRuntime(
            state_dir=state_dir,
            owner_uid=uid,
            config=configured.unwrap(),
            read_input=sys.stdin.read,
            store=ports,
            provision_target=ports,
            target_status=ports.target_status,
        )
    )
