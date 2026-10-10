"""terminal_probes.py — enumerating the panes each supported terminal instance owns.

The fact-gathering half of backend selection. :mod:`terminal_ownership` owns the
RULE and is pure; this module owns the two ENUMERATIONS that rule needs, one per
supported backend, and nothing else. Neither probe decides anything: each answers
"which panes does this one instance hold, which processes does it report for each,
and which live generation is answering?" and hands that back as a
:class:`terminal_ownership.ClaimReading`.

**An endpoint is a candidate, never a claim.** `endpoints` reads the environment
because that is the one thing `TMUX` and `HERDR_SOCKET_PATH` are good for here —
locating a socket worth probing. The values are inherited across `exec` and across
reparenting, so nothing downstream treats them as evidence; the invoking process's
ancestry does that, in the module above.

**The default tmux socket is the EMPTY endpoint, and that is the legacy
contract.** `SPECIFICATION/constraints.md` requires an unqualified legacy value to
keep selecting tmux rather than being reinterpreted, and the mechanical form of
that here is the absence of a `-S` argument: an empty endpoint produces exactly the
argv every existing call in :mod:`tmuxio` produces, so the default server keeps
being addressed the way it always was. A NAMED instance adds `-S <socket>` and
nothing else, which is what :class:`SocketScopedRun` exists to carry into the rest
of the tmux surface once an instance has been positively selected.

**Both probes bind the live GENERATION, not just the socket.** For tmux it is
`#{pid}` — the server's own pid, reported by the server that answered — paired with
that pid's `/proc` start time. For herdr it is the `SO_PEERCRED` pid the transport
already validates, paired with the same start-time read. The constraint is explicit
that a socket path alone is insufficient because a restart may reuse the path and
the pane ids; an unreadable start time therefore REFUSES rather than yielding a
half-identified instance.

**Every failure is fail-closed and SPECIFIC, and one shape deserves naming.** A
single pane whose process reading fails refuses the WHOLE instance rather than
being skipped. Skipping it would be indistinguishable, downstream, from "that pane
does not own us" — a silent downgrade of unreadable evidence to a negative answer,
which is precisely what the constraint forbids. Refusing names the pane instead,
and `terminal_ownership` surfaces that diagnostic whether or not another instance
verified.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import claude_sessions
import herdr_adapter
import herdr_identity
import terminal_ownership
from _seams import PidToOptionalStr
from tmux_process import TEXT_PROCESS_RUN, SocketScopedRun, TextProcess, TextProcessRun

__all__: list[str] = [
    "DEFAULT_TMUX_ENDPOINT",
    "HERDR_SOCKET_ENV",
    "PANE_ROW_FORMAT",
    "TEXT_PROCESS_RUN",
    "TMUX_ENV",
    "TMUX_TIMEOUT_SECONDS",
    "HerdrOwnershipProbe",
    "SocketScopedRun",
    "TextProcess",
    "TextProcessRun",
    "TmuxInstanceListing",
    "TmuxOwnershipProbe",
    "default_herdr_socket",
]

# tmux exports `TMUX` as `<socket-path>,<server-pid>,<session-id>`; only the first
# field names an endpoint, and the pid in it is NOT trusted — the server that
# answers reports its own.
TMUX_ENV = "TMUX"
HERDR_SOCKET_ENV = "HERDR_SOCKET_PATH"

# The default tmux server, addressed with no `-S` exactly as every legacy call in
# this package does. An empty string rather than a resolved path, because tmux
# derives that path itself from `TMUX_TMPDIR` and the uid, and re-deriving it here
# would be a second, drifting implementation of a decision tmux already makes.
DEFAULT_TMUX_ENDPOINT = ""

# `#{pid}` is the SERVER's pid as reported by the server that answered this
# socket; `#{pane_pid}` is the pane's own root process. Tab-separated because a
# pane id and two pids contain no tabs, while a space-separated format would be
# ambiguous if tmux ever padded a field.
PANE_ROW_FORMAT = "#{pane_id}\t#{pane_pid}\t#{pid}"
_PANE_ROW_FIELDS = 3

# The same liveness floor `tmuxio` uses, for the same reason: a local IPC round
# trip that exceeds it means tmux is not answering, which is a refusal rather than
# a slow success.
TMUX_TIMEOUT_SECONDS = 10.0

# Measured in `plan/herdr-overseer/research/002-herdr-api-evidence.md`: the default
# instance listens on `~/.config/herdr/herdr.sock`, and a `--session NAME` instance
# on `~/.config/herdr/sessions/NAME/herdr.sock`. Only the default is derived here;
# a named instance arrives through the environment, because its NAME is the
# operator's choice and nothing on disk declares which one is current.
_HERDR_CONFIG_DIR = ".config/herdr"
_HERDR_SOCKET_NAME = "herdr.sock"


def default_herdr_socket(*, home: Path | None = None) -> str:
    """The default herdr instance's socket path."""
    root = Path.home() if home is None else home
    return str(root / _HERDR_CONFIG_DIR / _HERDR_SOCKET_NAME)


def _with_declared(*, default: str, declared: str) -> tuple[str, ...]:
    """The default endpoint, plus the environment's if it names a different one."""
    return (default, declared) if declared and declared != default else (default,)


def _parsed_rows(*, stdout: str) -> tuple[tuple[str, int, int], ...] | None:
    """Every `(pane_id, pane_pid, server_pid)` triple, or None when any row is bad.

    None for ANY malformed row rather than for the row alone: a listing that cannot
    be read in full is unreadable evidence, and dropping the rows that happened to
    parse would silently narrow which panes this instance is believed to hold.
    """
    rows: list[tuple[str, int, int]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != _PANE_ROW_FIELDS:
            return None
        pane_id, pane_pid, server_pid = fields
        if not pane_id or not pane_pid.isdigit() or not server_pid.isdigit():
            return None
        rows.append((pane_id, int(pane_pid), int(server_pid)))
    return tuple(rows)


@dataclass(frozen=True, kw_only=True)
class TmuxInstanceListing:
    """One complete pane listing bound to the server generation that answered."""

    rows: tuple[tuple[str, int, int], ...]
    generation: tuple[int, str] | None
    error: str


@dataclass(frozen=True, kw_only=True)
class TmuxOwnershipProbe:
    """What one tmux instance holds, addressed by its socket and proven generation.

    `run` and `starttime_of` are injected for the reasons every seam in this
    package is: a test must be able to drive a server that exits non-zero, a
    binary that cannot be spawned, a listing that hangs, and a pid whose `/proc`
    start time has gone, none of which can be staged against a healthy server.
    """

    backend: str = herdr_identity.TMUX_BACKEND
    tmux_binary: str = "tmux"
    run: TextProcessRun = TEXT_PROCESS_RUN
    starttime_of: PidToOptionalStr = claude_sessions.proc_starttime
    timeout_seconds: float = TMUX_TIMEOUT_SECONDS

    def endpoints(self, *, environ: Mapping[str, str]) -> tuple[str, ...]:
        """The default server, plus the named one `TMUX` points at if it differs."""
        return _with_declared(
            default=DEFAULT_TMUX_ENDPOINT,
            declared=environ.get(TMUX_ENV, "").split(",")[0],
        )

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        """Every pane this instance holds, with its root process and generation."""
        listing = self.instance_listing(endpoint=endpoint)
        generation = listing.generation or (0, "")
        if listing.error:
            return terminal_ownership.ClaimReading(panes=(), error=listing.error)
        if not listing.rows:
            return terminal_ownership.ClaimReading(panes=(), error="")
        server_pid, starttime = generation
        return terminal_ownership.ClaimReading(
            panes=tuple(
                terminal_ownership.OwnedPane(
                    backend=self.backend,
                    socket_path=endpoint,
                    server_pid=server_pid,
                    server_starttime=starttime,
                    pane_id=pane_id,
                    pane_process_pids=(pane_pid,),
                )
                for pane_id, pane_pid, _ in listing.rows
            ),
            error="",
        )

    def instance_listing(self, *, endpoint: str) -> TmuxInstanceListing:
        """All panes and the exact live generation from one server answer."""
        stdout, error = self._listing(endpoint=endpoint)
        if error:
            return TmuxInstanceListing(rows=(), generation=None, error=error)
        rows = _parsed_rows(stdout=stdout)
        if rows is None:
            return TmuxInstanceListing(
                rows=(),
                generation=None,
                error=f"tmux pane listing on {endpoint or 'the default socket'} " "is unreadable",
            )
        if not rows:
            return TmuxInstanceListing(rows=(), generation=None, error="")
        servers = {server_pid for _, _, server_pid in rows}
        if len(servers) != 1:
            return TmuxInstanceListing(
                rows=(),
                generation=None,
                error=(
                    f"tmux pane listing names {len(servers)} distinct server pids "
                    f"{sorted(servers)}; one socket is one server"
                ),
            )
        server_pid = next(iter(servers))
        starttime = self.starttime_of(pid=server_pid)
        if starttime is None:
            return TmuxInstanceListing(
                rows=(),
                generation=None,
                error=(
                    f"tmux server generation is unreadable: no /proc start time for "
                    f"server pid {server_pid}"
                ),
            )
        return TmuxInstanceListing(
            rows=rows,
            generation=(server_pid, starttime),
            error="",
        )

    def _listing(self, *, endpoint: str) -> tuple[str, str]:
        """`list-panes -a` output for this instance, or why there is none.

        `OSError` covers a missing binary and every spawn fault;
        `subprocess.TimeoutExpired` subclasses `SubprocessError` rather than
        `OSError`, so it is named explicitly — without it the bound above would
        convert a wedged server into an uncaught exception. Both are the same fact
        to a caller: this instance did not answer.
        """
        scope = [] if endpoint == DEFAULT_TMUX_ENDPOINT else ["-S", endpoint]
        try:
            completed = self.run(
                [self.tmux_binary, *scope, "list-panes", "-a", "-F", PANE_ROW_FORMAT],
                input=None,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return "", f"tmux could not be run for {endpoint or 'the default socket'}: {exc}"
        if completed.returncode != 0:
            return "", (
                f"tmux did not answer for {endpoint or 'the default socket'} "
                f"(exit {completed.returncode})"
            )
        return completed.stdout or "", ""


@dataclass(frozen=True, kw_only=True)
class HerdrOwnershipProbe:
    """What one herdr instance holds, addressed by its socket and proven generation.

    `adapter` is the observation surface rather than a socket, so this probe owns
    no I/O of its own: identification, the deadline, the peer validation and the
    pane-echo guards all belong to :mod:`herdr_adapter` and are reused here rather
    than restated.
    """

    backend: str = herdr_identity.HERDR_BACKEND
    adapter: herdr_adapter.OwnershipObserver = field(default_factory=herdr_adapter.HerdrAdapter)
    home: Path | None = None

    def endpoints(self, *, environ: Mapping[str, str]) -> tuple[str, ...]:
        """The default instance, plus the one `HERDR_SOCKET_PATH` names if it differs."""
        return _with_declared(
            default=default_herdr_socket(home=self.home),
            declared=environ.get(HERDR_SOCKET_ENV, ""),
        )

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        """Every pane this instance holds, with its shell, leader and generation."""
        identified = self.adapter.identify(socket_path=endpoint)
        if identified.peer is None:
            return terminal_ownership.ClaimReading(
                panes=(),
                error=identified.error
                or f"herdr instance on {endpoint} reported no server generation",
            )
        probe_target = herdr_identity.HerdrPaneTarget(
            socket_path=endpoint,
            server_pid=identified.peer.pid,
            server_starttime=identified.peer.starttime,
            pane_id="",
        )
        listing = self.adapter.list_panes(target=probe_target)
        if not listing.ok:
            return terminal_ownership.ClaimReading(panes=(), error=listing.error)
        panes: list[terminal_ownership.OwnedPane] = []
        for row in listing.panes:
            reading = self.adapter.foreground(target=replace(probe_target, pane_id=row.pane_id))
            if reading.process is None:
                return terminal_ownership.ClaimReading(
                    panes=(),
                    error=(
                        f"herdr pane {row.pane_id!r} on {endpoint} has no readable "
                        f"process: {reading.error}"
                    ),
                )
            panes.append(
                terminal_ownership.OwnedPane(
                    backend=self.backend,
                    socket_path=endpoint,
                    server_pid=probe_target.server_pid,
                    server_starttime=probe_target.server_starttime,
                    pane_id=row.pane_id,
                    # Both, de-duplicated: an IDLE pane reports its retained shell
                    # as its own foreground leader, and the same pid offered twice
                    # is one candidate rather than two.
                    pane_process_pids=tuple(
                        dict.fromkeys((reading.process.shell_pid, reading.process.process_group_id))
                    ),
                )
            )
        return terminal_ownership.ClaimReading(panes=tuple(panes), error="")
