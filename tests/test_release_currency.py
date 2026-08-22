"""Controls for the update target's eligibility rule.

Work-item overseer-6s3pk6.1, under plan epic overseer-6s3pk6.

WHY THIS MODULE'S TESTS ARE WRITTEN TO FALSIFY RATHER THAN TO CONFIRM. The
requirement is not "adopt the latest release" — it is "adopt the latest release
ONLY IF that commit's own checks are green". A rule that says yes to a green
release is trivially satisfiable by a function that says yes to everything, so
every test below that matters is one where the correct answer is NO.

The lane this rule consumes is the reason. This repo's release-tag lane failed
93 of its most recent 100 runs and went green only at 2026-08-20T08:19:21Z,
after 123 consecutive failures across sixteen days that nobody noticed. A
currency rule that adopted "latest release" without checking would have
auto-propagated a broken supervisor to the whole fleet for that entire window.
"""

from __future__ import annotations

from overseer.release_currency import update_target

__all__: list[str] = []

_CURRENT = "1111111111111111111111111111111111111111"
_RELEASE = "2f47f010bba58ee87598a7396448c820044bc3f3"


def _green() -> list[dict[str, str]]:
    return [
        {"name": "ci-green", "conclusion": "success"},
        {"name": "check-types", "conclusion": "success"},
    ]


def test_a_green_release_resolves_as_eligible_and_names_the_target() -> None:
    """The one affirmative case. It is here to keep the rule from being vacuously strict."""
    verdict = update_target(current=_CURRENT, release=_RELEASE, checks=_green())

    assert verdict["eligible"] is True
    assert verdict["target"] == _RELEASE


def test_a_red_release_is_ineligible_and_the_reason_names_the_failing_check() -> None:
    """The acceptance's central case, and the sixteen-day outage in miniature.

    Naming the failing check is not decoration: a daemon that declines to
    update and cannot say which check stopped it is indistinguishable from one
    whose update path is silently broken.
    """
    checks = [
        {"name": "ci-green", "conclusion": "failure"},
        {"name": "check-types", "conclusion": "success"},
    ]

    verdict = update_target(current=_CURRENT, release=_RELEASE, checks=checks)

    assert verdict["eligible"] is False
    assert verdict["target"] is None
    assert "ci-green" in str(verdict["reason"])


def test_an_empty_check_set_is_not_green() -> None:
    """THE control that separates this rule from one that cannot fail.

    "Every check passed" is vacuously true of a commit with no checks, so the
    obvious implementation — all(c == success for c in checks) — says YES to a
    commit nothing has ever verified. That is the exact shape this repo keeps
    finding: a check whose passing carries no information.

    A freshly-tagged release reaches this state routinely, in the window
    between the tag landing and its first run appearing, so this is an ordinary
    case rather than a contrived one.
    """
    verdict = update_target(current=_CURRENT, release=_RELEASE, checks=[])

    assert verdict["eligible"] is False
    assert verdict["target"] is None
    assert "no checks" in str(verdict["reason"]).lower()


def test_a_check_still_in_flight_is_not_treated_as_green() -> None:
    """An unsettled rollup is not evidence of success.

    A run in progress reports an empty conclusion. Reading that as anything
    other than "not yet known" adopts a release whose verdict has not been
    reached — a false green with a timing dependency, which is the hardest
    kind to reproduce once it has shipped.
    """
    checks = [
        {"name": "ci-green", "conclusion": ""},
        {"name": "check-types", "conclusion": "success"},
    ]

    verdict = update_target(current=_CURRENT, release=_RELEASE, checks=checks)

    assert verdict["eligible"] is False
    assert "ci-green" in str(verdict["reason"])


def test_an_unresolvable_release_ref_is_ineligible_rather_than_an_error() -> None:
    """Fail open on currency: not knowing the target must not stop supervision.

    The daemon calling this rule is the fleet's supervisor. An unreachable or
    unresolvable ref has to degrade to "keep running what you have", which is
    what an ineligible verdict means to the caller.
    """
    verdict = update_target(current=_CURRENT, release=None, checks=None)

    assert verdict["eligible"] is False
    assert verdict["target"] is None
    assert verdict["reason"]


def test_an_unreadable_check_rollup_is_ineligible_rather_than_assumed_green() -> None:
    """The forge being unreachable is not evidence that the release is good.

    This is the direction the failure must fall. Assuming green on a failed
    read turns every forge outage into an unchecked fleet-wide adoption.
    """
    verdict = update_target(current=_CURRENT, release=_RELEASE, checks=None)

    assert verdict["eligible"] is False
    assert verdict["target"] is None


def test_a_release_equal_to_what_is_running_is_not_an_update() -> None:
    """Already-current is ineligible, and its reason must not read as a failure.

    The daemon ticks continuously, so this is the overwhelmingly common case.
    If it were reported the same way as a red release, the operator surface
    would show a permanent false alarm and be muted within a day.
    """
    verdict = update_target(current=_RELEASE, release=_RELEASE, checks=_green())

    assert verdict["eligible"] is False
    assert verdict["target"] is None
    assert "current" in str(verdict["reason"]).lower()


def test_the_already_current_verdict_is_distinguishable_from_a_blocked_one() -> None:
    """A discriminating control on the surfacing requirement itself.

    The acceptance says ineligibility must be SURFACED rather than silent. That
    is only useful if the routine no-op is separable from a genuine block —
    otherwise a caller must either shout every tick or stay quiet through a red
    release. This asserts the two carry different values, not merely different
    prose.
    """
    routine = update_target(current=_RELEASE, release=_RELEASE, checks=_green())
    blocked = update_target(
        current=_CURRENT,
        release=_RELEASE,
        checks=[{"name": "ci-green", "conclusion": "failure"}],
    )

    assert routine["blocked"] is False
    assert blocked["blocked"] is True
