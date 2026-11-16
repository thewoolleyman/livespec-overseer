"""Remote Control reissue tasks for hosts whose delivery changed accounts."""

from __future__ import annotations

from collections.abc import Callable

import streams
from caam_delivery_push_state import Host, scrubbed

__all__: list[str] = ["reissue_task"]


def reissue_task(
    *,
    host: Host,
    perform: Callable[[], str],
    token: str,
) -> Callable[[], None]:
    """Return a task that reports a redacted Remote Control reissue result.

    The task runs on a daemon thread, so a failure there is reported as that
    host's line rather than ending the thread with a bare traceback. The caught
    types are the ones its steps raise: OSError from ssh, the subprocess or a
    broken stdout pipe, and RuntimeError from Path.expanduser with no home.
    """

    def task() -> None:
        try:
            line = perform()
            streams.write_stdout(
                text=f"remote-control {host.label}: {scrubbed(text=line, token=token)}\n"
            )
        except (OSError, RuntimeError) as error:
            streams.write_stdout(
                text=f"remote-control {host.label}: failed {type(error).__name__}\n"
            )

    return task
