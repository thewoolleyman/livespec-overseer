"""The installed-root fixture runs only where this process can enter a chroot."""

from pathlib import Path

import pytest

from overseer import test_lpm_installed_runtime as runtime


def test_an_unprivileged_process_skips_the_installed_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime.os, "geteuid", lambda: 1000)
    with pytest.raises(pytest.skip.Exception):
        _ = runtime.chroot_binary()


def test_a_host_without_chroot_skips_the_installed_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime.os, "geteuid", lambda: 0)
    monkeypatch.setattr(runtime.shutil, "which", lambda *_args, **_kwargs: None)
    with pytest.raises(pytest.skip.Exception):
        _ = runtime.chroot_binary()


def test_root_resolves_chroot_from_either_binary_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched: list[str] = []

    def which(name: str, *, path: str) -> str:
        searched.append(path)
        return f"/usr/bin/{name}"

    monkeypatch.setattr(runtime.os, "geteuid", lambda: 0)
    monkeypatch.setattr(runtime.shutil, "which", which)
    assert runtime.chroot_binary() == "/usr/bin/chroot"
    assert searched == ["/usr/sbin:/usr/bin:/sbin:/bin"]


def test_the_system_interpreter_is_resolved_not_named_by_minor_version() -> None:
    interpreter = runtime.system_python()
    assert interpreter == Path("/usr/bin/python3").resolve()
    assert interpreter.is_file()
