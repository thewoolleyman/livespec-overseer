"""Importable entry point for the dedicated overseer daemon.

Run it with NO subcommands: it starts the deterministic supervisor daemon watching
every livespec fleet member. Its ONE option is ``--warn-percent N`` (int in [1, 99],
the daemon-wide default wind-down threshold; a per-track ``ctx_threshold`` still wins).
The command IS the daemon — there is nothing else to type. (Track management — list /
add / remove / unassign / start — is the supervisor MODULE, invoked one-shot from the
``/overseer`` skill, NOT this executable.)

Path discovery is self-contained so it "just works" from any working directory:
  * this module's own directory is pinned onto ``sys.path`` below, so
    ``import supervisor`` (and supervisor's sibling ``registry`` / ``signals`` /
    ``tmuxio``) resolve regardless of cwd or how the console script launches;
  * the watch-set is read from an ABSOLUTE ``$HOME`` path
    (``~/.livespec-overseer-repos.json``), so it resolves identically from any
    cwd AND from any location this package is installed to;
  * the mapping store + injection-stamp paths are the hard-coded ``$HOME``
    defaults, beside that same declaration.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streams
import supervisor  # intentionally after the sys.path pin above

__all__: list[str] = ["main"]

# A remaining-context percent. 0 would mean "warn only once context is gone", and
# 100 would mean "warn immediately, always" — neither is a threshold anyone wants,
# so the range is open at both ends rather than clamped.
_MIN_WARN_PERCENT = 1
_MAX_WARN_PERCENT = 99


def _default_daemon_log_path() -> Path:
    """Default daemon event-history log beside this checkout."""
    return Path(__file__).resolve().parent.parent / "tmp" / "overseer" / "daemon.log"


@contextmanager
def _native_daemon_stderr(*, log_path: Path) -> Iterator[None]:
    """Append daemon stderr to its event-history log for bare manual bounces."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    previous_stderr = sys.stderr
    with log_path.open("a", encoding="utf-8", buffering=1) as log_file:
        sys.stderr = log_file
        try:
            yield
        finally:
            sys.stderr = previous_stderr


def _warn_percent(value: str) -> int:
    """argparse type: an int in [1, 99] (a remaining-context percent)."""
    ivalue = int(value)  # raises ValueError → argparse surfaces a clear error
    if not _MIN_WARN_PERCENT <= ivalue <= _MAX_WARN_PERCENT:
        # TRY003: argparse's contract is that this exception's MESSAGE is the text
        # the user sees on a bad flag, so it has to carry the context. There is no
        # per-case exception subclass to move it into.
        raise argparse.ArgumentTypeError(  # noqa: TRY003 — argparse surfaces this text verbatim
            f"--warn-percent must be an integer in "
            f"[{_MIN_WARN_PERCENT}, {_MAX_WARN_PERCENT}], got {ivalue}"
        )
    return ivalue


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="overseerd",
        description="the livespec overseer daemon (watches the whole fleet)",
    )
    _ = parser.add_argument(
        "--warn-percent",
        type=_warn_percent,
        default=None,
        metavar="N",
        help=(
            "daemon-wide default remaining-context %% at which the first wrap-up "
            "fires (default 50); a per-track override still wins"
        ),
    )
    args = parser.parse_args(argv)
    with _native_daemon_stderr(log_path=_default_daemon_log_path()):
        streams.write_stderr(text=f"{supervisor.iso_now()} overseer: daemon log opened\n")
        return supervisor.run_daemon(warn_percent=args.warn_percent)


if __name__ == "__main__":
    raise SystemExit(main())
