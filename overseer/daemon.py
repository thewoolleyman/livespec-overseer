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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import supervisor  # intentionally after the sys.path pin above

__all__ = ["main"]

# A remaining-context percent. 0 would mean "warn only once context is gone", and
# 100 would mean "warn immediately, always" — neither is a threshold anyone wants,
# so the range is open at both ends rather than clamped.
_MIN_WARN_PERCENT = 1
_MAX_WARN_PERCENT = 99


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
    return supervisor.run_daemon(warn_percent=args.warn_percent)


if __name__ == "__main__":
    raise SystemExit(main())
