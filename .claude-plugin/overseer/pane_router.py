"""Route durable pane coordinates to their recorded terminal instance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, cast

import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_write
from tmuxio_protocols import PaneDriver

__all__: list[str] = ["MixedPaneDriver"]


class HerdrObserver(Protocol):
    def list_panes(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.PaneListing: ...

    def capture_pane(
        self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
    ) -> herdr_adapter.PaneCapture: ...

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading: ...


class HerdrInput(Protocol):
    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome: ...

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome: ...


@dataclass(kw_only=True)
class MixedPaneDriver:
    """A pane driver that resolves each qualified Herdr coordinate independently."""

    tmux: PaneDriver
    herdr: HerdrObserver = field(default_factory=herdr_adapter.HerdrAdapter)
    herdr_writer: HerdrInput = field(default_factory=herdr_write.HerdrWriter)
    coordinates: set[str] = field(default_factory=set)

    def _herdr_target(self, *, value: str) -> herdr_identity.HerdrPaneTarget | None:
        target = herdr_identity.decode_target(value=value).herdr
        if target is not None:
            self.coordinates.add(value)
        return target

    def capture_pane(self, *, session: str) -> str:
        target = self._herdr_target(value=session)
        if target is None:
            return self.tmux.capture_pane(session=session)
        return self.herdr.capture_pane(target=target, retain_ansi=True).text

    def pane_id(self, *, session: str) -> str | None:
        target = self._herdr_target(value=session)
        if target is None:
            return self.tmux.pane_id(session=session)
        return session

    def _foreground(self, *, session: str) -> herdr_adapter.ForegroundReading | None:
        target = self._herdr_target(value=session)
        return None if target is None else self.herdr.foreground(target=target)

    def pane_pid(self, *, session: str) -> int | None:
        reading = self._foreground(session=session)
        if reading is None:
            return self.tmux.pane_pid(session=session)
        return cast(int | None, getattr(reading.process, "shell_pid", None))

    def pane_current_command(self, *, session: str) -> str | None:
        reading = self._foreground(session=session)
        if reading is None:
            return self.tmux.pane_current_command(session=session)
        return cast(str | None, getattr(reading.process, "name", None))

    def pane_current_path(self, *, session: str) -> str | None:
        reading = self._foreground(session=session)
        if reading is None:
            return self.tmux.pane_current_path(session=session)
        return cast(str | None, getattr(reading.process, "cwd", None))

    def session_exists(self, *, session: str) -> bool:
        target = self._herdr_target(value=session)
        if target is None:
            return self.tmux.session_exists(session=session)
        listing = self.herdr.list_panes(target=target)
        return listing.ok and any(pane.pane_id == target.pane_id for pane in listing.panes)

    def pane_pid_sessions(self) -> dict[int, str]:
        out = self.tmux.pane_pid_sessions()
        for coordinate in self.coordinates:
            target = cast(
                herdr_identity.HerdrPaneTarget,
                herdr_identity.decode_target(value=coordinate).herdr,
            )
            process = cast(
                herdr_calls.ForegroundProcess,
                self.herdr.foreground(target=target).process,
            )
            out[process.shell_pid] = coordinate
            out[process.process_group_id] = coordinate
        return out

    def submit_prompt_once(self, *, session: str, text: str) -> tuple[bool, bool]:
        """Use Herdr's retained-shell-checked writes once, without uncertain replay."""
        target = cast(herdr_identity.HerdrPaneTarget, self._herdr_target(value=session))
        pasted = self.herdr_writer.bracketed_paste(target=target, text=text)
        submitted = self.herdr_writer.send_enter(target=target)
        return all((pasted.ok, submitted.ok)), not pasted.ok
