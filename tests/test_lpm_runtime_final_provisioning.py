"""The command runtime hands final provisioning only secret-free role input."""

from __future__ import annotations

import json
import os
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass, field

from overseer._lpm_role_runner import RoleCompletion
from overseer._lpm_roles import PackagedCompanion
from overseer._lpm_runtime_roles import FinalProvisioningRequest, run_final_provisioning

__all__: list[str] = []

_SECRET = "sk-ant-oat0-parent-must-never-hold-or-forward"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"


@dataclass(kw_only=True)
class _CommittedChild:
    request_bytes: bytes = b"{}"
    environ: Mapping[str, str] = field(default_factory=dict)
    inherited_fds: tuple[int, ...] = ()

    def __call__(
        self,
        *,
        argv: tuple[str, ...],
        environ: Mapping[str, str],
        request_bytes: bytes,
        timeout_seconds: float,
        inherited_fds: tuple[int, ...],
    ) -> RoleCompletion:
        _ = (argv, timeout_seconds)
        self.request_bytes = request_bytes
        self.environ = environ
        self.inherited_fds = inherited_fds
        return RoleCompletion(
            stdout=(
                b'{"version":1,"status":"committed",' b'"committed_at":"2026-10-10T12:00:00Z"}'
            ),
            exit_status=0,
            timed_out=False,
        )


def test_runtime_launches_final_provisioning_with_only_reference_metadata_and_target_lock(
    tmp_path: pathlib.Path,
) -> None:
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_runtime_roles.py"
    assert module_path.is_file(), "the runtime role composer must exist"
    lock_path = tmp_path / "target-reference.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    launch = _CommittedChild()
    try:
        outcome = run_final_provisioning(
            request=FinalProvisioningRequest(
                target_ref="target-a",
                consumer_run_id="run-a",
                record_id=_RECORD_ID,
                value_generation=_GENERATION,
                value_ref=(
                    "op://llm-provider-manager-token-values/"
                    f"{_RECORD_ID}-{_GENERATION}/credential"
                ),
                lease_expires_at="2026-10-10T13:00:00Z",
                external_call_timeout_seconds=30,
                op_executable="/usr/bin/op",
            ),
            companion=PackagedCompanion(
                python_executable="/usr/bin/python3",
                packaged_companion="/pkg/overseer/_lpm_companion.py",
            ),
            target_lock_descriptor=descriptor,
            environ={"PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": _SECRET},
            launch=launch,
        )
    finally:
        os.close(descriptor)
    carried = json.loads(launch.request_bytes)

    assert outcome.result_object == {
        "version": 1,
        "status": "committed",
        "committed_at": "2026-10-10T12:00:00Z",
    }
    assert outcome.refusal_reason is None
    assert outcome.launched is True
    assert carried == {
        "version": 1,
        "target_ref": "target-a",
        "consumer_run_id": "run-a",
        "record_id": _RECORD_ID,
        "value_generation": _GENERATION,
        "value_ref": (
            "op://llm-provider-manager-token-values/" f"{_RECORD_ID}-{_GENERATION}/credential"
        ),
        "lease_expires_at": "2026-10-10T13:00:00Z",
        "external_call_timeout_seconds": 30,
        "op_executable": "/usr/bin/op",
    }
    assert launch.inherited_fds == (descriptor,)
    assert _SECRET not in launch.request_bytes.decode("utf-8")
    assert _SECRET not in launch.environ.values()
