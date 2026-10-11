"""Installed manager subprocesses exercise the real credential-provider boundary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import cast

__all__: list[str] = []

_ROOT = Path(__file__).resolve().parents[1]
_SUPPORT = _ROOT / "overseer" / "test_lpm_installed_sandbox.py"


def _support() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lpm_installed_sandbox", _SUPPORT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_install_exposes_console_and_absolute_plugin_executable(tmp_path: Path) -> None:
    assert _SUPPORT.is_file(), "the installed subprocess sandbox must exist"
    sandbox = _support().InstalledManagerSandbox.create(root=tmp_path, repository=_ROOT)

    assert sandbox.console_on_path() == "/opt/lpm/bin/llm-provider-manager"
    result = sandbox.run(
        surface="plugin",
        arguments=("target", "--target-json", "-"),
        input_text="{}",
    )

    assert result.executable == "/plugin/bin/llm-provider-manager"
    assert result.exit_status == 2
    assert result.body["error_type"] == "invalid-request"


def test_fresh_installed_target_and_provision_write_only_the_registered_target(
    tmp_path: Path,
) -> None:
    sandbox = _support().InstalledManagerSandbox.create(root=tmp_path, repository=_ROOT)
    assert hasattr(sandbox, "seed_credential"), "the sandbox must isolate credential services"

    selected = "sk-ant-oat01-installed-exact-ß".encode()
    credential = sandbox.seed_credential(value=selected)
    run_id = "installed-success-run"
    destination = sandbox.register_target(consumer_run_id=run_id)
    decoy = sandbox.write_decoy_target(value=b"do-not-replace")
    target = sandbox.run(
        surface="console",
        arguments=("target", "--target-json", "-"),
        input_text=json.dumps({"version": 1, "consumer_run_id": run_id, "adapter": "isolated-run"}),
    )

    assert target.exit_status == 0
    assert set(target.body) == {"version", "status", "operation", "target_ref", "expires_at"}
    assert target.body["operation"] == "target"
    target_ref = target.body["target_ref"]
    assert isinstance(target_ref, str)
    sandbox.bind_target_lock(target_ref=target_ref)
    provision = sandbox.run(
        surface="console",
        arguments=("provision", "--request-json", "-"),
        input_text=json.dumps(
            {
                "version": 1,
                "provider": "anthropic",
                "kind": "claude-code-oauth",
                "purpose": "factory",
                "consumer_run_id": run_id,
                "target_ref": target_ref,
                "strategy": "consume-first",
                "lease_seconds": 3600,
            }
        ),
    )

    assert provision.exit_status == 0
    assert set(provision.body) == {"version", "status", "operation", "receipt"}
    assert provision.body["operation"] == "provision"
    receipt = cast("dict[str, object]", provision.body["receipt"])
    assert set(receipt) == {
        "record_id",
        "account_id",
        "purpose",
        "validated_at",
        "lease_expires_at",
    }
    assert receipt["record_id"] == credential.record_id
    assert destination.read_bytes() == selected
    assert decoy.read_bytes() == b"do-not-replace"


def test_installed_report_is_durable_and_its_duplicate_repeats_no_effect(
    tmp_path: Path,
) -> None:
    sandbox = _support().InstalledManagerSandbox.create(root=tmp_path, repository=_ROOT)
    assert hasattr(sandbox, "report_snapshot"), "the sandbox must expose durable report state"

    credential = sandbox.seed_credential(value=b"sk-ant-oat01-installed-report")
    run_id = "installed-report-run"
    _ = sandbox.register_target(consumer_run_id=run_id)
    target = sandbox.run(
        surface="plugin",
        arguments=("target", "--target-json", "-"),
        input_text=json.dumps({"version": 1, "consumer_run_id": run_id, "adapter": "isolated-run"}),
    )
    target_ref = target.body["target_ref"]
    assert isinstance(target_ref, str)
    sandbox.bind_target_lock(target_ref=target_ref)
    provision = sandbox.run(
        surface="plugin",
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
    assert provision.exit_status == 0
    before = sandbox.report_snapshot(
        consumer_run_id=run_id,
        record_id=credential.record_id,
        account_id=credential.account_id,
    )
    report_object = {
        "version": 1,
        "consumer_run_id": run_id,
        "record_id": credential.record_id,
        "occurred_at": sandbox.target_committed_at(consumer_run_id=run_id),
        "classification": "authentication",
    }

    reported = sandbox.run(
        surface="plugin",
        arguments=("report", "--report-json", "-"),
        input_text=json.dumps(report_object),
    )
    after = sandbox.report_snapshot(
        consumer_run_id=run_id,
        record_id=credential.record_id,
        account_id=credential.account_id,
    )
    duplicate = sandbox.run(
        surface="plugin",
        arguments=("report", "--report-json", "-"),
        input_text=json.dumps(report_object),
    )

    assert reported.exit_status == 0
    assert reported.body == {
        "version": 1,
        "status": "ok",
        "operation": "report",
        "duplicate": False,
    }
    assert before.status == "valid"
    assert before.lease_exists is True
    assert after.status == "suspect"
    assert after.lease_exists is False
    assert after.assignment_exists is False
    assert after.tombstone_exists is True
    assert after.metadata_revisions == before.metadata_revisions + 1
    assert duplicate.exit_status == 0
    assert duplicate.body == {
        "version": 1,
        "status": "ok",
        "operation": "report",
        "duplicate": True,
    }
    assert (
        sandbox.report_snapshot(
            consumer_run_id=run_id,
            record_id=credential.record_id,
            account_id=credential.account_id,
        )
        == after
    )
