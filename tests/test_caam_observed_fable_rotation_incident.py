"""The 2026-09-06 Fable-drain incident, reproduced end-to-end through ``decide()``.

INCIDENT (work-item overseer-dyt6). The active account drained its Fable
allowance to zero while three idle accounts still held Fable, and the rotator did
NOT move: the Fable-dependent sessions were left with no Fable and the operator
switched accounts by hand, twice.

WHY THIS FILE EXISTS ON TOP OF THE PIECES ALREADY PINNED. The mechanism the
incident needed is governed by SPECIFICATION v045 ("fable-quota-fleet-wide") and
was implemented on master before the incident: an ACTIVE account that cannot
serve the scoped model triggers rotation on its own, a candidate that CAN serve
it is ranked ahead and its relative-headroom margin waived, and a per-account
protection floor is never relaxed to reach one. But the existing ``decide()``
coverage arms that clause through an EXPLICIT ``foreman_model`` pin
(``test_caam_unsatisfiable_pin_hold``), while the incident's arming route is the
OTHER one v045 added and the one an unpinned foreman on default Fable actually
takes: a session merely OBSERVED running the scoped model. That route is pinned
only at the ``scoped_model_pinned`` unit level, and the protection-floor
exclusion only at the pure-helper level; neither is exercised end-to-end through
``decide()`` together. This file closes exactly that composition, so the incident
cannot regress through the path it actually travelled.

Every figure here is a SPENT percentage, matching the durable state the rotator
stores: a ``fable`` of 100.0 is ZERO Fable remaining (cannot serve), and the
"active is otherwise quiet" account sits well inside every other threshold so
that being unable to serve the scoped model is the SOLE reason it would leave.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord
from caam_foreman_override import OBSERVED_MODELS_KEY

__all__: list[str] = []

_SPENT = 100.0
_SERVES = 10.0


def _usage(*, seven_day: float, five_hour: float, fable: float | None = _SPENT) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=100.0 - five_hour,
        seven_day_remaining=100.0 - seven_day,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None if fable is None else 100.0 - fable,
        fable_resets_at=None,
    )


def _quiet_active(*, fable: float | None = _SPENT) -> UsageRecord:
    """An active account no OTHER trigger leg fires for.

    Short window well above the rotation floor, weekly well above the reserve, no
    protection floor. So when this account cannot serve the scoped model, that
    unserviceability is the sole reason the pass is leaving -- the incident's
    shape, where anthropic-1 drained Fable while its 5-hour and weekly were fine.
    """
    return _usage(seven_day=50.0, five_hour=40.0, fable=fable)


def _idle_holder(*, name: str, fable: float = _SERVES) -> ProfileUsage:
    """An idle account that still holds Fable and clears every ordinary exclusion."""
    return ProfileUsage(
        name=name,
        source="live",
        usage=_usage(seven_day=40.0, five_hour=20.0, fable=fable),
    )


@dataclass(frozen=True, kw_only=True)
class _SwitchResult:
    lines: tuple[str, ...]
    exit_code: int
    switched: bool = True


class _Flags:
    def __init__(self, *, force: bool = False, dry_run: bool = False) -> None:
        self.force = force
        self.dry_run = dry_run


class _Context:
    """Mirrors the decision context, armed through OBSERVED models rather than a pin.

    ``observed_models`` is the map enforcement rebuilds from the live panes each
    pass, before the decision runs; arming the clause from it is the whole point
    of the v045 widening this incident lives on.
    """

    def __init__(self, *, home: Path, observed: dict[str, str]) -> None:
        self.flags = _Flags()
        self.home = home
        self.now = 1_787_000_000.0
        self.state: dict[str, object] = {OBSERVED_MODELS_KEY: observed}
        self.state_path = home / "state.json"
        self.lines: list[str] = []

    def stdout(self, line: str) -> None:
        self.lines.append(line)


class _Outcome:
    def __init__(self) -> None:
        self.switched_to: str | None = None
        self.lines: list[str] = []

    @property
    def held(self) -> bool:
        return self.switched_to is None


def _run(
    *,
    tmp_path: Path,
    active: UsageRecord,
    candidates: tuple[ProfileUsage, ...],
    observed: dict[str, str],
    protection_floors: dict[str, float] | None = None,
) -> _Outcome:
    outcome = _Outcome()
    context = _Context(home=tmp_path, observed=observed)

    def _switch(*, request: object) -> _SwitchResult:
        outcome.switched_to = request.target.name  # type: ignore[attr-defined]
        return _SwitchResult(lines=("SWITCHED",), exit_code=0)

    decide(
        context=context,
        profiles=(ProfileUsage(name="anthropic-1", source="live", usage=active), *candidates),
        active_name="anthropic-1",
        current=active,
        protection_floors=protection_floors or {},
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used"),
            save_state=lambda **_: None,
            switch_account=_switch,
        ),
    )
    outcome.lines = context.lines
    return outcome


# ---------------------------------------------------------------------------
# Acceptance (a): active Fable=0, a session OBSERVED on Fable, an eligible
# Fable-holding unprotected candidate -> rotate to it.
# ---------------------------------------------------------------------------


def test_an_observed_fable_session_rotates_off_a_spent_active_to_a_fable_holder(
    tmp_path: Path,
) -> None:
    """THE INCIDENT. No operator pin -- the foreman is simply observed on Fable.

    The active account's Fable is spent while an idle account still holds it, so
    the pass must move there rather than strand the Fable-dependent session.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(_idle_holder(name="anthropic-2"),),
        observed={"homelab-foreman": "fable"},
    )
    assert outcome.switched_to == "anthropic-2", (
        f"an observed-on-Fable session must arm rotation to a Fable holder; "
        f"held={outcome.held} switched_to={outcome.switched_to}"
    )


def test_an_observed_fable_session_prefers_the_fable_holder_over_a_richer_non_holder(
    tmp_path: Path,
) -> None:
    """Ranking: a Fable holder sorts ahead of a candidate that cannot serve it.

    ``anthropic-3`` has more short-window headroom and would win the ordinary
    ranking, but it cannot serve the pinned model; ``anthropic-2`` can, so the
    pin is honoured rather than the raw headroom.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(
            ProfileUsage(
                name="anthropic-3",
                source="live",
                usage=_usage(seven_day=10.0, five_hour=5.0, fable=_SPENT),
            ),
            _idle_holder(name="anthropic-2"),
        ),
        observed={"homelab-foreman": "fable"},
    )
    assert outcome.switched_to == "anthropic-2"


# ---------------------------------------------------------------------------
# Acceptance (b): no Fable-driven rotation when no Fable-dependent session is
# active -- the weekly-optimizing behavior is preserved.
# ---------------------------------------------------------------------------


def test_no_session_on_fable_leaves_a_quiet_spent_active_in_place(
    tmp_path: Path,
) -> None:
    """With nothing observed on Fable, the spent scoped allowance reaches nothing.

    Same accounts as the incident, but every observed session is on the general
    model, so the scoped clause stays off and the quiet active holds on its own
    healthy allowances -- no rotation merely to spend Fable.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(_idle_holder(name="anthropic-2"),),
        observed={"some-worker": "opus"},
    )
    assert outcome.held, f"must not rotate on scoped grounds; switched to {outcome.switched_to}"


# ---------------------------------------------------------------------------
# Acceptance (c): a per-account protection floor is honoured under Fable-driven
# selection -- never select a protected account below its floor, even to serve
# the pin.
# ---------------------------------------------------------------------------


def test_a_protected_at_floor_fable_holder_is_never_selected_to_serve_the_pin(
    tmp_path: Path,
) -> None:
    """The floor outranks the pin. An at-floor protected holder is passed over.

    ``anthropic-p`` holds Fable but is protected and already at its floor, so the
    scoped waiver -- which relaxes only the relative-headroom margin -- may not
    reach it. The unprotected Fable holder is selected instead.
    """
    protected_at_floor = ProfileUsage(
        name="anthropic-p",
        source="live",
        usage=_usage(seven_day=90.0, five_hour=20.0, fable=_SERVES),
    )
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(protected_at_floor, _idle_holder(name="anthropic-2")),
        observed={"homelab-foreman": "fable"},
        protection_floors={"anthropic-p": 10.0},
    )
    assert outcome.switched_to == "anthropic-2"


def test_a_protected_at_floor_holder_is_not_reached_even_as_the_only_fable_source(
    tmp_path: Path,
) -> None:
    """When the ONLY Fable holder is protected-at-floor, the pass holds, not breaches.

    The unprotected candidate cannot serve the pin and the protected one may not
    be selected below its floor, so no candidate can serve it: the pass must hold
    rather than rotate onto the protected account to no lawful purpose.
    """
    protected_at_floor = ProfileUsage(
        name="anthropic-p",
        source="live",
        usage=_usage(seven_day=90.0, five_hour=20.0, fable=_SERVES),
    )
    non_holder = ProfileUsage(
        name="anthropic-2",
        source="live",
        usage=_usage(seven_day=40.0, five_hour=20.0, fable=_SPENT),
    )
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(protected_at_floor, non_holder),
        observed={"homelab-foreman": "fable"},
        protection_floors={"anthropic-p": 10.0},
    )
    assert (
        outcome.held
    ), f"must not breach the floor to serve the pin; switched to {outcome.switched_to}"
