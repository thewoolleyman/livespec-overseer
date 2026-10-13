"""Production acquisition performers keep local browser and terminal authority closed."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import ModuleType

from overseer._vendor.returns.result import Failure

__all__: list[str] = []


def _write_chrome_standin(*, path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import stat
import sys
from pathlib import Path

if sys.argv[1:] == ["--version"]:
    print("Google Chrome 999.0.0.0")
    raise SystemExit(0)

record = {
    "argv": sys.argv,
    "fd3_fifo": stat.S_ISFIFO(os.fstat(3).st_mode),
    "fd4_fifo": stat.S_ISFIFO(os.fstat(4).st_mode),
}
Path(os.environ["LPM_TEST_CHROME_RECORD"]).write_text(json.dumps(record))
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _profile_root(*, state_dir: Path) -> Path:
    root = state_dir / "browser-profiles"
    root.mkdir(parents=True, mode=0o700)
    return root


def _assert_non_chrome_routes_refuse(*, module: ModuleType, tmp_path: Path) -> None:
    extension_only = tmp_path / "extension-only"
    extension_only.mkdir()
    unavailable = module.resolve_installed_google_chrome(
        search_path=(extension_only,),
        environ={"DISPLAY": ":99", "BROWSER": "browser-extension://open"},
        timeout_seconds=1.0,
    )
    assert isinstance(unavailable, Failure)

    chromium_only = tmp_path / "chromium-only"
    chromium_only.mkdir()
    chromium = chromium_only / "chromium"
    chromium.write_text("#!/bin/sh\necho 'Chromium 999.0'\n", encoding="utf-8")
    chromium.chmod(0o755)
    assert isinstance(
        module.resolve_installed_google_chrome(
            search_path=(chromium_only,),
            environ={"WAYLAND_DISPLAY": "wayland-9"},
            timeout_seconds=1.0,
        ),
        Failure,
    )


def _profile_from(*, record: dict[str, object]) -> Path:
    arguments = record["argv"]
    assert isinstance(arguments, list)
    return Path(
        next(
            argument.removeprefix("--user-data-dir=")
            for argument in arguments
            if isinstance(argument, str) and argument.startswith("--user-data-dir=")
        )
    )


def _assert_private_headed_launch(*, module: ModuleType, tmp_path: Path) -> None:
    chrome_bin = tmp_path / "chrome-bin"
    chrome_bin.mkdir()
    chrome = chrome_bin / "google-chrome"
    _write_chrome_standin(path=chrome)
    record_path = tmp_path / "chrome-record.json"
    environment = {
        "DISPLAY": ":99",
        "PATH": os.environ["PATH"],
        "LPM_TEST_CHROME_RECORD": str(record_path),
        "CLAUDE_CODE_OAUTH_TOKEN": "must-not-cross",
        "OP_SERVICE_ACCOUNT_TOKEN": "must-not-cross-either",
    }
    installed = module.resolve_installed_google_chrome(
        search_path=(chrome_bin,),
        environ=environment,
        timeout_seconds=1.0,
    ).unwrap()
    state_dir = tmp_path / "state"
    _profile_root(state_dir=state_dir)
    performer = module.BrowserPerformer(
        chrome=installed,
        state_dir=state_dir,
        owner_uid=os.geteuid(),
        account_home=tmp_path,
        environ=environment,
    )
    first = performer.launch(provider="anthropic", account_id="account-a").unwrap()
    assert first.wait() == 0
    first_record = json.loads(record_path.read_text(encoding="utf-8"))
    first.close()
    second = performer.launch(provider="anthropic", account_id="account-b").unwrap()
    assert second.wait() == 0
    second_record = json.loads(record_path.read_text(encoding="utf-8"))
    second.close()

    assert _profile_from(record=first_record) != _profile_from(record=second_record)
    assert stat.S_IMODE(_profile_from(record=first_record).stat().st_mode) == 0o700
    assert stat.S_IMODE(_profile_from(record=second_record).stat().st_mode) == 0o700
    assert first_record["fd3_fifo"] is first_record["fd4_fifo"] is True
    arguments = first_record["argv"]
    assert "--remote-debugging-pipe" in arguments
    assert not any(
        forbidden in argument
        for argument in arguments
        for forbidden in ("headless", "extension", "remote-debugging-port")
    )


def test_browser_performer_launches_only_installed_headed_chrome_over_private_pipes(
    *, tmp_path: Path
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_browser_performer.py"
    assert module_path.is_file(), "the production browser performer must be implemented"

    import overseer._lpm_browser_performer as module

    _assert_non_chrome_routes_refuse(module=module, tmp_path=tmp_path)
    _assert_private_headed_launch(module=module, tmp_path=tmp_path)
