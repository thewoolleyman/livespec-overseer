"""Integration coverage for pushing deliveries to listed hosts over ssh."""

from __future__ import annotations

import importlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _live(*, home: Path, token: str, account: str) -> None:
    creds = home / ".claude/.credentials.json"
    creds.parent.mkdir(parents=True, exist_ok=True)
    _ = creds.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": token,
                    "expiresAt": 9_999_999_999_000,
                    "refreshToken": "r",
                }
            }
        ),
        encoding="utf-8",
    )
    _ = (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": account}, "userID": "u"}), encoding="utf-8"
    )


def _hosts(*, home: Path, text: str) -> None:
    path = home / ".config/caam-delivery/hosts"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")


def _apply(
    *,
    script: str,
    home: Path,
    payload: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    code = 0
    try:
        exec(compile(script, "<apply>", "exec"), {"__name__": "__main__"})  # noqa: S102
    except SystemExit as stop:
        code = int(stop.code or 0)
    return code, capsys.readouterr().out.strip()


def test_apply_script_merges_without_a_refresh_token_and_never_moves_backwards(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    host = tmp_path / "host"
    (host / ".claude").mkdir(parents=True)
    _ = (host / ".claude/.credentials.json").write_text(
        json.dumps({"mcpOAuth": {"k": 1}}), encoding="utf-8"
    )
    _ = (host / ".claude.json").write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    delivery = {
        "sequence": 2,
        "account_id": "a",
        "identity": {"oauthAccount": {"accountUuid": "a"}, "userID": "u"},
        "oauth": {"accessToken": "t2", "expiresAt": 1},
    }

    assert _apply(
        script=push.APPLY_SCRIPT,
        home=host,
        payload=json.dumps(delivery),
        monkeypatch=monkeypatch,
        capsys=capsys,
    ) == (
        0,
        "applied",
    )
    creds = json.loads((host / ".claude/.credentials.json").read_text(encoding="utf-8"))
    assert creds == {"mcpOAuth": {"k": 1}, "claudeAiOauth": {"accessToken": "t2", "expiresAt": 1}}
    state = json.loads((host / ".claude.json").read_text(encoding="utf-8"))
    assert state["theme"] == "dark" and state["oauthAccount"] == {"accountUuid": "a"}

    older = {**delivery, "sequence": 1, "oauth": {"accessToken": "t1"}}
    assert _apply(
        script=push.APPLY_SCRIPT,
        home=host,
        payload=json.dumps(older),
        monkeypatch=monkeypatch,
        capsys=capsys,
    ) == (0, "current")
    assert "t2" in (host / ".claude/.credentials.json").read_text(encoding="utf-8")

    own = tmp_path / "own"
    (own / ".claude").mkdir(parents=True)
    _ = (own / ".claude/.credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"refreshToken": "mine"}}), encoding="utf-8"
    )
    assert _apply(
        script=push.APPLY_SCRIPT,
        home=own,
        payload=json.dumps(delivery),
        monkeypatch=monkeypatch,
        capsys=capsys,
    ) == (
        3,
        "not-converted",
    )


def test_push_and_status_track_each_listed_host(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert push.load_hosts(home=tmp_path) == []
    assert push.live_pair(home=tmp_path) is None
    assert entry.run_once(home=tmp_path / "empty", now=1.0, seen=None) is None
    _live(home=tmp_path, token="tok-" + "a", account="acct-a")
    _hosts(home=tmp_path, text="good  # comment\n\nbad\n")
    calls: list[str] = []

    def fake_run(*, target: str, script: str, payload: str) -> tuple[int, str]:
        assert script == push.APPLY_SCRIPT and "refreshToken" not in payload
        calls.append(target)
        return (0, "applied") if target == "good" else (255, "ssh: connect timed out")

    seen = entry.run_once(
        home=tmp_path, now=100.0, seen=None, confirm=lambda **_: "acct-a", run=fake_run
    )
    assert seen is not None and sorted(calls) == ["bad", "good"]
    calls.clear()
    assert (
        entry.run_once(home=tmp_path, now=110.0, seen=seen, confirm=lambda **_: None, run=fake_run)
        == seen
    )
    assert calls == []
    _ = entry.run_once(home=tmp_path, now=140.0, seen=seen, run=fake_run)
    assert calls == ["bad"]

    lines = push.status_lines(home=tmp_path, now=150.0)
    assert lines[1].startswith("good  acct-a  1970-01-01T00:01:40Z  current  -")
    assert lines[2] == "bad  -  never  stale  ssh: connect timed out"
    assert "tok-a" not in "\n".join(lines)
    monkeypatch.setattr(sys, "argv", ["caam-delivery-push", "status"])
    assert entry.main() == 0
    monkeypatch.setattr(entry, "run_once", lambda **kw: kw["seen"])
    assert entry.main(argv=["run"], sleep=lambda _: None, passes=1) == 0


def test_ssh_runner_and_account_confirmation(*, monkeypatch: pytest.MonkeyPatch) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")

    def fake_subprocess(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert argv[:5] == ["/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
        if argv[5] == "slow":
            raise subprocess.TimeoutExpired(cmd=argv, timeout=30)
        return subprocess.CompletedProcess(argv, 0, stdout="x\napplied\n", stderr="")

    monkeypatch.setattr(push.subprocess, "run", fake_subprocess)
    assert push.run_ssh(target="h", script="print(1)", payload="{}") == (0, "applied")
    assert push.run_ssh(target="slow", script="print(1)", payload="{}") == (124, "timeout")

    probe = "t"
    monkeypatch.setattr(entry, "get_json", lambda **_: ({"account_uuid": "acct"}, None))
    assert entry.confirm_live_account(access_token=probe) == "acct"
    monkeypatch.setattr(entry, "get_json", lambda **_: (None, "HTTP 401 for t"))
    assert entry.confirm_live_account(access_token=probe) is None
    monkeypatch.setattr(entry, "get_json", lambda **_: ({}, None))
    assert entry.confirm_live_account(access_token=probe) is None
