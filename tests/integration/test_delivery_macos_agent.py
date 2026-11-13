"""Integration coverage for the macOS launch agent that applies a pushed delivery."""

from __future__ import annotations

import getpass
import importlib
import json
import os
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

TOKEN = "tok-" + "secret-new"
_REAL_REPLACE = os.replace


class FakeSecurity:
    """The login Keychain as /usr/bin/security presents it, held in a dict."""

    def __init__(self, *, value: str | None, fail_writes: int = 0) -> None:
        self.items: dict[tuple[str, str], str] = {}
        self.argv: list[list[str]] = []
        self.fail_writes = fail_writes
        if value is not None:
            self.items[("Claude Code-credentials", "cw")] = value

    def __call__(self, args: list[str], stdin: str) -> tuple[int, str]:
        self.argv.append(args)
        if args[0] == "find-generic-password":
            found = self.items.get((args[2], args[4]))
            return (0, found + "\n") if found is not None else (44, "")
        words = shlex.split(stdin)
        if self.fail_writes:
            self.fail_writes -= 1
            return 1, ""
        key = (words[words.index("-s") + 1], words[words.index("-a") + 1])
        if words[0] == "delete-generic-password":
            _ = self.items.pop(key, None)
        else:
            self.items[key] = bytes.fromhex(words[words.index("-X") + 1]).decode("utf-8")
        return 0, ""


def _home(*, tmp_path: Path, sequence: int = 3, oauth: dict[str, object] | None = None) -> Path:
    folder = tmp_path / ".claude"
    folder.mkdir(parents=True)
    delivery = {
        "sequence": sequence,
        "account_id": "acct-b",
        "identity": {"oauthAccount": {"accountUuid": "acct-b"}, "userID": "user-b"},
        "oauth": oauth or {"accessToken": TOKEN, "expiresAt": 9},
    }
    _ = (folder / ".caam-delivery-inbox.json").write_text(json.dumps(delivery), encoding="utf-8")
    _ = (tmp_path / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "acct-a"}, "userID": "user-a", "keep": 1}),
        encoding="utf-8",
    )
    return tmp_path


def _old(*, refresh: bool = False) -> str:
    oauth: dict[str, object] = {"accessToken": "tok-old", "expiresAt": 1}
    if refresh:
        oauth["refreshToken"] = "r"
    return json.dumps({"claudeAiOauth": oauth, "mcpOAuth": {"k": "v"}})


def _agent() -> dict[str, object]:
    """The exact agent program the installer copies to a Mac, loaded as its python3 would."""
    macos = importlib.import_module("caam_delivery_macos")
    namespace: dict[str, object] = {"__name__": "caam_delivery_agent"}
    exec(compile(macos.AGENT_SCRIPT, "<agent>", "exec"), namespace)  # noqa: S102
    return namespace


def _fn(*, agent: dict[str, object], name: str) -> Callable[..., object]:
    return cast("Callable[..., object]", agent[name])


def _apply(*, home: Path, security: FakeSecurity, agent: dict[str, object] | None = None) -> object:
    loaded = agent or _agent()
    return _fn(agent=loaded, name="apply_inbox")(home=home, security=security, account="cw")


def _result(*, home: Path) -> str:
    path = home / ".claude/.caam-delivery-result"
    assert path.stat().st_mode & 0o777 == 0o600
    return path.read_text(encoding="utf-8")


def test_scenario_the_agent_applies_the_inbox_to_the_login_keychain_and_records_its_result(
    *, tmp_path: Path
) -> None:
    home = _home(tmp_path=tmp_path)
    security = FakeSecurity(value=_old())
    assert _apply(home=home, security=security) == "applied 3"
    stored = json.loads(security.items[("Claude Code-credentials", "cw")])
    assert stored == {
        "claudeAiOauth": {"accessToken": TOKEN, "expiresAt": 9},
        "mcpOAuth": {"k": "v"},
    }
    state = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert state == {"oauthAccount": {"accountUuid": "acct-b"}, "userID": "user-b", "keep": 1}
    assert (home / ".claude.json").stat().st_mode & 0o777 == 0o600
    assert (home / ".claude/.caam-delivery-sequence").read_text(encoding="utf-8") == "3"
    assert not (home / ".claude/.caam-delivery-inbox.json").exists()
    assert _result(home=home) == "applied 3\n"
    assert all(TOKEN not in " ".join(args) for args in security.argv)
    assert _apply(home=home, security=security) is None


@pytest.mark.parametrize(
    ("sequence", "oauth", "keychain", "expected"),
    [
        (3, None, _old(refresh=True), "not-converted 3"),
        (2, None, _old(), "stale-sequence 2 host-applied 2"),
        (
            3,
            {"accessToken": TOKEN, "refreshToken": "r"},
            _old(),
            "failed 3 delivered-refresh-token",
        ),
    ],
)
def test_the_agent_refuses_without_changing_anything(
    *, tmp_path: Path, sequence: int, oauth: dict[str, object] | None, keychain: str, expected: str
) -> None:
    home = _home(tmp_path=tmp_path, sequence=sequence, oauth=oauth)
    _ = (home / ".claude/.caam-delivery-sequence").write_text("2", encoding="utf-8")
    before = (home / ".claude.json").read_text(encoding="utf-8")
    security = FakeSecurity(value=keychain)
    assert _apply(home=home, security=security) == expected
    assert security.items[("Claude Code-credentials", "cw")] == keychain
    assert (home / ".claude.json").read_text(encoding="utf-8") == before
    assert _result(home=home) == expected + "\n"
    assert not (home / ".claude/.caam-delivery-inbox.json").exists()


def test_a_malformed_inbox_or_keychain_value_still_leaves_one_result_line(
    *, tmp_path: Path
) -> None:
    home = _home(tmp_path=tmp_path)
    _ = (home / ".claude/.caam-delivery-inbox.json").write_text("{}", encoding="utf-8")
    assert _apply(home=home, security=FakeSecurity(value=_old())) == "failed - bad-delivery"
    _ = (home / ".claude/.caam-delivery-inbox.json").write_text(
        json.dumps({"sequence": 3, "oauth": [], "identity": {}}), encoding="utf-8"
    )
    assert _apply(home=home, security=FakeSecurity(value=_old())) == "failed - bad-delivery"
    _ = (home / ".claude/.caam-delivery-inbox.json").write_text(
        json.dumps({"sequence": 3, "oauth": {}, "identity": {}}), encoding="utf-8"
    )
    assert _apply(home=home, security=FakeSecurity(value="not json")) == "failed - JSONDecodeError"


def test_a_failed_write_restores_both_previous_contents(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _home(tmp_path=tmp_path)
    before = (home / ".claude.json").read_text(encoding="utf-8")
    security = FakeSecurity(value=_old())

    refused: list[str] = []

    def refuse_state(src: str, dst: str | Path) -> None:
        if str(dst).endswith(".claude.json") and not refused:
            refused.append(str(dst))
            raise OSError("disk full")
        _REAL_REPLACE(src, dst)

    monkeypatch.setattr(os, "replace", refuse_state)
    assert _apply(home=home, security=security) == "failed 3 OSError rolled-back"
    assert security.items[("Claude Code-credentials", "cw")] == _old()
    assert (home / ".claude.json").read_text(encoding="utf-8") == before
    assert not (home / ".claude/.caam-delivery-sequence").exists()


def test_a_failed_restore_is_named_and_an_absent_original_is_removed(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _home(tmp_path=tmp_path)
    (home / ".claude.json").unlink()
    absent = FakeSecurity(value=None)
    agent = _agent()
    real_put = _fn(agent=agent, name="_put")

    def refuse_sequence(path: Path, data: bytes) -> None:
        if path.name == ".caam-delivery-sequence":
            raise OSError("disk full")
        _ = real_put(path, data)

    monkeypatch.setitem(agent, "_put", refuse_sequence)
    assert _apply(home=home, security=absent, agent=agent) == "failed 3 OSError rolled-back"
    assert absent.items == {}
    assert not (home / ".claude.json").exists()


def test_a_keychain_write_that_does_not_verify_is_rolled_back(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    security = FakeSecurity(value=_old(), fail_writes=1)
    assert _apply(home=home, security=security) == "failed 3 OSError rolled-back"
    assert security.items[("Claude Code-credentials", "cw")] == _old()
    stuck = FakeSecurity(value=_old(), fail_writes=2)
    assert _apply(home=_home(tmp_path=tmp_path / "b"), security=stuck) == (
        "failed 3 OSError; unrestored credential"
    )


def test_main_applies_for_the_current_user_and_run_security_feeds_stdin(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agent = _agent()
    calls: list[tuple[list[str], str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, str(kwargs["input"])))
        return subprocess.CompletedProcess(argv, 0, stdout="out\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _fn(agent=agent, name="run_security")(["-i"], "cmd\n") == (0, "out\n")
    assert calls == [(["/usr/bin/security", "-i"], "cmd\n")]

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    assert _fn(agent=agent, name="main")() == 0
    assert capsys.readouterr().out == ""
    home = _home(tmp_path=tmp_path / "h")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setitem(agent, "run_security", FakeSecurity(value=_old()))
    monkeypatch.setattr(getpass, "getuser", lambda: "cw")
    assert _fn(agent=agent, name="main")() == 0
    assert capsys.readouterr().out == "applied 3\n"


def _install(
    *, action: str, home: Path, monkeypatch: pytest.MonkeyPatch, bootstrap_rc: int = 0
) -> tuple[int, list[list[str]]]:
    """Run the exact install program the recipe sends a Mac, with launchctl faked."""
    macos = importlib.import_module("caam_delivery_macos")
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        rc = bootstrap_rc if argv[1] == "bootstrap" else 3
        return subprocess.CompletedProcess(argv, rc, stdout="", stderr="Bootstrap failed: 5\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("HOME", str(home))
    code = 0
    try:
        program = macos.install_program(action=action)
        exec(compile(program, "<install>", "exec"), {"__name__": "__main__"})  # noqa: S102
    except SystemExit as stop:
        code = int(stop.code or 0)
    return code, calls


def test_the_install_program_writes_the_agent_and_a_watching_launch_agent_and_reverts(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    macos = importlib.import_module("caam_delivery_macos")
    uid = os.getuid()
    agent = tmp_path / "Library/Application Support/caam-delivery/agent.py"
    plist = tmp_path / f"Library/LaunchAgents/{macos.AGENT_LABEL}.plist"
    code, calls = _install(action="install", home=tmp_path, monkeypatch=monkeypatch)
    assert code == 0 and capsys.readouterr().out == f"installed {macos.AGENT_LABEL}\n"
    assert agent.read_text(encoding="utf-8") == macos.AGENT_SCRIPT
    assert agent.stat().st_mode & 0o777 == 0o700
    text = plist.read_text(encoding="utf-8")
    assert f"<string>{tmp_path}/.claude/.caam-delivery-inbox.json</string>" in text
    assert f"<string>/usr/bin/python3</string><string>{agent}</string>" in text
    assert calls == [
        ["/bin/launchctl", "bootout", f"gui/{uid}/{macos.AGENT_LABEL}"],
        ["/bin/launchctl", "bootstrap", f"gui/{uid}", str(plist)],
    ]

    code, calls = _install(action="install", home=tmp_path, monkeypatch=monkeypatch, bootstrap_rc=5)
    assert code == 1 and capsys.readouterr().out == "failed bootstrap 5 Bootstrap failed: 5\n"

    code, calls = _install(action="uninstall", home=tmp_path, monkeypatch=monkeypatch)
    assert code == 0 and capsys.readouterr().out == f"uninstalled {macos.AGENT_LABEL}\n"
    assert not agent.exists() and not plist.exists()
    assert calls == [["/bin/launchctl", "bootout", f"gui/{uid}/{macos.AGENT_LABEL}"]]
    code, _ = _install(action="uninstall", home=tmp_path, monkeypatch=monkeypatch)
    assert code == 0
