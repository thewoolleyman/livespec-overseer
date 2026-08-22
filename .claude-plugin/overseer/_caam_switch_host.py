"""Host boundary for caam switch execution: the OS lock and the caam call.

Split out of ``caam_switch`` so that module sits under the 200-LLOC soft
ceiling. The seam is not arbitrary: everything here touches the host and is
the only part of switch execution that cannot be exercised in-process, which
is why every definition below carries ``# pragma: no cover`` while nothing in
``caam_switch`` does. The two lock Protocols come with it because they are the
types this boundary is written in terms of, and leaving them behind would make
the import circular.

``caam_switch`` re-exports these names, so its public API is unchanged.
"""

from __future__ import annotations

import fcntl
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

__all__: list[str] = [
    "SwitchLock",
    "SwitchLockFactory",
    "acquire_switch_lock",
    "caam_activate",
]


class SwitchLock(Protocol):
    def __enter__(self) -> SwitchLock: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool | None: ...


class SwitchLockFactory(Protocol):
    def __call__(self, *, lock_path: Path) -> SwitchLock | None: ...


@dataclass(kw_only=True)
class _FcntlSwitchLock:  # pragma: no cover
    handle: TextIO

    def __enter__(self) -> _FcntlSwitchLock:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        del exc_type, exc, traceback
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        return False


def acquire_switch_lock(*, lock_path: Path) -> SwitchLock | None:  # pragma: no cover
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return _FcntlSwitchLock(handle=handle)


def caam_activate(  # pragma: no cover
    *, args: tuple[str, ...], timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ("caam", *args),
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
