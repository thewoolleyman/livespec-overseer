"""Importable entry point for the dedicated overseer daemon.

Run it with NO subcommands: it starts the deterministic supervisor daemon watching
every livespec fleet member. It takes TWO options, both daemon-wide defaults:
``--warn-percent N`` (int in [1, 99], the wind-down threshold; a per-track
``ctx_threshold`` still wins) and ``--idle-nudge {on,off}`` (whether an idle session
still holding context gets the keep-going nudge). Neither is required, and the defaults
are what the daemon has always done. The command IS the daemon — there is nothing else
to type. (Track management — list / add / remove / unassign / start — is the supervisor
MODULE, invoked one-shot from the ``/overseer`` skill, NOT this executable.)

``--idle-nudge off`` switches off ONE keystroke and no more: the low-context wrap-up and
the cardinal-rule restart-on-``ready`` are unconditional and stay that way. It is not a
"stop typing into my pane" switch.

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

import _supervisor_diagnostics
import daemon_log
import start
import supervisor  # intentionally after the sys.path pin above

__all__: list[str] = ["default_daemon_log_path", "main"]

# A remaining-context percent. 0 would mean "warn only once context is gone", and
# 100 would mean "warn immediately, always" — neither is a threshold anyone wants,
# so the range is open at both ends rather than clamped.
_MIN_WARN_PERCENT = 1
_MAX_WARN_PERCENT = 99


def _default_daemon_log_path() -> Path:
    """Backward-compatible private wrapper for the daemon log resolver."""
    return default_daemon_log_path()


def default_daemon_log_path() -> Path:
    """Default daemon event-history log beside the operator checkout when present."""
    return start.default_core_root() / "tmp" / "overseer" / daemon_log.HISTORY_FILENAME


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


def _help_epilog() -> str:
    log_path = _default_daemon_log_path()
    retention = daemon_log.DEFAULT_RETENTION
    oldest = retention.retained_generations
    return f"""\
Daemon event history:
  default log path: {log_path}
  The path follows the checkout the daemon was imported from and resolves to that
  checkout tmp/overseer/daemon.log, not the caller's current directory. If this
  help output disagrees with the acting daemon, the status file's
  daemon_package.package_dir names the checkout that daemon is actually running.

Event-history retention:
  The log is BOUNDED, not append-forever. The active file is rotated once the next
  write would take it past {retention.max_active_bytes} bytes; daemon.log becomes
  daemon.log.1, every retained generation shifts one older, and the generation past
  the bound is deleted. {oldest} retained generations are kept, so the whole history
  occupies at most {retention.total_bytes} bytes — roughly five days at the growth
  rate measured on 2026-09-11 (~190 MB/day).
  Recovery: generation 1 is the NEWEST retained history and daemon.log.{oldest} the
  oldest, so `cat daemon.log.{oldest} ... daemon.log.1 daemon.log` replays the whole
  retained history oldest-first. A daemon.log that is ALREADY over the bound when the
  daemon starts is migrated rather than discarded: its newest whole records are copied
  into daemon.log.1 and a fresh active file is opened, so the oversized file is
  released by that hand-off and never truncated underneath a writer still holding it.

OpenTelemetry export:
  OTEL_EXPORTER_OTLP_ENDPOINT
      OTLP/HTTP endpoint. With no endpoint set, export is disabled; the daemon
      remains local only and emits its event history to daemon.log.
  OTEL_SERVICE_NAME
      Service name override. Default: livespec-overseer.
      The service namespace is livespec-family.
  HONEYCOMB_INGEST_KEY_LIVESPEC
      Optional Honeycomb ingest key, sent as the x-honeycomb-team header.
      Prefer pointing OTEL_EXPORTER_OTLP_ENDPOINT at a host-local OTLP receiver
      and keeping this key out of the daemon environment. Direct-to-Honeycomb is
      the fallback when no receiver exists. If you export the key before starting
      overseerd, remember that overseerd's children inherit its environment; when
      that invocation starts the tmux server, supervised panes can inherit it too.
"""


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="overseerd",
        description="the livespec overseer daemon (watches the whole fleet)",
        epilog=_help_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    _ = parser.add_argument(
        "--idle-nudge",
        choices=["on", "off"],
        default="on",
        help=(
            "daemon-wide switch for the keep-going nudge sent to a session that has "
            "gone idle while still holding context (default on). `off` suppresses that "
            "nudge for every track; the low-context wrap-up and the restart-on-ready "
            "interlock are NOT affected and cannot be switched off"
        ),
    )
    args = parser.parse_args(argv)
    # The daemon OWNS its event history for the life of the process: this takes
    # `sys.stderr` and the stderr descriptor, migrates a pre-existing over-bound log,
    # and keeps every later write inside the finite retention bound. A bare manual
    # bounce therefore preserves the history with no shell redirect of its own, and the
    # launcher's `2>>` redirect is superseded rather than depended on.
    with daemon_log.bounded_daemon_history(log_path=_default_daemon_log_path()) as salvaged:
        _supervisor_diagnostics.log(message="daemon log opened")
        if salvaged:
            _supervisor_diagnostics.log(
                event="daemon-log-migrated",
                message=(
                    f"migrated an over-bound daemon log: salvaged {salvaged} bytes of its "
                    "newest records into daemon.log.1"
                ),
                fields={"salvaged_bytes": salvaged},
            )
        return supervisor.run_daemon(
            warn_percent=args.warn_percent, idle_nudge=args.idle_nudge == "on"
        )


if __name__ == "__main__":
    raise SystemExit(main())
