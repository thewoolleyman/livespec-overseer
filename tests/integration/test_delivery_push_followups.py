"""Status shows the live vs selected account; Remote Control is re-issued on account change."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest


def _write(*, path: Path, body: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(body), encoding="utf-8")


def _live(*, home: Path, token: str, account: str) -> None:
    _write(
        path=home / ".claude/.credentials.json",
        body={"claudeAiOauth": {"accessToken": token, "expiresAt": 9_999_999_999_000}},
    )
    _write(
        path=home / ".claude.json", body={"oauthAccount": {"accountUuid": account}, "userID": "u"}
    )


def test_status_flags_a_live_login_that_is_not_caams_selected_account(*, tmp_path: Path) -> None:
    push = importlib.import_module("caam_delivery_push")
    _live(home=tmp_path, token="t" + "1", account="acct-live")
    selection = tmp_path / ".local/state/caam-usage-rotate/selected-account.json"
    _write(
        path=selection,
        body={"account_uuid": "acct-other", "profile": "anthropic-3", "written_at": 1},
    )

    lines = push.status_lines(home=tmp_path, now=0.0)
    assert "role holder live account: acct-live" in lines
    assert "caam selected account: anthropic-3 (acct-other)" in lines
    assert any(line.startswith("MISMATCH") for line in lines)

    _write(
        path=selection,
        body={"account_uuid": "acct-live", "profile": "anthropic-2", "written_at": 2},
    )
    assert not any(
        line.startswith("MISMATCH") for line in push.status_lines(home=tmp_path, now=0.0)
    )


def test_remote_control_is_reissued_only_when_the_account_changes(*, tmp_path: Path) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    _write(path=tmp_path / ".config/caam-delivery/hosts", body=None)
    _ = (tmp_path / ".config/caam-delivery/hosts").write_text("h1\n", encoding="utf-8")
    sent: list[str] = []
    local: list[str] = []

    def fake_run(*, target: str, script: str, payload: str) -> tuple[int, str]:
        sent.append("apply" if script == push.APPLY_SCRIPT else "reissue")
        return 0, "applied" if script == push.APPLY_SCRIPT else '{"reissued": ["%3"]}'

    def fake_local(*, script: str) -> str:
        local.append(script)
        return '{"reissued": []}'

    def step(*, token: str, account: str, now: float) -> None:
        _live(home=tmp_path, token=token, account=account)
        _ = entry.run_once(
            home=tmp_path,
            now=now,
            seen=None,
            confirm=lambda **_: account,
            run=fake_run,
            reissue="RC",
            local=fake_local,
        )

    step(token="a" + "1", account="acct-a", now=10.0)
    assert sent == ["apply", "reissue"] and local == []
    sent.clear()
    step(token="a" + "2", account="acct-a", now=20.0)
    assert sent == ["apply"] and local == []
    sent.clear()
    step(token="b" + "1", account="acct-b", now=30.0)
    assert sent == ["apply", "reissue"] and local == ["RC"]


def test_reissue_script_loading_and_local_run(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    script = tmp_path / "remote_control_reissue.py"
    assert push.reissue_script(path=script) is None
    _ = script.write_text("print(1)", encoding="utf-8")
    assert push.reissue_script(path=script) == "print(1)"

    def fake_subprocess(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout='{"reissued": ["%1"]}\n', stderr="")

    monkeypatch.setattr(entry.subprocess, "run", fake_subprocess)
    assert entry.run_local(script="print(1)") == '{"reissued": ["%1"]}'
