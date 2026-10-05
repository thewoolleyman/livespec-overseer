"""The adapter's DEFAULT request-id factory, pinned deterministically.

**This file pins EXISTING behaviour and passed the moment it was written. It is
not Red-driven and must not be read as evidence of a Red-Green cycle.** It exists
for two reasons, both about coverage rather than about a new claim:

  1. The default factory is only advanced when a caller does NOT inject ids, and
     every deterministic test injects them so it can assert the exact bytes on
     the wire. The one suite that takes the default is
     `tests/test_herdr_live_observation.py`, which SKIPS wherever herdr is
     absent — and this repository's CI container
     (`ghcr.io/thewoolleyman/livespec-fabro-sandbox:python-v1.64.1`) does not
     ship herdr. So on the CI lane the shipped default was executed by nothing,
     while the coverage gate stayed at 100%.
  2. The invariant is worth stating on its own terms. `herdr_transport` refuses
     a reply whose id is not the one it sent, which is the guard against a
     mismatched or replayed answer — and that guard is worth nothing if every
     request carries the SAME id. Nothing else asserts that the shipped default
     actually varies, so a change to a constant would have been invisible.
"""

from __future__ import annotations

import importlib
import itertools
from pathlib import Path
from typing import Any

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
ADAPTER_PATH = PACKAGE_DIR / "herdr_adapter.py"
SAMPLE = 32


def _adapter_module() -> Any:
    assert ADAPTER_PATH.is_file(), f"the observation adapter needs {ADAPTER_PATH.name}"
    return importlib.import_module("herdr_adapter")


def test_the_shipped_default_request_ids_are_distinct_and_prefixed():
    """A freshly-constructed adapter yields a distinct, recognizable id per request.

    Distinctness is the load-bearing half: the transport's id match is what makes
    a stale or replayed reply detectable, and a constant id would satisfy that
    check against any reply. The prefix is the operator-facing half — an id seen
    in a herdr server log should name the overseer as its author.
    """
    adapter_module = _adapter_module()
    adapter = adapter_module.HerdrAdapter()

    issued = list(itertools.islice(adapter.request_ids, SAMPLE))

    assert len(set(issued)) == SAMPLE, f"request ids repeat: {issued}"
    assert all(one.startswith(adapter_module.REQUEST_ID_PREFIX) for one in issued), issued
    # Two adapters must not share a generator: a `default_factory` that returned
    # one module-level iterator would hand out ids already consumed elsewhere,
    # and a caller reading its own ids would silently skip.
    other = list(itertools.islice(adapter_module.HerdrAdapter().request_ids, 1))
    assert other == [issued[0]], "each adapter starts its own id sequence"
