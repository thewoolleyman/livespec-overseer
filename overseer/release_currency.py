"""Whether a resolved release commit may be adopted as the daemon's runtime.

Work-item overseer-6s3pk6.1, under plan epic overseer-6s3pk6.

CURRENCY AND CORRECTNESS ARE SEPARATE GATES AND BOTH ARE REQUIRED. "The latest
release" is already a single CI-maintained ref -- `.github/workflows/
fast-forward-release-branch.yml` fast-forwards `refs/heads/release` on every
`release: published` -- so resolving a candidate needs no new rule. What needs a
rule is whether that candidate is SAFE, and released does not imply green: this
repo's release-tag lane failed 93 of its most recent 100 runs and went green
only at 2026-08-20T08:19:21Z, after 123 consecutive failures across sixteen days
that nobody noticed. Adopting latest-release without checking would have
auto-propagated a broken supervisor to the whole fleet for that entire window.

THE VERDICT FAILS TOWARD NOT ADOPTING, ALWAYS. Every unknown -- an unresolvable
ref, an unreadable rollup, a run still in flight, a commit with no checks at all
-- resolves to ineligible. The caller is the fleet's supervisor, so declining to
update costs one tick of staleness while adopting wrongly costs every tracked
session. There is no symmetric risk here and the rule does not pretend there is.

WHY `blocked` IS A SEPARATE FIELD FROM `eligible`. The daemon ticks
continuously, so "already running the release" is the overwhelmingly common
verdict and is not a problem. Reporting it through the same channel as a red
release would put a permanent false alarm on the operator surface, and this repo
has a documented history of gates that fire for the wrong reason being muted
within a day. `eligible` answers "adopt this?"; `blocked` answers "does a human
need to know?". The routine no-op is the one ineligible verdict that is not
blocked.

The rule is a pure function of values the caller supplies. As with
``release_lane_watch``, the forge call lives entirely in the caller, so no
network reaches the enforcement aggregate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

__all__: list[str] = ["update_target"]

_SUCCESS = "success"


def update_target(
    *,
    current: str,
    release: str | None,
    checks: Sequence[Mapping[str, object]] | None,
) -> dict[str, object]:
    """Decide whether `release` may replace `current` as the daemon's runtime.

    `release` is the commit `refs/heads/release` resolves to, or None when the
    ref could not be resolved. `checks` carries one mapping per check run on
    THAT COMMIT, each with a `name` and a `conclusion`, or None when the rollup
    could not be read. The two None cases are distinct inputs with the same
    disposition, and both are reported rather than collapsed.
    """
    if release is None:
        return _verdict(reason="release ref did not resolve; keeping the running version")
    if release == current:
        return _verdict(reason="already current: the running version is the release", blocked=False)
    if checks is None:
        return _verdict(reason=f"check rollup for {release} could not be read")
    unsettled = _not_green(checks=checks)
    if unsettled:
        return _verdict(reason=f"{release} is not check-green: {', '.join(unsettled)}")
    if not checks:
        # A commit nothing has verified is not a green commit. `all()` over an
        # empty sequence is True, so the obvious implementation adopts exactly
        # the release that carries the least evidence -- and a freshly-tagged
        # release sits in this state routinely, between the tag landing and its
        # first run appearing. This branch is why that window is not a hole.
        return _verdict(reason=f"{release} reports no checks at all; absence is not green")
    return {"eligible": True, "target": release, "blocked": False, "reason": f"{release} is green"}


def _not_green(*, checks: Sequence[Mapping[str, object]]) -> list[str]:
    """Name every check that is not a settled success, in the order supplied.

    A run still in flight reports an empty conclusion. It is grouped with the
    outright failures deliberately: both mean "this commit is not known to be
    good", and separating them would invite a caller to treat pending as
    benign, which is a false green with a timing dependency.
    """
    return [
        str(check.get("name") or "<unnamed>")
        for check in checks
        if str(check.get("conclusion") or "") != _SUCCESS
    ]


def _verdict(*, reason: str, blocked: bool = True) -> dict[str, object]:
    return {"eligible": False, "target": None, "blocked": blocked, "reason": reason}
