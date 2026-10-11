"""Both installed launchers preserve the typed, secret-free manager wire contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

__all__: list[str] = []

_ROOT = Path(__file__).resolve().parents[1]
_SUPPORT = _ROOT / "overseer" / "test_lpm_installed_sandbox.py"
_ATTENTION_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


class _Result(Protocol):
    exit_status: int
    stdout: str
    stderr: str
    body: dict[str, object]


class _Credential(Protocol):
    record_id: str


class _Sandbox(Protocol):
    def credential_taints(self) -> tuple[str, ...]: ...

    def seed_credential(self, *, value: bytes) -> _Credential: ...

    def write_attention(self, *, record_id: str) -> str: ...

    def register_target(self, *, consumer_run_id: str) -> Path: ...

    def bind_target_lock(self, *, target_ref: str) -> None: ...

    def target_committed_at(self, *, consumer_run_id: str) -> str: ...

    def run(self, *, surface: str, arguments: tuple[str, ...], input_text: str = "") -> _Result: ...


def _support() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lpm_installed_surface_sandbox", _SUPPORT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_chain(
    *, sandbox: _Sandbox, surface: str, secret: bytes
) -> tuple[_Result, _Result, _Result, _Result]:
    credential = sandbox.seed_credential(value=secret)
    _ = sandbox.write_attention(record_id=_ATTENTION_RECORD)
    attention = sandbox.run(surface=surface, arguments=())
    run_id = f"installed-{surface}-wire-run"
    _ = sandbox.register_target(consumer_run_id=run_id)
    target = sandbox.run(
        surface=surface,
        arguments=("target", "--target-json", "-"),
        input_text=json.dumps({"version": 1, "consumer_run_id": run_id, "adapter": "isolated-run"}),
    )
    target_ref = target.body["target_ref"]
    assert isinstance(target_ref, str)
    sandbox.bind_target_lock(target_ref=target_ref)
    provision = sandbox.run(
        surface=surface,
        arguments=("provision", "--request-json", "-"),
        input_text=json.dumps(
            {
                "version": 1,
                "provider": "anthropic",
                "kind": "claude-code-oauth",
                "purpose": "factory",
                "consumer_run_id": run_id,
                "target_ref": target_ref,
                "lease_seconds": 3600,
            }
        ),
    )
    report = sandbox.run(
        surface=surface,
        arguments=("report", "--report-json", "-"),
        input_text=json.dumps(
            {
                "version": 1,
                "consumer_run_id": run_id,
                "record_id": credential.record_id,
                "occurred_at": sandbox.target_committed_at(consumer_run_id=run_id),
                "classification": "authentication",
            }
        ),
    )
    return attention, target, provision, report


def _invalid_results(*, sandbox: _Sandbox, surface: str) -> tuple[_Result, ...]:
    return tuple(
        sandbox.run(
            surface=surface,
            arguments=(command, option, "-"),
            input_text="{}",
        )
        for command, option in (
            ("target", "--target-json"),
            ("provision", "--request-json"),
            ("report", "--report-json"),
        )
    )


def _assert_wire_contract(*, results: tuple[_Result, ...], secret_markers: tuple[str, ...]) -> None:
    attention, target, provision, report, unavailable, *invalid = results
    assert [result.exit_status for result in results[:4]] == [0, 0, 0, 0]
    assert set(attention.body) == {"version", "status", "operation", "items"}
    assert set(target.body) == {"version", "status", "operation", "target_ref", "expires_at"}
    assert set(provision.body) == {"version", "status", "operation", "receipt"}
    assert set(cast("dict[str, object]", provision.body["receipt"])) == {
        "record_id",
        "account_id",
        "purpose",
        "validated_at",
        "lease_expires_at",
    }
    assert report.body == {
        "version": 1,
        "status": "ok",
        "operation": "report",
        "duplicate": False,
    }
    assert unavailable.exit_status == 4
    assert unavailable.body["error_type"] == "store-unavailable"
    assert [result.exit_status for result in invalid] == [2, 2, 2]
    assert [result.body["error_type"] for result in invalid] == [
        "invalid-request",
        "invalid-request",
        "invalid-report",
    ]
    for result in results:
        assert len(result.stdout.splitlines()) == 1
        assert result.stderr == ""
        for marker in secret_markers:
            assert marker not in result.stdout
            assert marker not in result.stderr


def test_both_installed_surfaces_keep_result_fields_statuses_and_streams_secret_free(
    tmp_path: Path,
) -> None:
    support = _support()
    probe = support.InstalledManagerSandbox.create(root=tmp_path / "probe", repository=_ROOT)
    assert hasattr(probe, "credential_taints"), "installed runs must carry credential taints"
    for surface in ("console", "plugin"):
        sandbox = cast(
            "_Sandbox",
            support.InstalledManagerSandbox.create(
                root=tmp_path / surface,
                repository=_ROOT,
            ),
        )
        unavailable = sandbox.run(surface=surface, arguments=())
        secret = f"sk-ant-oat01-{surface}-wire-secret"
        success = _valid_chain(sandbox=sandbox, surface=surface, secret=secret.encode())
        invalid = _invalid_results(sandbox=sandbox, surface=surface)
        _assert_wire_contract(
            results=(*success, unavailable, *invalid),
            secret_markers=(secret, "fixture-token-", *sandbox.credential_taints()),
        )
