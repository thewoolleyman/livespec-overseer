"""Shared installed pre-operation runtime and typed consumer wire boundary."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_attention import attention_item_object, attention_items
from _lpm_commands import ManagerInvocation
from _lpm_config import ManagerConfig, load_manager_config
from _lpm_paths import account_database_home, config_file, manager_state_dir
from _lpm_results import (
    ManagerError,
    internal_bug,
    invalid_report,
    invalid_request,
    store_unavailable,
)
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

    def run(self, *, invocation: ManagerInvocation) -> CommandOutcome:
        """Answer attention and reject malformed object commands before any operation."""
        if invocation.command == "attention":
            listed = attention_items(state_dir=self.state_dir, owner_uid=self.owner_uid)
            if isinstance(listed, Failure):
                return error_outcome(error=listed.failure())
            return success_outcome(
                payload={
                    "operation": "attention",
                    "items": [attention_item_object(item=item) for item in listed.unwrap()],
                }
            )
        source = invocation.source
        if source is None:
            return error_outcome(
                error=internal_bug(message="an object command reached the runtime without input")
            )
        refuse = invalid_report if invocation.command == "report" else invalid_request
        parsed = read_command_object(source=source, read_input=self.read_input, refuse=refuse)
        if isinstance(parsed, Failure):
            return error_outcome(error=parsed.failure())
        return error_outcome(error=refuse(message=f"{invocation.command} input is invalid"))


def runtime_for_host() -> Result[ConcreteManagerRuntime, ManagerError]:
    """Resolve the local namespace without reading any credential value."""
    uid = os.geteuid()
    home = account_database_home(uid=uid)
    if home is None:
        return Failure(store_unavailable(message="the effective user has no account home"))
    configured = load_manager_config(path=config_file(home=home))
    if isinstance(configured, Failure):
        return Failure(configured.failure())
    return Success(
        ConcreteManagerRuntime(
            state_dir=manager_state_dir(home=home),
            owner_uid=uid,
            config=configured.unwrap(),
            read_input=sys.stdin.read,
        )
    )
