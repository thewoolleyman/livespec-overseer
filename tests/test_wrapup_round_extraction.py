"""The wrap-up act's ROUND BOOKKEEPING is its own cohesive module.

`_supervisor_wrapup_injection` orchestrates one act: decide which bands are due,
prove the channel binding, deliver, and report. The round-state CONSEQUENCES of
that delivery — stamping the round open, marking the bands a landed message
answered, and rolling back a round that stands behind an undelivered one — are a
separate concern, and the one the v060 channel work grew. They move out together
with the private helpers only they used, as PUBLIC functions, because pyright
strict and the `private_calls` check both reject importing an `_`-prefixed name
across a module boundary.
"""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []

_MOVED_PRIVATE_NAMES = (
    "_mark_delivered",
    "_open_round",
    "_report_undelivered",
)
_PUBLIC_NAMES = (
    "mark_delivered",
    "open_round",
    "report_undelivered",
)


def test_round_bookkeeping_moved_to_its_own_module_as_public_functions() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_supervisor_wrapup_round.py"
    assert module_path.is_file()

    extracted = importlib.import_module("_supervisor_wrapup_round")
    for name in _PUBLIC_NAMES:
        assert hasattr(extracted, name), f"{name} must be public on the extracted module"
    assert sorted(extracted.__all__) == sorted(_PUBLIC_NAMES)


def test_the_wrapup_act_reaches_the_bookkeeping_through_the_new_module() -> None:
    """The source module keeps NO copy of the moved helpers under their old names.

    A size-split that leaves the private helper behind has moved nothing; a split
    that imports the private name back is the cross-module private usage both the
    type checker and the `private_calls` check refuse.
    """
    injection = importlib.import_module("_supervisor_wrapup_injection")
    for name in _MOVED_PRIVATE_NAMES:
        assert not hasattr(injection, name), f"{name} must be gone from the source module"
