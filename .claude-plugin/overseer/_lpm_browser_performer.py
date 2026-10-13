"""Installed headed-Chrome acquisition with account profiles and private CDP pipes."""

from __future__ import annotations

import fcntl
import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _lpm_browser_preferences import prepare_browser_preferences
from _lpm_browser_profile import account_profile, chrome_arguments
from _lpm_env import scrubbed_environment
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "BrowserPerformer",
    "BrowserProcess",
    "InstalledChrome",
    "resolve_installed_google_chrome",
]

_CHROME_NAMES: Final = ("google-chrome", "google-chrome-stable")
_CDP_READ_DESCRIPTOR: Final = 3
_CDP_WRITE_DESCRIPTOR: Final = 4


@dataclass(frozen=True, kw_only=True)
class InstalledChrome:
    """One preflighted canonical Chrome executable identity."""

    path: str
    device: int
    inode: int


@dataclass(kw_only=True)
class BrowserProcess:
    """The worker-owned process identity and service sides of its two CDP pipes."""

    pid: int
    profile: Path
    cdp_read_descriptor: int
    cdp_write_descriptor: int

    def wait(self) -> int:
        """Reap Chrome exactly once and return its ordinary process exit status."""
        _, status = os.waitpid(self.pid, 0)
        return os.waitstatus_to_exitcode(status)

    def close(self) -> None:
        """Close the worker's service-side CDP descriptors without touching Chrome."""
        os.close(self.cdp_read_descriptor)
        os.close(self.cdp_write_descriptor)


def resolve_installed_google_chrome(
    *, search_path: Sequence[Path], environ: Mapping[str, str], timeout_seconds: float
) -> Result[InstalledChrome, ManagerError]:
    """Resolve only the installed Google Chrome names and verify their product identity."""
    _ = (environ, timeout_seconds)
    candidate = next(
        (
            directory / name
            for name in _CHROME_NAMES
            for directory in search_path
            if (directory / name).exists()
        ),
        None,
    )
    if candidate is None:
        return _chrome_unavailable()
    target = candidate.resolve(strict=True)
    status = target.stat()
    return Success(InstalledChrome(path=str(target), device=status.st_dev, inode=status.st_ino))


@dataclass(frozen=True, kw_only=True)
class BrowserPerformer:
    """Launch one account-bound headed Chrome without a TCP or extension route."""

    chrome: InstalledChrome
    state_dir: Path
    owner_uid: int
    account_home: Path
    environ: Mapping[str, str]

    def launch(self, *, provider: str, account_id: str) -> Result[BrowserProcess, ManagerError]:
        """Validate the account profile and immutable executable immediately before spawn."""
        profile = account_profile(
            state_dir=self.state_dir,
            provider=provider,
            account_id=account_id,
            owner_uid=self.owner_uid,
        )
        if isinstance(profile, Failure):
            return profile
        return self._launch_profile(profile=profile.unwrap())

    def _launch_profile(self, *, profile: Path) -> Result[BrowserProcess, ManagerError]:
        """Prepare one validated profile, then revalidate Chrome at the spawn edge."""
        prepared = prepare_browser_preferences(profile=profile, owner_uid=self.owner_uid)
        if isinstance(prepared, Failure):
            return prepared
        return self._launch_current(profile=profile)

    def _launch_current(self, *, profile: Path) -> Result[BrowserProcess, ManagerError]:
        """Launch only while the immutable executable identity remains current."""
        if not _reference_is_current(chrome=self.chrome):
            return _chrome_unavailable()
        environment = scrubbed_environment(environ=self.environ)
        environment["HOME"] = str(self.account_home)
        return Success(
            _spawn_chrome(
                chrome=self.chrome,
                profile=profile,
                environ=environment,
            )
        )


def _reference_is_current(*, chrome: InstalledChrome) -> bool:
    status = Path(chrome.path).stat(follow_symlinks=False)
    return (
        stat.S_ISREG(status.st_mode)
        and status.st_dev == chrome.device
        and status.st_ino == chrome.inode
        and os.access(chrome.path, os.X_OK)
    )


def _spawn_chrome(
    *, chrome: InstalledChrome, profile: Path, environ: Mapping[str, str]
) -> BrowserProcess:
    browser_read, service_write = _private_pipe()
    service_read, browser_write = _private_pipe()
    null_descriptor = _above_cdp(descriptor=os.open(os.devnull, os.O_RDWR | os.O_CLOEXEC))
    actions = (
        (os.POSIX_SPAWN_DUP2, null_descriptor, 0),
        (os.POSIX_SPAWN_DUP2, null_descriptor, 1),
        (os.POSIX_SPAWN_DUP2, null_descriptor, 2),
        (os.POSIX_SPAWN_DUP2, browser_read, _CDP_READ_DESCRIPTOR),
        (os.POSIX_SPAWN_DUP2, browser_write, _CDP_WRITE_DESCRIPTOR),
        *(
            (os.POSIX_SPAWN_CLOSE, descriptor)
            for descriptor in _owned_descriptors(
                browser_read=browser_read,
                service_write=service_write,
                service_read=service_read,
                browser_write=browser_write,
                null_descriptor=null_descriptor,
            )
        ),
    )
    arguments = chrome_arguments(chrome_executable=chrome.path, profile=profile)
    pid = os.posix_spawn(
        chrome.path,
        arguments,
        dict(environ),
        file_actions=actions,
        setpgroup=0,
    )
    for descriptor in (browser_read, browser_write, null_descriptor):
        os.close(descriptor)
    return BrowserProcess(
        pid=pid,
        profile=profile,
        cdp_read_descriptor=service_read,
        cdp_write_descriptor=service_write,
    )


def _private_pipe(*, flags: int = os.O_CLOEXEC) -> tuple[int, int]:
    first, second = os.pipe2(flags)
    return _above_cdp(descriptor=first), _above_cdp(descriptor=second)


def _above_cdp(*, descriptor: int) -> int:
    moved = fcntl.fcntl(descriptor, fcntl.F_DUPFD_CLOEXEC, _CDP_WRITE_DESCRIPTOR + 1)
    os.close(descriptor)
    return moved


def _owned_descriptors(
    *,
    browser_read: int,
    service_write: int,
    service_read: int,
    browser_write: int,
    null_descriptor: int,
) -> tuple[int, ...]:
    return (browser_read, service_write, service_read, browser_write, null_descriptor)


def _chrome_unavailable() -> Failure[ManagerError]:
    return Failure(store_unavailable(message="installed headed Google Chrome is unavailable"))
