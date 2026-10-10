"""A zero-argument manager invocation is the exact path-sorted attention read."""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

from overseer._lpm_attention import attention_item_object, attention_items
from overseer._lpm_commands import ManagerInvocation, run_manager_command
from overseer._lpm_localstate import write_local_record
from overseer._vendor.returns.result import Success

__all__: list[str] = []

_RECORD_A = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_RECORD_B = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


@dataclass(frozen=True, kw_only=True)
class _AttentionRuntime:
    state_dir: pathlib.Path

    def run(self, *, invocation: ManagerInvocation) -> dict[str, object]:
        assert invocation.command == "attention"
        listed = attention_items(state_dir=self.state_dir, owner_uid=os.getuid()).unwrap()
        return {
            "version": 1,
            "status": "ok",
            "operation": "attention",
            "items": [attention_item_object(item=item) for item in listed],
        }


def _artifact(*, record_id: str, status: str) -> dict[str, object]:
    return {
        "version": 1,
        "type": "browser-verification-wall",
        "record_id": record_id,
        "operation_id": "9b2c4d6e-8f10-4a3b-9c5d-7e1f2a3b4c5d",
        "worker_pid": 321,
        "worker_start_ticks": 654,
        "provider": "anthropic",
        "account_id": f"account-{record_id[0]}",
        "reason": "captcha",
        "status": status,
        "raised_at": "2026-10-10T10:00:00Z",
        "deadline": "2026-10-10T11:00:00Z",
    }


def _write(*, state_dir: pathlib.Path, name: str, value: dict[str, object]) -> pathlib.Path:
    path = state_dir / "attention" / name
    written = write_local_record(path=path, value=value, owner_uid=os.getuid())
    assert isinstance(written, Success)
    return path


def _run(*, state_dir: pathlib.Path) -> dict[str, object]:
    try:
        return run_manager_command(arguments=(), runtime=_AttentionRuntime(state_dir=state_dir))
    except IndexError:
        return {"unimplemented": True}


def test_zero_arguments_return_exact_path_sorted_pending_attention(
    tmp_path: pathlib.Path,
) -> None:
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_attention.py"
    assert module_path.is_file(), "the shared attention reader must exist"
    empty = _run(state_dir=tmp_path / "absent")
    state_dir = tmp_path / "manager-state"
    path_b = _write(
        state_dir=state_dir, name="bb.json", value=_artifact(record_id=_RECORD_B, status="pending")
    )
    path_a = _write(
        state_dir=state_dir, name="aa.json", value=_artifact(record_id=_RECORD_A, status="pending")
    )
    _ = _write(
        state_dir=state_dir, name="cc.json", value=_artifact(record_id=_RECORD_A, status="resolved")
    )

    outcome = _run(state_dir=state_dir)

    assert empty == {"version": 1, "status": "ok", "operation": "attention", "items": []}
    assert outcome == {
        "version": 1,
        "status": "ok",
        "operation": "attention",
        "items": [
            {
                "path": str(path_a),
                "record_id": _RECORD_A,
                "provider": "anthropic",
                "account_id": "account-3",
                "reason": "captcha",
                "deadline": "2026-10-10T11:00:00Z",
            },
            {
                "path": str(path_b),
                "record_id": _RECORD_B,
                "provider": "anthropic",
                "account_id": "account-7",
                "reason": "captcha",
                "deadline": "2026-10-10T11:00:00Z",
            },
        ],
    }
