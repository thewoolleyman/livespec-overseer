"""Browser profiles and verification attention retain authority only to the deadline."""

from __future__ import annotations

import importlib
import json
import os
import stat
from pathlib import Path

from overseer._vendor.returns.result import Failure, Success


def _assert_profile(*, profile_module, tmp_path):
    state = tmp_path / "state"
    profiles = state / "browser-profiles"
    profiles.mkdir(parents=True, mode=0o700)
    result = profile_module.account_profile(
        state_dir=state,
        provider="anthropic",
        account_id="account-1",
        owner_uid=os.geteuid(),
    )
    profile = result.unwrap()
    assert profile.parent == profiles
    assert stat.S_IMODE(profile.stat().st_mode) == 0o700
    argv = profile_module.chrome_arguments(
        chrome_executable="/usr/bin/google-chrome", profile=profile
    )
    assert argv[0] == "/usr/bin/google-chrome"
    assert f"--user-data-dir={profile}" in argv
    assert "--remote-debugging-pipe" in argv
    assert not any("headless" in argument or "extension" in argument for argument in argv)

    unsafe = profiles / "unsafe"
    unsafe.symlink_to(profile, target_is_directory=True)
    refused = profile_module.validate_profile(profile=unsafe, owner_uid=os.geteuid())
    assert isinstance(refused, Failure)
    assert unsafe.is_symlink()


def _resolve(*, attention, status, now):
    captures = [bytearray(b"synthetic-capture")]
    events: list[object] = []
    session = attention.AttentionSession(
        profile_ref="profile:opaque",
        remaining_steps=11,
        deadline=100.0,
        captures=captures,
    )
    outcome = attention.resolve_attention(
        session=session,
        status=status,
        now=now,
        remove_artifact=lambda: events.append("removed"),
        transition_failed=lambda reason: events.append(("failed", reason)),
    )
    return outcome, captures, events


def _assert_attention(*, attention):
    assert (
        attention.attention_deadline(raised_at=90.0, wait_seconds=20, worker_deadline=100.0)
        == 100.0
    )
    resumed = _resolve(attention=attention, status="resolved", now=99.0)
    assert resumed[0].action == "resume"
    assert resumed[0].profile_ref == "profile:opaque"
    assert resumed[0].remaining_steps == 11
    assert resumed[1][0] == bytearray(b"synthetic-capture")
    assert resumed[2] == ["removed"]

    for status, now in (("give-up", 99.0), ("pending", 100.0)):
        failed = _resolve(attention=attention, status=status, now=now)
        assert failed[0].action == "failed"
        assert failed[0].profile_ref is None
        assert failed[0].remaining_steps == 0
        assert failed[1] == [bytearray()]
        assert failed[2] == ["removed", ("failed", "flow-unavailable")]


def _assert_acquire_entrypoint(*, tmp_path):
    argv = importlib.import_module("_lpm_manager_argv")
    runtime_module = importlib.import_module("_lpm_runtime")
    commands = importlib.import_module("_lpm_commands")
    parsed = argv.manager_invocation(arguments=("acquire", "--acquisition-json", "-")).unwrap()
    runtime = runtime_module.ConcreteManagerRuntime(
        state_dir=tmp_path / "runtime",
        owner_uid=os.geteuid(),
        config=importlib.import_module("_lpm_config").default_config(),
        read_input=lambda: json.dumps(
            {
                "version": 1,
                "provider": "anthropic",
                "account_id": "account-1",
                "kind": "claude-code-oauth",
                "purpose": "factory",
            }
        ),
        acquisition=lambda *, request: Success(
            {"operation": "acquire", "credential_status": "acquiring", **request}
        ),
    )
    outcome = runtime.run(invocation=commands.ManagerInvocation(command=parsed.command, source="-"))
    assert outcome.exit_status == 0
    assert outcome.body["credential_status"] == "acquiring"


def test_attention_profile_and_acquire_entrypoint_fail_closed_at_deadline(tmp_path):
    root = Path(__file__).parents[1] / "overseer"
    assert (root / "_lpm_browser_profile.py").is_file()
    assert (root / "_lpm_acquisition_attention.py").is_file()
    profile = importlib.import_module("_lpm_browser_profile")
    attention = importlib.import_module("_lpm_acquisition_attention")

    _assert_profile(profile_module=profile, tmp_path=tmp_path)
    _assert_attention(attention=attention)
    _assert_acquire_entrypoint(tmp_path=tmp_path)
