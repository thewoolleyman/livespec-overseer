"""This repository's committed factory table is registry-backed and names no machine.

Integration-tier coverage for the factory-routing rule in
`SPECIFICATION/constraints.md`: every entry this repository commits under
`dispatcher.factories` declares `"registry": true` and carries no `server` and
no `docker_host`, so the binding from a factory NAME to a machine lives only in
the fleet gitops inventory that each dispatching host renders as
`/etc/livespec/fabro-factories.json`; and `dispatcher.default_factory` names
`petri` since the cutover (bd-ib-iud52v).

The subject is the REAL committed `.livespec.jsonc` at the repository root, read
through the package's own JSONC reader rather than a second stripper — a
synthesized fixture would prove nothing about what this repository ships.
"""

from __future__ import annotations

from pathlib import Path

import _supervisor_wait_target_liveness
import jsonio

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _committed_dispatcher() -> dict[str, object]:
    dispatcher = _supervisor_wait_target_liveness.dispatcher_config(repo=_REPO_ROOT)
    assert dispatcher is not None, f"no dispatcher block in {_REPO_ROOT / '.livespec.jsonc'}"
    return dispatcher


def test_the_committed_factory_table_is_registry_backed_petri_alone() -> None:
    factories = jsonio.as_object(value=_committed_dispatcher().get("factories"))
    assert factories is not None
    assert sorted(factories) == ["petri"]
    for name in ("petri",):
        entry = jsonio.as_object(value=factories[name])
        assert entry is not None
        assert entry.get("registry") is True
        assert "server" not in entry
        assert "docker_host" not in entry


def test_the_committed_default_factory_names_petri() -> None:
    assert _committed_dispatcher().get("default_factory") == "petri"
