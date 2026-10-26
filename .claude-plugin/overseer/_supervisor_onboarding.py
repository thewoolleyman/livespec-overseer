"""Claude Code first-run onboarding classification and bounded resolution.

The three accepted transcripts below are the Claude Code v2.1.310 first-run
screens.  They are intentionally whole-screen matches: a partial, changed, or
otherwise unfamiliar capture is ambiguous evidence, not authority to send a key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_active_models import ActiveDecision

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_evaluate_active import ActiveRequest

__all__: list[str] = [
    "ONBOARDING_CONDITION",
    "OnboardingDecision",
    "OnboardingRequest",
    "OnboardingScreen",
    "active_decision",
    "onboarding_decision",
]

ONBOARDING_CONDITION = "blocked-onboarding"
_THEME = "theme picker"
_SECURITY = "security-notes screen"
_TRUST = "workspace-trust prompt"
_THEME_LINES = (
    "Let's get started.",
    "Choose the text style that looks best with your terminal",
    "❯ Dark mode",
    "  Light mode",
    "  Dark mode (colorblind-friendly)",
    "  Light mode (colorblind-friendly)",
    "To change this later, run /theme",
)
_SECURITY_LINES = (
    "Security notes:",
    "1. Claude can make mistakes",
    "You should always review Claude's responses, especially when running code.",
    "2. Due to prompt injection risks, only use it with code you trust",
    "For more details see:",
    "https://code.claude.com/docs/en/security",
    "Press Enter to continue…",
)
_TRUST_PREFIX = (
    "Accessing workspace:",
    (
        "Quick safety check: Is this a project you created or one you trust? "
        "(Like your own code, a well-known"
    ),
    (
        "open source project, or work from your team). If not, take a moment "
        "to review what's in this folder first."
    ),
    "Claude Code'll be able to read, edit, and execute files here.",
    "Security guide",
)
_TRUST_EXIT = ("❯ No, exit", "  Yes, I trust this folder")
_TRUST_ACCEPT = ("  No, exit", "❯ Yes, I trust this folder")


@dataclass(frozen=True, kw_only=True)
class OnboardingScreen:
    """One exact first-run screen and its actionable selection, if any."""

    name: str
    folder: str | None = None
    selection: str | None = None


@dataclass(frozen=True, kw_only=True)
class OnboardingDecision:
    """The distinct waiting status and active condition for one onboarding screen."""

    note: str
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class OnboardingRequest:
    """All trusted inputs needed to classify and, only when allowed, resolve a screen."""

    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    capture: str
    is_codex: bool
    act: bool


def onboarding_decision(*, request: OnboardingRequest) -> OnboardingDecision | None:
    """Classify one exact Claude first-run screen and perform its bounded action."""
    if request.is_codex:
        return None
    screen = _screen(capture=request.capture)
    if screen is None:
        return None
    note = _note(screen=screen)
    if request.act:
        _alert(request=request, note=note)
        _resolve(request=request, screen=screen)
    return OnboardingDecision(note=note, active_conditions={ONBOARDING_CONDITION})


def _screen(*, capture: str) -> OnboardingScreen | None:
    """Recognise exactly one known transcript, rejecting partial or conflicting text."""
    lines = _lines(capture=capture)
    named_screens: dict[tuple[str, ...], str] = {
        _THEME_LINES: _THEME,
        _SECURITY_LINES: _SECURITY,
    }
    name = named_screens.get(lines)
    if name is not None:
        return OnboardingScreen(name=name)
    return _trust_screen(lines=lines)


def active_decision(*, request: ActiveRequest) -> ActiveDecision | None:
    """Publish the onboarding outcome in the evaluator's active-result shape."""
    onboarding = onboarding_decision(
        request=OnboardingRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.target,
            capture=request.capture,
            is_codex=request.obs.is_codex,
            act=request.act,
        )
    )
    if onboarding is None:
        return None
    return ActiveDecision(
        status=ONBOARDING_CONDITION,
        note=onboarding.note,
        ready=request.ready,
        blocked=request.blocked,
        blocked_age=request.blocked_age,
        blocked_age_label=request.blocked_age_label,
        active_conditions=onboarding.active_conditions,
    )


def _trust_screen(*, lines: tuple[str, ...]) -> OnboardingScreen | None:
    """Recognise the workspace-trust screen and its current selection exactly."""
    if len(lines) != len(_TRUST_PREFIX) + 3 or lines[0] != _TRUST_PREFIX[0]:
        return None
    folder = lines[1]
    if not folder.startswith("/") or tuple(lines[2:6]) != _TRUST_PREFIX[1:]:
        return None
    options = tuple(lines[6:])
    if options == _TRUST_EXIT:
        return OnboardingScreen(name=_TRUST, folder=folder, selection="exit")
    if options == _TRUST_ACCEPT:
        return OnboardingScreen(name=_TRUST, folder=folder, selection="accept")
    return None


def _lines(*, capture: str) -> tuple[str, ...]:
    """The ANSI-free complete display, preserving meaningful option indentation."""
    lines = [signals.strip_ansi(text=line).rstrip() for line in capture.splitlines()]
    while lines and not lines[0]:
        _ = lines.pop(0)
    while lines and not lines[-1]:
        _ = lines.pop()
    return tuple(line for line in lines if line)


def _note(*, screen: OnboardingScreen) -> str:
    if screen.folder is None:
        return screen.name
    return f"{screen.name} for {screen.folder}"


def _alert(*, request: OnboardingRequest, note: str) -> None:
    """Emit the track-scoped first-observation event through the alert edge."""
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=f"first-run onboarding {note}",
        condition=ONBOARDING_CONDITION,
    )


def _resolve(*, request: OnboardingRequest, screen: OnboardingScreen) -> None:
    """Send only a re-read-safe key sequence for a recognised, owned screen."""
    if screen.name in (_THEME, _SECURITY):
        _send_if_same(request=request, expected=screen, key="Enter")
    elif screen.folder == request.track.repo and screen.selection == "exit":
        _send_if_same(request=request, expected=screen, key="Down")
        accepted = OnboardingScreen(name=_TRUST, folder=screen.folder, selection="accept")
        _send_if_same(request=request, expected=accepted, key="Enter")


def _send_if_same(*, request: OnboardingRequest, expected: OnboardingScreen, key: str) -> None:
    """Re-read before one key and record only a keystroke the terminal accepted."""
    reread = _screen(capture=request.sup.tmux.capture_pane(session=request.pane))
    if reread != expected or not request.sup.tmux.send_keys(session=request.pane, keys=key):
        return
    request.sup.log(
        event="onboarding-keystroke",
        message=f"sent {key} for {expected.name} on pane {request.pane}",
        repo=request.track.repo,
        topic=request.track.topic,
        fields={"pane": request.pane, "screen": expected.name, "key": key},
    )
