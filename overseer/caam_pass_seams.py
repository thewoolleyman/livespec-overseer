"""The production seams a caam rotation pass binds when a caller injects none.

Split out of ``caam_anthropic_pass`` (work-item overseer-m7qrgp.3), which stood
exactly ON the 250-LLOC hard ceiling and could not carry another line. The cut is
by cohesion rather than by count: everything here is how the pass REACHES THE
HOST -- running `caam`, running an agent, writing a log line -- while the module
it left holds the pass's own shape and ordering.

Every name is PUBLIC because a seam another module binds cannot be a private
helper: pyright strict's ``reportPrivateUsage`` and the repo's ``private_calls``
gate both refuse a cross-module ``_``-prefixed import, and rightly so -- these
four ARE the interface between the pass and the host it runs on.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Final, Protocol

from _caam_switch_host import caam_activate
from caam_anthropic_finish import LineWriter
from caam_warm import AgentProcess, Logger

__all__: list[str] = [
    "AgentRunner",
    "default_agent_runner",
    "default_caam_runner",
    "line_logger",
]

_CAAM_TIMEOUT_S: Final = 60.0


class AgentRunner(Protocol):
    def __call__(
        self,
        *,
        args: tuple[str, ...],
        env: dict[str, str],
        timeout: float,
    ) -> AgentProcess: ...


def default_caam_runner(*, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return caam_activate(args=args, timeout=_CAAM_TIMEOUT_S)


def line_logger(*, writer: LineWriter) -> Logger:
    return _LineLogger(writer=writer)


@dataclass(frozen=True, kw_only=True)
class _LineLogger:
    writer: LineWriter

    def __call__(self, message: str) -> None:
        self.writer(message)


def default_agent_runner(
    *, args: tuple[str, ...], env: dict[str, str], timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        args,
        env=env,
        timeout=timeout,
        check=False,
        capture_output=True,
        text=True,
    )
