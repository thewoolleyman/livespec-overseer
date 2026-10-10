"""The tmux window-layout concern shared by bootstrap and legacy callers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeGuard

import tmux_process
from tmuxio_protocols import PaneGeometry

__all__: list[str] = ["TmuxLayout"]


def _ok(*, completed: tmux_process.TextProcess | None) -> TypeGuard[tmux_process.TextProcess]:
    return completed is not None and completed.returncode == 0


@dataclass(frozen=True, kw_only=True)
class TmuxLayout:
    """One typed layout view over an already selected tmux command boundary."""

    call: tmux_process.TmuxCall
    split_size: tuple[str, ...] = ()

    def split_window_top(self, *, pane: str, cwd: str, command: str) -> str | None:
        """Split PANE's window; new pane ABOVE, focus stays on PANE; run COMMAND in CWD.

        ``-v`` splits top/bottom, ``-b`` puts the NEW pane before (above) the
        target, ``-d`` keeps focus on the target (the bottom Claude pane), and
        ``-P -F '#{pane_id}'`` prints the new pane id. Targeting ``pane`` (the
        skill's own ``$TMUX_PANE``) means the daemon pane is created in the
        skill's OWN window — never in a session grabbed by name. Returns the new
        pane id (e.g. ``%47``) or None on failure.
        """
        completed = self.call(
            args=[
                "split-window",
                "-v",
                "-b",
                "-d",
                *self.split_size,
                "-P",
                "-F",
                "#{pane_id}",
                "-t",
                pane,
                "-c",
                cwd,
                command,
            ]
        )
        if not _ok(completed=completed):
            return None
        return (completed.stdout or "").strip() or None

    def pane_exists(self, *, pane: str) -> bool:
        """Whether PANE is still present in the tmux server."""
        completed = self.call(args=["list-panes", "-a", "-F", "#{pane_id}"])
        if not _ok(completed=completed):
            return False
        return pane in {line.strip() for line in (completed.stdout or "").splitlines()}

    def set_pane_title(self, *, pane: str, title: str) -> bool:
        """``tmux select-pane -t <pane> -T <title>`` — tag a pane (idempotency)."""
        return _ok(completed=self.call(args=["select-pane", "-t", pane, "-T", title]))

    def select_layout_even(self, *, pane: str) -> bool:
        """``tmux select-layout -t <pane> even-vertical`` — restack the window evenly.

        A THIRD pane that was opened and later closed leaves tmux's rows
        redistributed unevenly. Running this on every ``overseer-start`` normalizes
        the window (targeting ``pane`` targets its window) BEFORE
        :meth:`set_pane_height_percent` gives the daemon its share — so the resize
        starts from a known stack rather than whatever a stray pane left behind.
        """
        return _ok(completed=self.call(args=["select-layout", "-t", pane, "even-vertical"]))

    def pane_by_title(self, *, pane: str, title: str) -> str | None:
        """The pane id in PANE's window whose title is TITLE (``None`` if absent).

        The idempotent-path counterpart of :meth:`window_pane_titles`: that answers
        "is the daemon pane here?", this answers "which pane IS it?" — needed to
        target the daemon pane for a resize when ``overseer-start`` re-runs and did
        not create it (so never held its id).
        """
        completed = self.call(args=["list-panes", "-t", pane, "-F", "#{pane_id}\t#{pane_title}"])
        if not _ok(completed=completed):
            return None
        for line in (completed.stdout or "").splitlines():
            pane_id, _, pane_title = line.partition("\t")
            if pane_title.strip() == title:
                return pane_id.strip() or None
        return None

    def _window_pane_geometries(self, *, pane: str, complete: bool) -> list[PaneGeometry]:
        """Read either legacy vertical geometry or complete pane rectangles."""
        fields = (
            "#{pane_id}\t#{pane_left}\t#{pane_top}\t#{pane_width}\t#{pane_height}"
            if complete
            else "#{pane_id}\t#{pane_top}\t#{pane_height}"
        )
        completed = self.call(args=["list-panes", "-t", pane, "-F", fields])
        if not _ok(completed=completed):
            return []
        geometries: list[PaneGeometry] = []
        for line in (completed.stdout or "").splitlines():
            pane_id, *raw_coordinates = line.split("\t")
            try:
                coordinates = [int(value.strip()) for value in raw_coordinates]
                if complete:
                    left, top, width, height = coordinates
                else:
                    top, height = coordinates
                    left, width = 0, 1
                if complete and (left < 0 or top < 0 or width < 1 or height < 1):
                    return []
                geometries.append(
                    PaneGeometry(
                        pane=pane_id.strip(),
                        left=left,
                        top=top,
                        width=width,
                        height=height,
                    )
                )
            except ValueError:
                return []
        return geometries

    def window_pane_geometries(self, *, pane: str) -> list[PaneGeometry]:
        """Every pane id, top row, and height in PANE's window.

        The two-pane overseer contract is geometric: the daemon must occupy the
        TOP pane. Pane indexes are intentionally not used because tmux renumbers
        panes after a collapse, silently retargeting index-based commands.
        """
        return self._window_pane_geometries(pane=pane, complete=False)

    def window_pane_rectangles(self, *, pane: str) -> list[PaneGeometry]:
        """Every complete pane rectangle in PANE's window.

        Public bootstrap uses this generation-bound read so a full-height pane
        beside the caller cannot be mistaken for another daemon candidate above
        it. The legacy vertical reader remains unchanged for its older callers.
        """
        return self._window_pane_geometries(pane=pane, complete=True)

    def set_pane_height_percent(self, *, pane: str, percent: int) -> bool:
        """``tmux resize-pane -t <pane> -y <percent>%`` — size PANE within its window.

        Percentage sizes are a tmux feature (verified on 3.5a), so the legacy split
        does not have to be recomputed in rows against a window height that changes
        whenever the terminal is resized.
        """
        return _ok(completed=self.call(args=["resize-pane", "-t", pane, "-y", f"{percent}%"]))

    def rename_window(self, *, pane: str, name: str) -> bool:
        """Rename PANE's window to NAME, and PIN the name (``automatic-rename off``).

        Pinning is part of renaming, not an optional extra: tmux otherwise re-derives a
        window's name from its foreground command on the next tick and silently
        overwrites NAME. Both steps must succeed for the rename to hold.
        """
        if not _ok(completed=self.call(args=["rename-window", "-t", pane, name])):
            return False
        return _ok(
            completed=self.call(args=["set-window-option", "-t", pane, "automatic-rename", "off"])
        )

    def window_pane_titles(self, *, pane: str) -> list[str]:
        """Every pane title in PANE's window (``[]`` on error) — the idempotency read."""
        completed = self.call(args=["list-panes", "-t", pane, "-F", "#{pane_title}"])
        if not _ok(completed=completed):
            return []
        return [line for line in (completed.stdout or "").splitlines() if line.strip()]
