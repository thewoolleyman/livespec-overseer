"""Integration coverage for pushing in-memory deliveries to listed hosts over ssh."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOKEN = "tok-" + "secret-a"
_REAL_REPLACE = os.replace


def _write(*, path: Path, body: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(body), encoding="utf-8")


def _live(*, home: Path, token: str, account: str, expires: int = 9_999_999_999_000) -> None:
    _write(
        path=home / ".claude/.credentials.json",
        body={"claudeAiOauth": {"accessToken": token, "expiresAt": expires, "refreshToken": "r"}},
    )
    _write(
        path=home / ".claude.json", body={"oauthAccount": {"accountUuid": account}, "userID": "u"}
    )


def _apply(
    *,
    home: Path,
    payload: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    """Run the exact program the push sends, as the host's python3 would."""
    push = importlib.import_module("caam_delivery_push")
    monkeypatch.setenv("HOME", str(home))
    code = 0
    try:
        program = push.apply_program(payload=payload)
        exec(compile(program, "<apply>", "exec"), {"__name__": "__main__"})  # noqa: S102
    except SystemExit as stop:
        code = int(stop.code or 0)
    return code, capsys.readouterr().out.strip()


def _delivery(*, sequence: int, oauth: dict[str, object] | None = None) -> str:
    return json.dumps(
        {
            "sequence": sequence,
            "account_id": "a",
            "identity": {"oauthAccount": {"accountUuid": "a"}, "userID": "u", "extra": 1},
            "oauth": oauth or {"accessToken": f"t{sequence}", "expiresAt": 1},
        }
    )


def _flaky_replace(*, monkeypatch: pytest.MonkeyPatch, failing: set[int]) -> None:
    """Make the numbered calls to os.replace raise, counting from 1."""
    calls = {"n": 0}

    def flaky(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] in failing:
            raise OSError("disk full")
        _REAL_REPLACE(src, dst)

    monkeypatch.setattr(os, "replace", flaky)


def _read(*, path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_apply_step_result_lines_carry_the_sequence_and_change_only_owned_keys(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    host = tmp_path / "host"
    _write(path=host / ".claude/.credentials.json", body={"mcpOAuth": {"k": 1}})
    _write(path=host / ".claude.json", body={"theme": "dark"})
    io_kwargs = {"monkeypatch": monkeypatch, "capsys": capsys}

    assert _apply(home=host, payload=_delivery(sequence=2), **io_kwargs) == (0, "applied 2")
    creds = host / ".claude/.credentials.json"
    assert _read(path=creds) == {
        "mcpOAuth": {"k": 1},
        "claudeAiOauth": {"accessToken": "t2", "expiresAt": 1},
    }
    assert _read(path=host / ".claude.json") == {
        "theme": "dark",
        "oauthAccount": {"accountUuid": "a"},
        "userID": "u",
    }
    applied = host / ".claude/.caam-delivery-sequence"
    assert applied.read_text(encoding="utf-8") == "2"
    for path in (creds, host / ".claude.json", applied):
        assert path.stat().st_mode & 0o777 == 0o600
    assert _apply(home=host, payload=_delivery(sequence=2), **io_kwargs) == (
        0,
        "stale-sequence 2 host-applied 2",
    )
    assert _apply(home=host, payload=_delivery(sequence=1), **io_kwargs) == (
        0,
        "stale-sequence 1 host-applied 2",
    )
    leaky = _delivery(sequence=3, oauth={"accessToken": "t3", "refreshToken": "x"})
    assert _apply(home=host, payload=leaky, **io_kwargs) == (4, "failed 3 delivered-refresh-token")
    assert _apply(home=host, payload="not json", **io_kwargs) == (5, "failed - bad-delivery")
    shapeless = json.dumps({"sequence": 4, "identity": "x", "oauth": {}})
    assert _apply(home=host, payload=shapeless, **io_kwargs) == (5, "failed - bad-delivery")

    own = tmp_path / "own"
    _write(path=own / ".claude/.credentials.json", body={"claudeAiOauth": {"refreshToken": "m"}})
    assert _apply(home=own, payload=_delivery(sequence=1), **io_kwargs) == (3, "not-converted 1")

    corrupt = tmp_path / "corrupt"
    (corrupt / ".claude").mkdir(parents=True)
    _ = (corrupt / ".claude/.credentials.json").write_text("{", encoding="utf-8")
    assert _apply(home=corrupt, payload=_delivery(sequence=1), **io_kwargs) == (
        5,
        "failed 1 JSONDecodeError",
    )
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    _ = (blocked / ".claude").write_text("a file, not a directory", encoding="utf-8")
    assert _apply(home=blocked, payload=_delivery(sequence=1), **io_kwargs) == (
        5,
        "failed 1 FileExistsError",
    )


def test_apply_step_rolls_back_both_files_and_reports_each_failed_restore(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    io_kwargs = {"monkeypatch": monkeypatch, "capsys": capsys}

    def seeded(name: str) -> Path:
        home = tmp_path / name
        _write(path=home / ".claude/.credentials.json", body={"keep": 1})
        _write(path=home / ".claude.json", body={"keep": 2})
        return home

    def untouched(home: Path) -> bool:
        return (
            _read(path=home / ".claude/.credentials.json") == {"keep": 1}
            and _read(path=home / ".claude.json") == {"keep": 2}
            and not (home / ".claude/.caam-delivery-sequence").exists()
            and not [p for p in (home / ".claude").iterdir() if p.name.startswith("tmp")]
        )

    second = seeded("second-write")
    _flaky_replace(monkeypatch=monkeypatch, failing={2})
    reply = _apply(home=second, payload=_delivery(sequence=1), **io_kwargs)
    assert reply == (5, "failed 1 rolled-back OSError")
    assert untouched(second)

    sequence_write = seeded("sequence-write")
    _flaky_replace(monkeypatch=monkeypatch, failing={3})
    reply = _apply(home=sequence_write, payload=_delivery(sequence=1), **io_kwargs)
    assert reply == (5, "failed 1 rolled-back OSError")
    assert untouched(sequence_write)

    one_restore = seeded("one-restore")
    _flaky_replace(monkeypatch=monkeypatch, failing={2, 3})
    reply = _apply(home=one_restore, payload=_delivery(sequence=1), **io_kwargs)
    assert reply == (5, "failed 1 OSError; unrestored credential")
    assert _read(path=one_restore / ".claude.json") == {"keep": 2}

    both = seeded("both-restores")
    _flaky_replace(monkeypatch=monkeypatch, failing={2, 3, 4})
    reply = _apply(home=both, payload=_delivery(sequence=1), **io_kwargs)
    assert reply == (5, "failed 1 OSError; unrestored credential,global-state")

    fresh = tmp_path / "fresh"
    _flaky_replace(monkeypatch=monkeypatch, failing={2})
    reply = _apply(home=fresh, payload=_delivery(sequence=1), **io_kwargs)
    assert reply == (5, "failed 1 rolled-back OSError")
    assert not (fresh / ".claude/.credentials.json").exists()
    assert not (fresh / ".claude.json").exists()


def test_push_records_each_host_and_status_shows_spec_states(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    status = importlib.import_module("caam_delivery_push_status")
    assert push.HOSTS_FILE.startswith(".local/state/caam-usage-rotate/")
    assert push.KNOWN_HOSTS.startswith(".local/state/caam-usage-rotate/")
    _live(home=tmp_path, token=TOKEN, account="acct-a")
    (tmp_path / push.HOSTS_FILE).parent.mkdir(parents=True)
    _ = (tmp_path / push.HOSTS_FILE).write_text(
        "good u@good linux\nkey u@key linux\nnc u@nc linux\nmac u@mac macos\n"
        "bad -oProxyCommand=x linux\nalias good2 linux\njunk\n# comment\n\n",
        encoding="utf-8",
    )
    sent: list[str] = []
    replies = {
        "u@good": "applied 1",
        "u@key": "failed host-key-verification",
        "u@nc": "not-converted 1",
        "u@mac": "queued 1",
    }
    macos = importlib.import_module("caam_delivery_macos")

    def fake_run(
        *, target: str, program: str, key: str, known_hosts: str, timeout: float
    ) -> tuple[int, str]:
        assert key.endswith("id_ed25519") and timeout > 0
        assert known_hosts == str(tmp_path / push.KNOWN_HOSTS)
        is_apply = program.startswith(push.APPLY_SCRIPT)
        is_inbox = program.startswith(macos.INBOX_PROGRAM)
        delivered = program[len(push.APPLY_SCRIPT) :] if is_apply else ""
        assert "refreshToken" not in delivered
        assert not is_inbox or "refreshToken" not in program
        sent.append(target if is_apply else ("inbox:" + target if is_inbox else "rc:" + target))
        return 0, replies.get(target, '{"reissued": []}')

    loop = entry.PushLoop()
    run = {"confirm": lambda **_: "acct-a", "run": fake_run, "reissue": "RC"}
    entry.run_once(home=tmp_path, now=100.0, loop=loop, **run)
    assert sorted(sent) == ["inbox:u@mac", "rc:u@good", "u@good", "u@key", "u@nc"]
    err = capsys.readouterr().err
    assert "host list line 5 rejected" in err and "host list line 6 rejected" in err

    sent.clear()
    entry.run_once(home=tmp_path, now=110.0, loop=loop, **run)
    entry.run_once(home=tmp_path, now=150.0, loop=loop, **run)
    assert sent == []
    entry.run_once(home=tmp_path, now=161.0, loop=loop, **run)
    assert sorted(sent) == ["inbox:u@mac", "u@key"]

    sent.clear()
    replies["u@good"] = "failed 2 weird " + "tok-" + "secret-b"
    _live(home=tmp_path, token="tok-" + "secret-b", account="acct-a")
    entry.run_once(home=tmp_path, now=170.0, loop=loop, **run)
    assert sorted(sent) == ["inbox:u@mac", "u@good", "u@key"]
    saved = (tmp_path / push.PUSH_STATE).read_text(encoding="utf-8")
    assert "secret" not in saved and "[redacted]" in saved

    lines = status.status_lines(home=tmp_path, now=180.0, reissue_available=False)
    text = "\n".join(lines)
    assert "secret" not in text
    assert (
        "good  u@good  linux  lagging  account acct-a profile -  sequence 1 applied"
        " 1970-01-01T00:01:40Z  last-success 1970-01-01T00:01:40Z"
        "  last-error failed 2 weird [redacted] at 1970-01-01T00:02:50Z"
    ) in text
    assert (
        "key  u@key  linux  stale  account - profile -  sequence - applied never"
        "  last-success never  last-error failed host-key-verification at 1970-01-01T00:02:50Z"
    ) in text
    assert "nc  u@nc  linux  not-converted  " in text
    assert "mac  u@mac  macos  stale  " in text and "unsupported-platform" not in text
    assert "remote-control: re-issue unavailable" in text
    assert entry.run_once(home=tmp_path, now=1_100.0, loop=loop, **run) is None
    assert "u@nc" in sent


def test_push_treats_a_host_already_holding_the_sequence_as_reached(*, tmp_path: Path) -> None:
    push = importlib.import_module("caam_delivery_push")
    service = importlib.import_module("caam_delivery_service")
    delivery = service.Delivery(
        sequence=3, account_id="acct-a", identity={}, oauth={"accessToken": TOKEN, "expiresAt": 9}
    )
    (tmp_path / push.HOSTS_FILE).parent.mkdir(parents=True)
    _ = (tmp_path / push.HOSTS_FILE).write_text(
        "same u@same linux\nahead u@ahead linux\n", encoding="utf-8"
    )
    replies = {
        "u@same": "stale-sequence 3 host-applied 3",
        "u@ahead": "stale-sequence 3 host-applied 7",
    }

    def fake_run(*, target: str, **_: object) -> tuple[int, str]:
        return 0, replies[target]

    outcomes = push.push_due(home=tmp_path, delivery=delivery, now=50.0, run=fake_run)
    assert outcomes == {"same": replies["u@same"], "ahead": replies["u@ahead"]}
    state = push.load_state(home=tmp_path)
    assert state["same"]["sequence"] == 3 and state["same"]["account_id"] == "acct-a"
    assert state["same"]["last_success"] == 50.0
    assert state["ahead"]["last_error"] == "stale-sequence 3 host-applied 7"
    assert state["ahead"]["last_error_at"] == 50.0
    assert "last_success" not in state["ahead"]


def test_push_state_write_failure_is_logged_and_the_pass_continues(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    service = importlib.import_module("caam_delivery_service")
    delivery = service.Delivery(sequence=1, account_id="a", identity={}, oauth={})
    (tmp_path / push.HOSTS_FILE).parent.mkdir(parents=True)
    _ = (tmp_path / push.HOSTS_FILE).write_text("h u@h linux\n", encoding="utf-8")

    def refuse(**_: object) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(service, "write_private_json", refuse)
    outcomes = push.push_due(
        home=tmp_path, delivery=delivery, now=1.0, run=lambda **_: (0, "applied 1")
    )
    assert outcomes == {"h": "applied 1"}
    assert "FAIL push state not written: PermissionError" in capsys.readouterr().err


def test_status_states_profiles_divergence_and_expiry(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path
) -> None:
    status = importlib.import_module("caam_delivery_push_status")
    state = status.host_state
    fresh = {"state": "ok", "sequence": 1, "last_success": 100.0}
    assert state(entry=fresh, current_sequence=1, now=110.0, stale_after=900.0) == "current"
    assert state(entry=fresh, current_sequence=2, now=110.0, stale_after=900.0) == "lagging"
    assert state(entry=fresh, current_sequence=1, now=5_000.0, stale_after=900.0) == "stale"
    assert state(entry={}, current_sequence=1, now=1.0, stale_after=900.0) == "stale"
    failed = {"state": "failed", "last_error": "failed timeout"}
    assert state(entry=failed, current_sequence=1, now=1.0, stale_after=900.0) == "stale"
    expired = {**fresh, "expires_at": 50_000}
    assert state(entry=expired, current_sequence=1, now=110.0, stale_after=900.0) == "expired"
    held = {**expired, "state": "not-converted"}
    assert state(entry=held, current_sequence=1, now=110.0, stale_after=900.0) == "not-converted"

    _live(home=tmp_path, token=TOKEN, account="acct-live", expires=1_000)
    assert "role holder live account: acct-live profile -" in status.status_lines(
        home=tmp_path, now=10.0, reissue_available=True
    )
    vault = tmp_path / ".local/share/caam/vault/claude"
    _write(path=vault / "_backup/.claude.json", body={})
    _write(path=vault / "anthropic-1/.claude.json", body={"oauthAccount": {"accountUuid": "x"}})
    _write(
        path=vault / "anthropic-2/.claude.json", body={"oauthAccount": {"accountUuid": "acct-live"}}
    )
    selection = tmp_path / ".local/state/caam-usage-rotate/selected-account.json"
    _write(path=selection, body={"account_uuid": "x", "profile": "anthropic-1", "written_at": 1})
    hosts = tmp_path / ".local/state/caam-usage-rotate/delivery-hosts"
    _ = hosts.write_text("h u@h linux\n", encoding="utf-8")
    _write(
        path=tmp_path / ".local/state/caam-usage-rotate/delivery-push.json",
        body={"h": {"account_id": "acct-live", "sequence": 1, "applied_at": 5.0}},
    )
    lines = status.status_lines(home=tmp_path, now=10.0, reissue_available=True)
    assert "role holder live account: acct-live profile anthropic-2" in lines
    assert "caam selected account: x profile anthropic-1" in lines
    assert any(line.startswith("diverged") for line in lines)
    assert any(line.startswith("expired") for line in lines)
    assert not any(line.startswith("remote-control") for line in lines)
    row = "account acct-live profile anthropic-2  sequence 1 applied"
    assert any(row in line for line in lines)
    _write(path=selection, body={"account_uuid": "acct-live", "profile": "anthropic-2"})
    _ = (vault / "anthropic-1/.claude.json").unlink()
    _ = vault.joinpath("anthropic-1").rmdir()
    lines = status.status_lines(home=tmp_path, now=10.0, reissue_available=True)
    assert not any(line.startswith("diverged") for line in lines)
    assert "caam selected account: acct-live profile anthropic-2" in lines

    other = tmp_path / "other"
    _live(home=other, token=TOKEN, account="acct-z")
    _write(path=other / ".local/share/caam/vault/claude/p/.claude.json", body={})
    assert "role holder live account: acct-z profile -" in status.status_lines(
        home=other, now=10.0, reissue_available=True
    )


def test_ssh_runner_pins_host_keys_to_the_record_and_sends_the_program_on_stdin(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    push = importlib.import_module("caam_delivery_push")
    record = tmp_path / "known_hosts"
    _ = record.write_text("good ssh-ed25519 AAAA\n", encoding="utf-8")
    outcomes: dict[str, object] = {
        "ok": subprocess.CompletedProcess([], 0, stdout="x\napplied 3\n", stderr=""),
        "hostkey": subprocess.CompletedProcess(
            [], 255, stdout="", stderr="Host key verification failed.\n"
        ),
        "exit": subprocess.CompletedProcess([], 255, stdout="", stderr="Connection refused"),
        "silent": subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        "slow": subprocess.TimeoutExpired(cmd="ssh", timeout=1),
        "gone": FileNotFoundError("no ssh"),
    }
    program = "print('applied 3')  # PROGRAM"

    def fake_subprocess(argv: list[str], **kwargs: object) -> object:
        assert argv[:15] == [
            "/usr/bin/ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={record}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-i",
            str(Path("~/k").expanduser()),
            "-o",
            "IdentitiesOnly=yes",
        ]
        assert argv[15] == "--" and argv[17:] == ["python3 -"]
        assert kwargs["input"] == program and not any("PROGRAM" in arg for arg in argv)
        result = outcomes[argv[16]]
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(push.subprocess, "run", fake_subprocess)

    def ssh(target: str, known_hosts: Path = record) -> tuple[int, str]:
        return push.run_ssh(
            target=target, program=program, key="~/k", known_hosts=str(known_hosts), timeout=1.0
        )

    assert ssh("ok") == (0, "applied 3")
    assert ssh("hostkey") == (255, "failed host-key-verification")
    assert ssh("exit") == (255, "failed ssh-exit 255")
    assert ssh("silent") == (0, "failed no-reply")
    assert ssh("slow") == (124, "failed timeout")
    assert ssh("gone") == (255, "failed ssh-unavailable FileNotFoundError")
    assert ssh("ok", known_hosts=tmp_path / "absent") == (255, "failed no-known-hosts-record")


def test_entry_seams_and_main(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    probe = "t"
    # The provider's real profile body nests the identifier as `account.uuid`
    # (measured on the role holder 2026-11-13, overseer-4ji2n4); a top-level
    # `account_uuid` is not part of it and must not confirm anything.
    profile = {
        "account": {"uuid": "acct", "has_claude_max": True},
        "organization": {"uuid": "org", "rate_limit_tier": "default_claude_max_20x"},
    }
    monkeypatch.setattr(entry, "get_json", lambda **_: (profile, None))
    assert entry.confirm_live_account(access_token=probe) == "acct"
    monkeypatch.setattr(entry, "get_json", lambda **_: ({"account_uuid": "acct"}, None))
    assert entry.confirm_live_account(access_token=probe) is None
    monkeypatch.setattr(entry, "get_json", lambda **_: ({"account": "acct"}, None))
    assert entry.confirm_live_account(access_token=probe) is None
    monkeypatch.setattr(entry, "get_json", lambda **_: (None, "HTTP 401 for t"))
    assert entry.confirm_live_account(access_token=probe) is None
    assert "[redacted]" in capsys.readouterr().err
    monkeypatch.setattr(entry, "get_json", lambda **_: ({}, None))
    assert entry.confirm_live_account(access_token=probe) is None

    results: list[object] = [
        subprocess.CompletedProcess([], 0, stdout='{"reissued": ["%1"]}\n', stderr=""),
        subprocess.CompletedProcess([], 1, stdout="", stderr=""),
        subprocess.TimeoutExpired(cmd="python", timeout=1),
    ]

    def fake_subprocess(argv: list[str], **kwargs: object) -> object:
        assert argv == [sys.executable, "-"] and kwargs["input"] == "print(1)"
        result = results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(entry.subprocess, "run", fake_subprocess)
    assert entry.run_local(script="print(1)") == '{"reissued": ["%1"]}'
    assert entry.run_local(script="print(1)") == "failed exit 1"
    assert entry.run_local(script="print(1)") == "failed TimeoutExpired"

    script = tmp_path / "remote_control_reissue.py"
    assert push.reissue_script(path=script) is None
    _ = script.write_text("print(1)", encoding="utf-8")
    assert push.reissue_script(path=script) == "print(1)"
    assert push.load_hosts(home=tmp_path) == []

    loop = entry.PushLoop()
    entry.run_once(home=tmp_path, now=1.0, loop=loop)
    _write(path=tmp_path / ".claude/.credentials.json", body={"claudeAiOauth": {}})
    entry.run_once(home=tmp_path, now=1.0, loop=loop)
    assert loop.last is None

    switched: list[str] = []
    _live(home=tmp_path, token="tok-" + "x1", account="acct-1")
    entry.run_once(home=tmp_path, now=2.0, loop=loop, confirm=lambda **_: "acct-1")
    _live(home=tmp_path, token="tok-" + "x2", account="acct-2")
    entry.run_once(home=tmp_path, now=3.0, loop=loop, confirm=lambda **_: "acct-2")
    _live(home=tmp_path, token="tok-" + "x3", account="acct-3")
    entry.run_once(
        home=tmp_path,
        now=4.0,
        loop=loop,
        confirm=lambda **_: "acct-3",
        reissue="RC",
        local=lambda **kw: switched.append(kw["script"]) or "ok",
    )
    assert switched == ["RC"]
    assert "remote-control role holder: re-issue unavailable" in capsys.readouterr().out

    _live(home=tmp_path, token="tok-" + "x4", account="acct-4")
    entry.run_once(home=tmp_path, now=5.0, loop=loop, confirm=lambda **_: "someone-else")
    assert loop.last is not None and loop.last.account_id == "acct-3"
    host = push.Host(label="h", target="u@h", platform="linux")
    unavailable = push._reissue(
        host=host, script=None, run=None, settings=push.load_config(home=tmp_path), home=tmp_path
    )
    assert unavailable == "re-issue unavailable"

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["caam-delivery-push", "status"])
    assert entry.main() == 0
    monkeypatch.setattr(entry, "run_once", lambda **_: None)
    assert entry.main(argv=["run"], sleep=lambda _: None, passes=1) == 0

    _write(path=tmp_path / push.CONFIG_FILE, body={"retry_s": "soon"})
    assert push.load_config(home=tmp_path)["retry_s"] == "soon"
    entry_state = {"last_attempt": 1.0, "attempt_sequence": 1}
    settings = push.load_config(home=tmp_path)
    assert not push._due(entry=entry_state, sequence=1, now=40.0, settings=settings)
    assert push._due(entry=entry_state, sequence=1, now=61.0, settings=settings)


def test_a_failed_confirmation_is_retried_each_retry_interval_and_a_mismatch_waits(
    *, tmp_path: Path
) -> None:
    """A FAILED confirmation is retried; a MISMATCHED one waits for the next change.

    Measured at deploy 2026-11-13 (overseer-4ji2n4): the first confirmation
    timed out, and because the pass had already remembered the live credential
    as seen, the service never asked again and issued no delivery for as long
    as the token stayed the same. A failed request is not an answer, so it is
    retried no more often than once per `retry_s` (default 60 s). A different
    account IS an answer, and spec v096 has the service read again only on the
    next change to the live credential or the global state file.
    """
    entry = importlib.import_module("caam_delivery_push_entry")
    answers = iter([None, "acct-1", "someone-else"])
    asked: list[str | None] = []

    def confirm(**_: object) -> str | None:
        answer = next(answers)
        asked.append(answer)
        return answer

    loop = entry.PushLoop()
    _live(home=tmp_path, token="tok-" + "r1", account="acct-1")
    entry.run_once(home=tmp_path, now=100.0, loop=loop, confirm=confirm)
    assert asked == [None] and loop.last is None
    entry.run_once(home=tmp_path, now=130.0, loop=loop, confirm=confirm)
    assert asked == [None]
    entry.run_once(home=tmp_path, now=160.0, loop=loop, confirm=confirm)
    assert asked == [None, "acct-1"]
    assert loop.last is not None and loop.last.account_id == "acct-1"
    sequence_file = tmp_path / ".local/state/caam-usage-rotate/delivery-sequence.json"
    assert _read(path=sequence_file) == {"sequence": loop.last.sequence}

    _live(home=tmp_path, token="tok-" + "r2", account="acct-2")
    entry.run_once(home=tmp_path, now=200.0, loop=loop, confirm=confirm)
    assert asked == [None, "acct-1", "someone-else"]
    entry.run_once(home=tmp_path, now=400.0, loop=loop, confirm=confirm)
    assert asked == [None, "acct-1", "someone-else"]
    assert loop.last.account_id == "acct-1"


def _inbox(
    *, home: Path, payload: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    """Run the exact inbox program the push sends a macOS host, as its python3 would."""
    macos = importlib.import_module("caam_delivery_macos")
    monkeypatch.setenv("HOME", str(home))
    code = 0
    try:
        program = macos.inbox_program(payload=payload)
        exec(compile(program, "<inbox>", "exec"), {"__name__": "__main__"})  # noqa: S102
    except SystemExit as stop:
        code = int(stop.code or 0)
    return code, capsys.readouterr().out.strip()


def test_scenario_a_macos_host_applies_a_delivery_from_its_inbox_and_its_result_is_recorded(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    inbox = tmp_path / ".claude/.caam-delivery-inbox.json"
    result = tmp_path / ".claude/.caam-delivery-result"
    run = {"home": tmp_path, "monkeypatch": monkeypatch, "capsys": capsys}

    assert _inbox(payload=_delivery(sequence=3), **run) == (0, "queued 3")
    assert inbox.stat().st_mode & 0o777 == 0o600
    assert json.loads(inbox.read_text(encoding="utf-8"))["sequence"] == 3
    assert [path.name for path in inbox.parent.iterdir()] == [inbox.name]

    _ = result.write_text("applied 2\n", encoding="utf-8")
    assert _inbox(payload=_delivery(sequence=3), **run) == (0, "queued 3; last-result applied 2")

    inbox.unlink()
    _ = result.write_text("applied 2\napplied 3\n", encoding="utf-8")
    assert _inbox(payload=_delivery(sequence=3), **run) == (0, "applied 3")
    assert not inbox.exists()
    _ = result.write_text("not-converted 3\n", encoding="utf-8")
    assert _inbox(payload=_delivery(sequence=3), **run) == (0, "not-converted 3")
    assert not inbox.exists()

    assert _inbox(payload="{}", **run) == (5, "failed - bad-delivery")
    assert TOKEN not in result.read_text(encoding="utf-8")


def test_a_macos_host_is_recorded_from_the_agent_result_for_this_sequence(
    *, tmp_path: Path
) -> None:
    push = importlib.import_module("caam_delivery_push")
    service = importlib.import_module("caam_delivery_service")
    settings = {**push.load_config(home=tmp_path), "retry_s": 60.0}
    delivery = service.Delivery(
        sequence=4, account_id="acct-a", identity={}, oauth={"accessToken": TOKEN, "expiresAt": 9}
    )
    (tmp_path / push.HOSTS_FILE).parent.mkdir(parents=True)
    _ = (tmp_path / push.HOSTS_FILE).write_text("mac u@mac macos\n", encoding="utf-8")
    replies = ["queued 4; last-result applied 3"]

    def fake_run(*, program: str, **_: object) -> tuple[int, str]:
        assert program.endswith("\n") and "main(" in program and "refreshToken" not in program
        return 0, replies[-1]

    def push_at(now: float) -> dict[str, str]:
        return push.push_due(
            home=tmp_path, delivery=delivery, now=now, run=fake_run, config=settings
        )

    assert push_at(10.0) == {"mac": "queued 4; last-result applied 3"}
    queued = push.load_state(home=tmp_path)["mac"]
    assert queued["state"] == "queued" and "last_success" not in queued
    assert "last_error" not in queued
    assert push_at(30.0) == {}

    replies.append("applied 4")
    assert push_at(71.0) == {"mac": "applied 4"}
    applied = push.load_state(home=tmp_path)["mac"]
    assert applied["state"] == "ok" and applied["sequence"] == 4
    assert applied["last_success"] == 71.0
    assert push_at(200.0) == {}


def test_only_a_result_naming_this_sequence_counts_as_reached(*, tmp_path: Path) -> None:
    push = importlib.import_module("caam_delivery_push")
    service = importlib.import_module("caam_delivery_service")
    delivery = service.Delivery(sequence=5, account_id="a", identity={}, oauth={})
    (tmp_path / push.HOSTS_FILE).parent.mkdir(parents=True)
    _ = (tmp_path / push.HOSTS_FILE).write_text("h u@h linux\n", encoding="utf-8")
    outcomes = push.push_due(
        home=tmp_path, delivery=delivery, now=1.0, run=lambda **_: (0, "applied 4")
    )
    assert outcomes == {"h": "applied 4"}
    entry = push.load_state(home=tmp_path)["h"]
    assert "last_success" not in entry and entry["last_error"] == "failed applied 4"
