"""Rendered statusline model parsing and mismatch checks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "STATUSLINE_BASELINE_ABSENT_CONDITION",
    "STATUSLINE_MISMATCH_CONDITION",
    "rendered_statusline_model",
    "restart_blocked_by_statusline_mismatch",
    "statusline_baseline_absent",
    "statusline_model_disagreement",
]

# The alert condition a standing recorded-vs-rendered disagreement raises. Named so
# the evaluate cascade can register it as an ACTIVE condition while the disagreement
# holds, which is what keeps the edge-triggered alert (invariant 10) from re-arming
# every tick — `clear_alert_conditions` retains an alerted key only while its
# condition is active, and re-arms it the moment the disagreement clears.
STATUSLINE_MISMATCH_CONDITION = "statusline-model-mismatch"

# The alert condition a PROFILED-but-UNBASELINED track raises at restart. DISTINCT
# from both `STATUSLINE_MISMATCH_CONDITION` and `statusline-model-unreadable`,
# deliberately: those two report a recorded-versus-rendered COMPARISON, and this
# shape has no recorded side for a comparison to have happened against. Registered
# as an ACTIVE condition by the evaluate cascade on the same terms as the mismatch,
# so the alert fires once per unbaselined episode and re-arms when a baseline lands.
STATUSLINE_BASELINE_ABSENT_CONDITION = "statusline-baseline-absent"

_STATUSLINE_CTX_RE = re.compile(r"(?:Ctx:|Context)\s*\d+%\s*left")
_MIN_STATUSLINE_PARTS = 3
_STATUSLINE_TAIL_ROWS = 4


def _tail_non_empty_lines(*, capture: str) -> list[str]:
    out: list[str] = []
    for raw in reversed(capture.splitlines()):
        line = signals.strip_ansi(text=raw).strip()
        if line:
            out.append(line)
            if len(out) >= _STATUSLINE_TAIL_ROWS:
                break
    out.reverse()
    return out


def _statusline_parts(*, line: str) -> list[str]:
    separator = "·" if "·" in line else "|"
    return [part.strip() for part in line.split(separator)]


def _has_statusline_shape(*, parts: list[str]) -> bool:
    if len(parts) < _MIN_STATUSLINE_PARTS:
        return False
    model, cwd, *rest = parts
    return (
        bool(model)
        and cwd.startswith(("/", "~"))
        and any(_STATUSLINE_CTX_RE.search(part) for part in rest)
    )


def rendered_statusline_model(*, capture: str) -> str | None:
    """Best-effort rendered model segment from the runtime statusline."""
    for line in reversed(_tail_non_empty_lines(capture=capture)):
        parts = _statusline_parts(line=line)
        if _has_statusline_shape(parts=parts):
            return parts[0]
    return None


def statusline_model_disagreement(
    *,
    capture: str,
    model_profile: Mapping[str, str | None] | None,
) -> tuple[str, str] | None:
    """Return ``(recorded, rendered)`` only for a resolved disagreement."""
    recorded = None if model_profile is None else model_profile.get("statusline_model")
    rendered = rendered_statusline_model(capture=capture)
    if not recorded or rendered is None or rendered == recorded:
        return None
    return recorded, rendered


def _recorded_statusline_model(*, model_profile: Mapping[str, str | None] | None) -> str | None:
    return None if model_profile is None else model_profile.get("statusline_model")


def _recorded_launch_model(*, model_profile: Mapping[str, str | None] | None) -> str | None:
    return None if model_profile is None else model_profile.get("model")


def statusline_baseline_absent(*, model_profile: Mapping[str, str | None] | None) -> bool:
    """True for a track that HAS a launch profile but NO statusline baseline.

    A row carrying NO recorded profile at all is a DIFFERENT case and is excluded
    here: its relaunch is the fail-soft bare command, which re-asserts no model, so
    there is nothing unverified to report about it. The population this admits is the
    one the launch-profile text refuses to call verified — a reserved foreman or
    grooming seat born from ``registration_model_profile`` (which emits harness, model
    and wrapper and no baseline), a track adopted against an unreadable pane, or one
    whose wrap-up refresh could never fill the key.
    """
    return model_profile is not None and not model_profile.get("statusline_model")


def _alert_unreadable_statusline(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
    recorded: str,
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=(
            "statusline model unreadable: "
            f"{track.repo}::{track.topic} has recorded model {recorded!r}, "
            "but no rendered statusline model could be read; "
            "restart is proceeding fail-soft"
        ),
        condition="statusline-model-unreadable",
    )


def _alert_baseline_absent(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
    launch_model: str | None,
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=(
            "statusline model unverified: "
            f"{track.repo}::{track.topic} has no recorded statusline verification "
            f"baseline, so the re-asserted launch model {launch_model!r} was never "
            "checked against the running session; restart is proceeding unverified"
        ),
        condition=STATUSLINE_BASELINE_ABSENT_CONDITION,
    )


def _alert_statusline_mismatch(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
    recorded: str,
    rendered: str,
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=(
            "statusline model mismatch: "
            f"{track.repo}::{track.topic} has "
            f"recorded model {recorded!r}, rendered model {rendered!r}; "
            "skipping restart and keeping the ready declaration"
        ),
        condition=STATUSLINE_MISMATCH_CONDITION,
    )


def restart_blocked_by_statusline_mismatch(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
) -> bool:
    """Surface and veto only a resolved recorded-vs-rendered model disagreement.

    Three shapes reach here and they stay DISTINGUISHABLE. A resolved disagreement
    vetoes. A recorded baseline whose render cannot be read raises
    ``statusline-model-unreadable`` and proceeds. A track that carries a launch
    profile but NO baseline raises ``STATUSLINE_BASELINE_ABSENT_CONDITION`` and
    proceeds — never the unreadable alert, whose text reports a comparison that in
    that shape never happened. A row with no recorded profile at all raises nothing;
    it re-asserts no model, so it has nothing unverified to report.
    """
    capture = sup.tmux.capture_pane(session=target)
    disagreement = statusline_model_disagreement(
        capture=capture,
        model_profile=track.model_profile,
    )
    if disagreement is not None:
        recorded, rendered = disagreement
        _alert_statusline_mismatch(
            sup=sup,
            track=track,
            target=target,
            session=session,
            recorded=recorded,
            rendered=rendered,
        )
        return True

    # An unbaselined track has nothing to compare against, so this can never be a
    # veto — but it must not be SILENT either, which is what it used to be. Raise the
    # distinct baseline-absent condition and still return False: the restart proceeds
    # exactly as before, and nothing is mutated on the restart path.
    if statusline_baseline_absent(model_profile=track.model_profile):
        _alert_baseline_absent(
            sup=sup,
            track=track,
            target=target,
            session=session,
            launch_model=_recorded_launch_model(model_profile=track.model_profile),
        )
        return False

    recorded = _recorded_statusline_model(model_profile=track.model_profile)
    if not recorded:
        # No recorded profile at all — the separate fail-soft clause, deliberately silent.
        return False

    if rendered_statusline_model(capture=capture) is None:
        _alert_unreadable_statusline(
            sup=sup,
            track=track,
            target=target,
            session=session,
            recorded=recorded,
        )
        return False
    return False
