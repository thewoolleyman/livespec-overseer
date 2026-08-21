"""Protocol seams for the tmux boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

__all__: list[str] = ["PaneDriver", "SessionNameDriver", "WindowLayoutDriver"]


class SessionNameDriver(Protocol):
    """The tmux read needed by ``overseer-declare`` topic inference."""

    def pane_session_name(self, *, pane: str) -> str | None: ...


class PaneDriver(Protocol):
    """The tmux surface the daemon actually depends on — its injectable seam.

    :class:`tmuxio.TmuxIO` satisfies this structurally, and so does the beside-tests'
    ``FakeTmux``; neither declares it, because a ``Protocol`` is checked by shape
    rather than by inheritance (the project bans inheritance in favor of exactly
    this). Typing ``Supervisor.tmux`` as ``PaneDriver`` instead of ``object`` is
    what lets a type checker see through the seam at all.

    It declares the THIRTEEN methods the ``Supervisor`` calls, not all nineteen
    :class:`tmuxio.TmuxIO` exposes. The narrower surface is the point: it states what a
    substitute must implement to be substitutable, so a test double is complete
    when it satisfies this and not before. The seven omitted methods
    (``list_sessions``, ``split_window_top``, ``pane_exists``, ``set_pane_title``,
    ``select_layout_even``, ``set_pane_height_percent``, ``window_pane_titles``)
    drive the two-pane LAYOUT from the CLI entry points, which hold a concrete
    ``TmuxIO`` rather than reaching through this seam.
    """

    def capture_pane(self, *, session: str) -> str: ...

    def pane_id(self, *, session: str) -> str | None: ...

    def pane_by_title(self, *, pane: str, title: str) -> str | None: ...

    def pane_pid(self, *, session: str) -> int | None: ...

    def pane_current_command(self, *, session: str) -> str | None: ...

    def pane_current_path(self, *, session: str) -> str | None: ...

    def session_exists(self, *, session: str) -> bool: ...

    def pane_pid_sessions(self) -> dict[int, str]: ...

    def send_keys(self, *, session: str, keys: str) -> bool: ...

    def bracketed_paste(self, *, session: str, text: str) -> bool: ...

    def respawn_pane(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: Mapping[str, str | None] | None = None,
    ) -> bool: ...

    def new_session(self, *, name: str, cwd: str) -> bool: ...

    def kill_session(self, *, session: str) -> bool: ...

    def rename_window(self, *, pane: str, name: str) -> bool: ...


class WindowLayoutDriver(Protocol):
    """The tmux surface the two-pane BOOTSTRAP depends on — the launcher's seam.

    The counterpart to :class:`PaneDriver`, and the reason that one declares only
    twelve of :class:`tmuxio.TmuxIO`'s methods: these six are window-LAYOUT operations
    (split, title, resize, enumerate), used once at bootstrap by ``overseer-start``
    and never by the daemon's per-tick loop. Splitting the surfaces keeps each
    stated obligation honest — a daemon test double does not have to pretend it can
    resize a pane, and a launcher test double does not have to pretend it can paste.

    ``tmuxio.TmuxIO`` satisfies both structurally, being the one real implementation.
    """

    def window_pane_titles(self, *, pane: str) -> list[str]: ...

    def split_window_top(self, *, pane: str, cwd: str, command: str) -> str | None: ...

    def pane_exists(self, *, pane: str) -> bool: ...

    def set_pane_title(self, *, pane: str, title: str) -> bool: ...

    def select_layout_even(self, *, pane: str) -> bool: ...

    def pane_by_title(self, *, pane: str, title: str) -> str | None: ...

    def set_pane_height_percent(self, *, pane: str, percent: int) -> bool: ...
