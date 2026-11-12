"""Integration coverage for pushing in-memory deliveries to listed hosts over ssh."""

from __future__ import annotations

import importlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOKEN = "tok-" + "secret-a"


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
    push = importlib.import_module("caam_delivery_push")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    code = 0
    try:
        exec(compile(push.APPLY_SCRIPT, "<apply>", "exec"), {"__name__": "__main__"})  # noqa: S102
    except SystemExit as stop:
        code = int(stop.code or 0)
    return code, capsys.readouterr().out.strip()


def _delivery(*, sequence: int, oauth: dict[str, object] | None = None) -> str:
    return json.dumps(
        {
            "sequence": sequence,
            "account_id": "a",
            "identity": {"oauthAccount": {"accountUuid": "a"}, "userID": "u"},
            "oauth": oauth or {"accessToken": f"t{sequence}", "expiresAt": 1},
        }
    )


def test_apply_step_locks_merges_refuses_and_rolls_back(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    host = tmp_path / "host"
    _write(path=host / ".claude/.credentials.json", body={"mcpOAuth": {"k": 1}})
    _write(path=host / ".claude.json", body={"theme": "dark"})
    io_kwargs = {"monkeypatch": monkeypatch, "capsys": capsys}

    assert _apply(home=host, payload=_delivery(sequence=2), **io_kwargs) == (0, "applied 2")
    creds = host / ".claude/.credentials.json"
    assert json.loads(creds.read_text(encoding="utf-8")) == {
        "mcpOAuth": {"k": 1},
        "claudeAiOauth": {"accessToken": "t2", "expiresAt": 1},
    }
    assert creds.stat().st_mode & 0o777 == 0o600
    assert (host / ".claude.json").stat().st_mode & 0o777 == 0o600
    assert json.loads((host / ".claude.json").read_text(encoding="utf-8"))["theme"] == "dark"
    assert _apply(home=host, payload=_delivery(sequence=2), **io_kwargs) == (0, "current 2")
    assert _apply(home=host, payload=_delivery(sequence=1), **io_kwargs) == (
        0,
        "stale-sequence 2",
    )
    leaky = _delivery(sequence=3, oauth={"accessToken": "t3", "refreshToken": "x"})
    assert _apply(home=host, payload=leaky, **io_kwargs) == (4, "failed delivered-refresh-token")
    assert _apply(home=host, payload="not json", **io_kwargs) == (5, "failed bad-delivery")

    own = tmp_path / "own"
    _write(path=own / ".claude/.credentials.json", body={"claudeAiOauth": {"refreshToken": "m"}})
    assert _apply(home=own, payload=_delivery(sequence=1), **io_kwargs) == (3, "not-converted")

    partial = tmp_path / "partial"
    _write(path=partial / ".claude/.credentials.json", body={"keep": 1})
    _write(path=partial / ".claude.json", body={"keep": 2})
    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    reply = _apply(home=partial, payload=_delivery(sequence=1), **io_kwargs)
    assert reply == (5, "failed rolled-back OSError")
    assert json.loads((partial / ".claude/.credentials.json").read_text(encoding="utf-8")) == {
        "keep": 1
    }
    assert json.loads((partial / ".claude.json").read_text(encoding="utf-8")) == {"keep": 2}


def test_push_records_each_host_state_and_never_leaks_the_token(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    status = importlib.import_module("caam_delivery_push_status")
    _live(home=tmp_path, token=TOKEN, account="acct-a")
    _write(path=tmp_path / ".config/caam-delivery/config.json", body={"retry_s": 30})
    _ = (tmp_path / ".config/caam-delivery/hosts").write_text(
        "good u@good linux\nkey u@key linux\nnc u@nc linux\nmac u@mac macos\n"
        "bad -oProxyCommand=x linux\njunk\n# comment\n\n",
        encoding="utf-8",
    )
    sent: list[str] = []
    replies = {
        "u@good": "applied 1",
        "u@key": "failed host-key-verification",
        "u@nc": "not-converted",
    }

    def fake_run(
        *, target: str, script: str, payload: str, key: str, timeout: float
    ) -> tuple[int, str]:
        assert key.endswith("id_ed25519") and timeout > 0 and "refreshToken" not in payload
        sent.append(target if script == push.APPLY_SCRIPT else "rc:" + target)
        return 0, replies.get(target, '{"reissued": []}')

    loop = entry.PushLoop()
    run = {"confirm": lambda **_: "acct-a", "run": fake_run, "reissue": "RC"}
    entry.run_once(home=tmp_path, now=100.0, loop=loop, **run)
    assert sorted(sent) == ["rc:u@good", "u@good", "u@key", "u@nc"]
    assert "host list line 5 rejected" in capsys.readouterr().err

    sent.clear()
    entry.run_once(home=tmp_path, now=110.0, loop=loop, **run)
    assert sent == []
    entry.run_once(home=tmp_path, now=140.0, loop=loop, **run)
    assert sent == ["u@key"]

    sent.clear()
    replies["u@good"] = "failed weird " + "tok-" + "secret-b"
    _live(home=tmp_path, token="tok-" + "secret-b", account="acct-a")
    entry.run_once(home=tmp_path, now=150.0, loop=loop, **run)
    assert "rc:u@good" not in sent
    saved = (tmp_path / push.PUSH_STATE).read_text(encoding="utf-8")
    assert "secret" not in saved and "[redacted]" in saved

    lines = status.status_lines(home=tmp_path, now=160.0, reissue_available=False)
    text = "\n".join(lines)
    assert "secret" not in text
    assert "good  u@good  linux  failed  1" in text
    assert "key  u@key  linux  failed  -  never  failed host-key-verification" in text
    assert "nc  u@nc  linux  not-converted" in text
    assert "mac  u@mac  macos  failed  -  never  failed unsupported-platform" in text
    assert "remote-control: re-issue unavailable" in text
    assert entry.run_once(home=tmp_path, now=1_100.0, loop=loop, **run) is None
    assert "u@nc" in sent


def test_status_states_profiles_divergence_and_expiry(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path
) -> None:
    status = importlib.import_module("caam_delivery_push_status")
    state = status.host_state
    fresh = {"state": "ok", "sequence": 1, "last_success": 100.0}
    assert state(entry=fresh, current_sequence=1, now=110.0, stale_after=900.0) == "current"
    assert state(entry=fresh, current_sequence=2, now=110.0, stale_after=900.0) == "lagging"
    assert state(entry=fresh, current_sequence=1, now=5_000.0, stale_after=900.0) == "stale"
    expired = {**fresh, "expires_at": 50_000}
    assert state(entry=expired, current_sequence=1, now=110.0, stale_after=900.0) == "expired"

    _live(home=tmp_path, token=TOKEN, account="acct-live", expires=1_000)
    assert "role holder live profile: acct-live" in status.status_lines(
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
    lines = status.status_lines(home=tmp_path, now=10.0, reissue_available=True)
    assert "role holder live profile: anthropic-2" in lines
    assert "caam selected profile: anthropic-1" in lines
    assert any(line.startswith("diverged") for line in lines)
    assert any(line.startswith("expired") for line in lines)
    assert not any(line.startswith("remote-control") for line in lines)
    _write(path=selection, body={"account_uuid": "acct-live", "profile": "anthropic-2"})
    _ = (vault / "anthropic-1/.claude.json").unlink()
    _ = vault.joinpath("anthropic-1").rmdir()
    lines = status.status_lines(home=tmp_path, now=10.0, reissue_available=True)
    assert not any(line.startswith("diverged") for line in lines)

    other = tmp_path / "other"
    _live(home=other, token=TOKEN, account="acct-z")
    _write(path=other / ".local/share/caam/vault/claude/p/.claude.json", body={})
    assert "role holder live profile: acct-z" in status.status_lines(
        home=other, now=10.0, reissue_available=True
    )


def test_ssh_runner_hardening_and_failures(*, monkeypatch: pytest.MonkeyPatch) -> None:
    push = importlib.import_module("caam_delivery_push")
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

    def fake_subprocess(argv: list[str], **_: object) -> object:
        assert argv[:7] == [
            "/usr/bin/ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-o",
            "StrictHostKeyChecking=yes",
        ]
        assert argv[7] == "-i" and argv[9:12] == ["-o", "IdentitiesOnly=yes", "--"]
        result = outcomes[argv[12]]
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(push.subprocess, "run", fake_subprocess)

    def ssh(target: str) -> tuple[int, str]:
        return push.run_ssh(target=target, script="print(1)", payload="{}", key="~/k", timeout=1.0)

    assert ssh("ok") == (0, "applied 3")
    assert ssh("hostkey") == (255, "failed host-key-verification")
    assert ssh("exit") == (255, "failed ssh-exit 255")
    assert ssh("silent") == (0, "failed no-reply")
    assert ssh("slow") == (124, "failed timeout")
    assert ssh("gone") == (255, "failed ssh-unavailable FileNotFoundError")


def test_entry_seams_and_main(  # noqa: PLR0915 - one end-to-end scenario per test
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    probe = "t"
    monkeypatch.setattr(entry, "get_json", lambda **_: ({"account_uuid": "acct"}, None))
    assert entry.confirm_live_account(access_token=probe) == "acct"
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

    def fake_subprocess(argv: list[str], **_: object) -> object:
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
        host=host, script=None, run=None, settings=push.load_config(home=tmp_path)
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
    assert push._due(entry=entry_state, sequence=1, now=40.0, settings=settings)
