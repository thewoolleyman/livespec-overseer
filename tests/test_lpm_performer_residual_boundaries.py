"""Residual fail-closed boundaries for the production acquisition performers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from overseer._vendor.returns.result import Failure

__all__: list[str] = []


def _write_executable(*, path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env python3\n{body}", encoding="utf-8")
    path.chmod(0o755)


def test_chrome_preflight_is_bounded_and_records_only_the_probed_identity(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_browser_performer as module

    oversized_dir = tmp_path / "oversized"
    oversized_dir.mkdir()
    oversized = oversized_dir / "google-chrome"
    _write_executable(
        path=oversized,
        body="import os\nos.write(1, b'Google Chrome 999.0 ' + b'x' * 8192 + b'\\n')\n",
    )
    assert isinstance(
        module.resolve_installed_google_chrome(
            search_path=(oversized_dir,),
            environ={"PATH": os.environ["PATH"]},
            timeout_seconds=1.0,
        ),
        Failure,
    )

    raced_dir = tmp_path / "raced"
    raced_dir.mkdir()
    raced = raced_dir / "google-chrome"
    _write_executable(path=raced, body="print('Google Chrome 999.0')\n")
    probed_identity = raced.stat().st_ino

    def replace_after_probe(**_kwargs: object) -> bool:
        replacement = raced_dir / "replacement"
        _write_executable(path=replacement, body="print('Google Chrome replacement')\n")
        replacement.replace(raced)
        assert raced.stat().st_ino != probed_identity
        return True

    monkeypatch.setattr(module, "is_google_chrome", replace_after_probe)
    assert isinstance(
        module.resolve_installed_google_chrome(
            search_path=(raced_dir,),
            environ={"PATH": os.environ["PATH"]},
            timeout_seconds=1.0,
        ),
        Failure,
    )
