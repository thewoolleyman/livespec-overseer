"""Guard that the supervise-plan seat is gone and the daemon's loop is not.

The supervise-plan operator seat was retired by SPECIFICATION v047 (maintainer
ruling 2026-09-06, console plan decision D5 bucket 2). The cut is by CONSUMER,
not by name prefix, and this seat is the one where that distinction does the most
work: the daemon's ``_supervisor_*`` loop IS overseerd, which is bucket 1 and
STAYS. Only what the supervise-plan binder/handoff alone reached goes.

So this test pins both halves. The removed half is the skill in all three
harnesses, its prose, the manifest advertisements and the one module whose sole
consumer was the generated-charter contract. The kept half is the daemon's
supervisor loop — including the restart interlock's binder certification, which
SPECIFICATION still requires of the daemon for a SUPERVISOR topic — so a later
cut cannot mistake this seat's retirement for a licence to delete the loop that
shares its name.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "overseer"
PLUGIN = ROOT / ".claude-plugin"
CARRIER = PLUGIN / "overseer"

# Surfaces the supervise-plan seat owned outright.
REMOVED_PATHS = (
    PLUGIN / "prose" / "supervise-plan.md",
    PLUGIN / "skills" / "supervise-plan",
    PLUGIN / ".codex-plugin" / "skills" / "supervise-plan",
    PLUGIN / ".pi-plugin" / "skills" / "livespec-overseer-supervise-plan",
)

# The one module whose only consumer was the generated supervisor-handoff
# contract, measured 2026-09-06: `_prompt_realizations` was imported by nothing
# but `tests/prompts/test_generated_supervisor_handoff_contract.py`, which reads
# the deleted generator prose.
REMOVED_MODULES = ("_prompt_realizations.py",)

# Bucket-1 daemon modules that carry the seat's vocabulary and must SURVIVE it:
# the restart interlock's binder certification, the supervision-offer surface,
# the supervisor entity's own prompts, and its state file.
KEPT_DAEMON_MODULES = (
    "_supervisor_offer.py",
    "_supervisor_prompts_supervisor.py",
    "_supervisor_restart_binder.py",
    "_supervisor_supervisor_state.py",
)

MANIFESTS = (
    PLUGIN / "plugin.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / "marketplace.json",
)


def test_the_supervise_plan_skill_surfaces_are_deleted() -> None:
    assert [str(path.relative_to(ROOT)) for path in REMOVED_PATHS if path.exists()] == []


def test_no_manifest_advertises_a_supervise_plan_operation() -> None:
    offenders = [
        manifest.name
        for manifest in MANIFESTS
        if "supervise-plan" in json.dumps(json.loads(manifest.read_text(encoding="utf-8")))
    ]
    assert offenders == []


def test_the_seat_only_module_is_gone_from_the_package_and_its_carrier() -> None:
    for directory in (PACKAGE, CARRIER):
        assert [name for name in REMOVED_MODULES if (directory / name).exists()] == []


def test_the_daemon_supervisor_loop_survives_in_both_trees() -> None:
    """The kept half of the cut, asserted by name rather than by count.

    A count would drift with every ordinary refactor of the loop; these four
    modules are the ones a name-prefix cut would have taken with the seat.
    """
    for directory in (PACKAGE, CARRIER):
        assert [name for name in KEPT_DAEMON_MODULES if not (directory / name).is_file()] == []


def test_the_supervision_offer_no_longer_points_at_a_deleted_skill() -> None:
    """The offer surface is bucket 1 and stays; its remediation text cannot dangle."""
    for directory in (PACKAGE, CARRIER):
        source = (directory / "_supervisor_offer.py").read_text(encoding="utf-8")
        assert "supervise-plan" not in source
        assert "publish a supervisor handoff" in source
