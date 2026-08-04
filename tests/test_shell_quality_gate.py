"""Positive controls for the pinned shell-quality gate."""

from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path

import pytest

__all__: list[str] = []


def _git(*, cwd: Path, args: list[str]) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        check=True,
        env={
            "HOME": str(cwd),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "PATH": os.environ["PATH"],
        },
        text=True,
    )


def _write(*, root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _run_shell_quality(
    *, root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    _git(cwd=root, args=["init", "-q"])
    _git(cwd=root, args=["add", "-A"])
    monkeypatch.chdir(root)
    module = importlib.import_module("livespec_dev_tooling.checks.shell_quality")
    rc = module.main()
    captured = capsys.readouterr()
    return rc, captured.err


def test_shell_quality_rejects_known_shellcheck_warning(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(
        root=tmp_path,
        rel="scripts/defect.sh",
        body="#!/usr/bin/env bash\nset -euo pipefail\nunused_value=1\n",
    )

    rc, stderr = _run_shell_quality(root=tmp_path, monkeypatch=monkeypatch, capsys=capsys)

    assert rc == 1, stderr
    assert '"reason": "shellcheck-finding"' in stderr
    assert '"code": "SC2034"' in stderr


def test_shell_quality_accepts_clean_shell_surface(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(
        root=tmp_path,
        rel="scripts/clean.sh",
        body="#!/usr/bin/env bash\nset -euo pipefail\nprintf '%s\\n' ok\n",
    )

    rc, stderr = _run_shell_quality(root=tmp_path, monkeypatch=monkeypatch, capsys=capsys)

    assert rc == 0, stderr
