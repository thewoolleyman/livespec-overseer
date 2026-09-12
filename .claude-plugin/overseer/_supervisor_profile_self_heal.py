"""Bounded recapture for a mapped row whose stored harness is not the live runtime.

A launch profile records the harness, model and wrapper a track will be RE-ASSERTED with
on restart. It is captured at adoption and refreshed when a wrap-up round OPENS — and
nowhere else, deliberately. That is enough for every ordinary track, and it is exactly
one refresh short for the shape this module exists for: a row whose stored profile names
a DIFFERENT harness than the process actually running in its pane.

Such a row cannot be relaunched at all. The launch planners refuse a cross-runtime
profile rather than aim a Claude relaunch at a Codex pane (which would destroy the live
session), so the refusal is correct — but with the round already open, nothing re-reads
the profile, and the refusal repeats every tick for as long as the declaration stands.
Measured live 2026-09-12 (`overseer-phz7te`): 95 consecutive refusals over half an hour
against a live Codex pane whose row still carried its predecessor's Claude profile.

So the restart path asks here FIRST. The recapture takes every fact from the proven live
process — the same discovery that names the pane's runtime elsewhere — and GUESSES
nothing: no runtime, no model, no wrapper, no session identity, no repository. When no
live source is discoverable for this track, or its harness already agrees with the stored
one, this does nothing at all and the caller's ordinary refusal stands.

**It heals, then STOPS.** A heal persists the recaptured profile and returns True, and
the caller abandons this tick's restart rather than proceeding on a profile written
moments ago in the same pass. The `ready` declaration is untouched, so an ordinary later
tick re-observes the healed row and restarts through the normal path — the destructive
`respawn-pane -k` happens only after the daemon has SEEN the profile it is acting on.
That also bounds the repair: once persisted, the harnesses agree and this is a no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
from _supervisor_codex_adoption import codex_host_readers
from _supervisor_discovery_adoption import sessions_dir
from _supervisor_launch_profile import (
    LaunchProfileProblem,
    complete_launch_profile,
    read_launch_profile,
    rendered_statusline_model,
)
from _supervisor_launch_profile_sources import (
    LaunchProfileSource,
    codex_model_source,
    live_profile_sources,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "PROFILE_SELF_HEAL_CONDITION",
    "heal_cross_runtime_profile",
]

# The alert condition a completed recapture raises. DISTINCT from `stale-launch-profile`,
# which reports the refusal this replaces: that one says the restart cannot proceed, this
# one says the obstacle has been repaired and the next tick will carry it out.
PROFILE_SELF_HEAL_CONDITION = "launch-profile-self-healed"


def _live_source(*, sup: Supervisor, session: str, topic: str) -> LaunchProfileSource | None:
    return live_profile_sources(
        sessions_dir=sessions_dir(sup=sup),
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        ppid_of=sup.ppid_of,
        starttime_of=sup.starttime_of,
        codex_readers=codex_host_readers(sup=sup),
    ).get((session, topic))


def _recaptured_profile(
    *, sup: Supervisor, source: LaunchProfileSource
) -> dict[str, str | None] | LaunchProfileProblem:
    return complete_launch_profile(
        profile=read_launch_profile(
            pid=source.pid,
            harness=source.harness,
            pane_pid=source.pane_pid,
            cmdline_of=sup.cmdline_of,
            environ_of=sup.environ_of,
            ppid_of=sup.ppid_of,
        ),
        harness=source.harness,
        pid=source.pid,
        runtime_model_of=sup.runtime_model_of,
        codex_identity=codex_model_source(
            source=source,
            environ_of=sup.environ_of,
            codex_home=sup.codex_home,
        ),
    )


def heal_cross_runtime_profile(
    *, sup: Supervisor, track: registry.Track, session: str, target: str
) -> bool:
    """Recapture and persist the live profile for a cross-runtime row. True when healed.

    False — leaving the caller's own refusal to stand — for every row this cannot speak
    for: one carrying no stored profile, one with no discoverable live process, one whose
    stored harness already IS the live runtime, and one whose live process names no usable
    model at all. The last of those is reported under the ordinary unreadable-profile
    condition, because it is the same fact: the pane is preserved, the declaration is
    preserved, and an operator is told which pane could not be read.
    """
    stored = track.model_profile
    source = _live_source(sup=sup, session=session, topic=track.topic)
    if source is None or stored is None or source.harness == stored["harness"]:
        return False
    profile = _recaptured_profile(sup=sup, source=source)
    if isinstance(profile, LaunchProfileProblem):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=(
                f"{profile.message}; the stored {stored['harness']!r} profile cannot "
                f"relaunch this live {source.harness!r} session and could not be recaptured"
            ),
            condition="launch-profile-unreadable",
        )
        return False
    # Re-baseline the statusline from the live render for the same reason a round open
    # does: the inherited baseline belongs to the OTHER runtime, so keeping it would hand
    # the repaired row a standing statusline veto it could never satisfy. An unreadable
    # render leaves the key absent, which is the unverified-but-permitted shape.
    profile["statusline_model"] = rendered_statusline_model(
        capture=sup.tmux.capture_pane(session=target)
    )
    if not registry.record_model_profile(
        repo=track.repo,
        topic=track.topic,
        model_profile=profile,
        store_path=sup.store_path,
    ):
        return False
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=(
            f"stored launch profile harness {stored['harness']!r} is not the live "
            f"{source.harness!r} runtime; recaptured and persisted the live profile "
            f"(model {profile['model']!r}), keeping the ready declaration so the next "
            "tick restarts on the re-observed profile"
        ),
        condition=PROFILE_SELF_HEAL_CONDITION,
    )
    return True
