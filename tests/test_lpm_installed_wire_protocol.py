"""Both installed manager surfaces emit one typed, credential-free JSON result."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import replace
from importlib.machinery import ModuleSpec
from pathlib import Path

import pytest

from overseer.llm_provider_manager import subprocess_launch
from overseer.runtime_prefix import ensure_runtime

__all__: list[str] = []

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE = _ROOT / "overseer"
_PLUGIN = _ROOT / ".claude-plugin" / "bin" / "llm-provider-manager"
_SECRET = "sk-ant-oat0-runtime-output-must-not-contain-this"


@pytest.fixture(scope="module")
def installed_console(*, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Install the distribution into a clean environment and return its console script."""
    if shutil.which("uv") is None:
        pytest.skip("uv is required for the installed-distribution integration test")
    prefix = tmp_path_factory.mktemp("lpm-installed")
    assert ensure_runtime(prefix=prefix, install_source=str(_ROOT)) is not None
    return prefix / "venv" / "bin" / "llm-provider-manager"


def _run(*, launcher: Path, arguments: tuple[str, ...], input_text: str = "") -> dict[str, object]:
    completed = subprocess_launch(
        executable=launcher,
        argv=arguments,
        stdin_bytes=None if input_text == "" else input_text.encode("utf-8"),
    )
    assert completed.stderr == ""
    assert completed.stdout.count("\n") == 1
    assert _SECRET not in completed.stdout
    return {
        "status": completed.exit_status,
        "body": json.loads(completed.stdout),
    }


def test_both_installed_executables_emit_the_exact_secret_free_wire_result(
    *, installed_console: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (_PACKAGE / "_lpm_companion.py").is_file()
    monkeypatch.setenv("ANTHROPIC_API_KEY", _SECRET)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", _SECRET)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    cases = (
        ((), "", 0, None),
        (("target", "--target-json", "-"), "{}", 2, "invalid-request"),
        (("provision", "--request-json", "-"), "{}", 2, "invalid-request"),
        (("report", "--report-json", "-"), "{}", 2, "invalid-report"),
    )
    for launcher in (installed_console, _PLUGIN):
        for arguments, payload, status, error_type in cases:
            ran = _run(launcher=launcher, arguments=arguments, input_text=payload)
            body = ran["body"]
            assert ran["status"] == status
            assert isinstance(body, dict)
            assert body["version"] == 1
            if error_type is None:
                assert body == {
                    "version": 1,
                    "status": "ok",
                    "operation": "attention",
                    "items": [],
                }
            else:
                assert set(body) == {"version", "status", "error_type", "message"}
                assert body["error_type"] == error_type


def test_argument_and_input_wire_helpers_cover_the_closed_grammar(tmp_path: Path) -> None:
    from _lpm_manager_argv import manager_invocation
    from _lpm_results import invalid_request
    from _lpm_wire import error_outcome, read_command_object, render_outcome, success_outcome

    accepted = manager_invocation(arguments=())
    assert accepted.unwrap().command == "attention"
    assert manager_invocation(arguments=("attention",)).unwrap().source is None
    target = manager_invocation(arguments=("target", "--target-json", "-"))
    assert target.unwrap().source == "-"
    invalid_vectors = (
        ("attention", "extra"),
        ("unknown",),
        ("target", "--wrong", "-"),
        ("target", "--target-json", ""),
        ("report", "--report-json"),
    )
    refused = [manager_invocation(arguments=vector) for vector in invalid_vectors]
    assert [item.failure().error_type for item in refused] == [
        "invalid-request",
        "invalid-request",
        "invalid-request",
        "invalid-request",
        "invalid-report",
    ]
    request = tmp_path / "request.json"
    request.write_text('{"version":1}', encoding="utf-8")
    for source, reader in (("-", lambda: '{"version":1}'), (str(request), lambda: "unused")):
        assert read_command_object(
            source=source, read_input=reader, refuse=invalid_request
        ).unwrap() == {"version": 1}
    for source, reader in (
        (str(tmp_path / "missing"), lambda: "unused"),
        ("-", lambda: "[]"),
    ):
        assert (
            read_command_object(source=source, read_input=reader, refuse=invalid_request)
            .failure()
            .error_type
            == "invalid-request"
        )
    success = success_outcome(payload={"operation": "attention", "items": []})
    assert success.exit_status == 0
    assert render_outcome(outcome=success).startswith('{"version":1,"status":"ok"')
    assert error_outcome(error=invalid_request(message="bad")).exit_status == 2


def test_companion_refuses_an_unloadable_product_without_leaking(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_companion

    assert _lpm_companion.package_root() == _PACKAGE
    assert _lpm_companion.load_product_package(root=tmp_path) is None
    assert _lpm_companion.run(arguments=(), root=tmp_path) == 70
    assert capsys.readouterr().out == f"{_lpm_companion.INTERNAL_BUG_LINE}\n"
    monkeypatch.setattr(_lpm_companion, "package_root", lambda: tmp_path)
    monkeypatch.setattr(_lpm_companion.sys, "argv", ["companion"])
    assert _lpm_companion.main() == 70


def test_companion_loads_and_dispatches_only_the_adjacent_product(
    *, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_companion

    original = sys.modules["overseer"]
    with monkeypatch.context() as context:
        context.setitem(sys.modules, "overseer", original)
        loaded = _lpm_companion.load_product_package(root=_PACKAGE)
        assert loaded is not None
        assert _lpm_companion.run(arguments=(), root=_PACKAGE) == 0
    assert json.loads(capsys.readouterr().out) == {
        "version": 1,
        "status": "ok",
        "operation": "attention",
        "items": [],
    }
    assert _lpm_companion.run(arguments=("unknown",), root=_PACKAGE) == 2
    assert json.loads(capsys.readouterr().out)["error_type"] == "invalid-request"
    import _lpm_runtime
    from _lpm_results import store_unavailable

    from overseer._vendor.returns.result import Failure

    monkeypatch.setattr(
        _lpm_runtime,
        "runtime_for_host",
        lambda: Failure(store_unavailable(message="host unavailable")),
    )
    assert _lpm_companion.run(arguments=(), root=_PACKAGE) == 4
    assert json.loads(capsys.readouterr().out)["error_type"] == "store-unavailable"
    with monkeypatch.context() as context:
        context.setattr(
            _lpm_companion.importlib.util, "spec_from_file_location", lambda *_a, **_k: None
        )
        assert _lpm_companion.load_product_package(root=_PACKAGE) is None
        context.setattr(
            _lpm_companion.importlib.util,
            "spec_from_file_location",
            lambda *_a, **_k: ModuleSpec("overseer", loader=None),
        )
        assert _lpm_companion.load_product_package(root=_PACKAGE) is None


def test_runtime_types_every_pre_operation_refusal(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_runtime
    from _lpm_attention import AttentionItem
    from _lpm_commands import ManagerInvocation
    from _lpm_config import default_config
    from _lpm_results import store_unavailable

    from overseer._vendor.returns.result import Failure, Success

    runtime = _lpm_runtime.ConcreteManagerRuntime(
        state_dir=tmp_path,
        owner_uid=os.getuid(),
        config=default_config(),
        read_input=lambda: "{}",
    )
    assert runtime.run(invocation=ManagerInvocation(command="attention", source=None)).body == {
        "version": 1,
        "status": "ok",
        "operation": "attention",
        "items": [],
    }
    for command, error_type in (
        ("target", "invalid-request"),
        ("provision", "invalid-request"),
        ("report", "invalid-report"),
    ):
        assert (
            runtime.run(invocation=ManagerInvocation(command=command, source="-")).body[
                "error_type"
            ]
            == error_type
        )
    malformed = replace(runtime, read_input=lambda: "[]")
    assert (
        malformed.run(invocation=ManagerInvocation(command="target", source="-")).body["error_type"]
        == "invalid-request"
    )
    assert (
        runtime.run(invocation=ManagerInvocation(command="target", source=None)).body["error_type"]
        == "internal-bug"
    )
    monkeypatch.setattr(
        _lpm_runtime,
        "attention_items",
        lambda **_kwargs: Failure(store_unavailable(message="unreadable")),
    )
    assert (
        runtime.run(invocation=ManagerInvocation(command="attention", source=None)).exit_status == 4
    )
    monkeypatch.setattr(
        _lpm_runtime,
        "attention_items",
        lambda **_kwargs: Success(
            (
                AttentionItem(
                    path="/attention/a.json",
                    record_id="record-a",
                    provider="anthropic",
                    account_id="account-a",
                    reason="renew",
                    deadline="2026-10-11T00:00:00Z",
                ),
            )
        ),
    )
    listed = runtime.run(invocation=ManagerInvocation(command="attention", source=None))
    assert listed.body["items"] == [
        {
            "path": "/attention/a.json",
            "record_id": "record-a",
            "provider": "anthropic",
            "account_id": "account-a",
            "reason": "renew",
            "deadline": "2026-10-11T00:00:00Z",
        }
    ]


def test_valid_object_commands_cannot_fall_back_to_the_hermetic_runtime_backend(
    *, tmp_path: Path
) -> None:
    import _lpm_runtime
    from _lpm_commands import ManagerInvocation
    from _lpm_config import default_config

    runtime = _lpm_runtime.ConcreteManagerRuntime(
        state_dir=tmp_path,
        owner_uid=os.getuid(),
        config=default_config(),
        read_input=lambda: json.dumps(
            {
                "version": 1,
                "consumer_run_id": "installed-valid-command",
                "adapter": "isolated-run",
            }
        ),
    )

    outcome = runtime.run(invocation=ManagerInvocation(command="target", source="-"))

    assert outcome.body.get("error_type") == "internal-bug"


def test_host_runtime_resolution_is_typed(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import _lpm_runtime
    from _lpm_results import store_unavailable

    from overseer._vendor.returns.result import Failure

    monkeypatch.setattr(_lpm_runtime, "account_database_home", lambda **_kwargs: None)
    assert _lpm_runtime.runtime_for_host().failure().error_type == "store-unavailable"
    monkeypatch.setattr(_lpm_runtime, "account_database_home", lambda **_kwargs: tmp_path)
    monkeypatch.setattr(
        _lpm_runtime,
        "load_manager_config",
        lambda **_kwargs: Failure(store_unavailable(message="config unavailable")),
    )
    assert _lpm_runtime.runtime_for_host().failure().message == "config unavailable"
    from _lpm_config import default_config

    from overseer._vendor.returns.result import Success

    monkeypatch.setattr(
        _lpm_runtime, "load_manager_config", lambda **_kwargs: Success(default_config())
    )
    assert _lpm_runtime.runtime_for_host().unwrap().state_dir.name == "llm-provider-manager"
