"""Registry-backed factory resolution for remote wait-target liveness.

Under `SPECIFICATION/constraints.md` a committed `dispatcher.factories` entry
declares `"registry": true` and names no machine, so the server that answers to a
factory name is bound only in the fleet gitops inventory's factory registry — a
JSON object mapping factory name to `{server, optional docker_host}`, rendered on
each dispatching host as `/etc/livespec/fabro-factories.json`. These tests supply
that registry through the injectable registry path, because no factory sandbox
carries the host file.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path

import _supervisor_wait_target_liveness as liveness

__all__: list[str] = []

_REGISTRY_BACKED_CONFIG = (
    '{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": '
    '{"legacy": {"registry": true}, "petri": {"registry": true}}}}}'
)
_PETRI_RUNNING = '{"runs": [{"id": "dispatch-1", "status": "running"}]}'


@dataclass(frozen=True, kw_only=True)
class Completed:
    returncode: int
    stdout: str = ""


def registry_backed_repo(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _ = (repo / ".livespec.jsonc").write_text(_REGISTRY_BACKED_CONFIG, encoding="utf-8")
    return repo


def write_registry(*, path: Path, text: str) -> Path:
    _ = path.write_text(text, encoding="utf-8")
    return path


def test_a_registry_backed_factory_resolves_its_server_from_the_supplied_registry(*, tmp_path):
    repo = registry_backed_repo(tmp_path=tmp_path)
    registry_path = write_registry(
        path=tmp_path / "fabro-factories.json",
        text=(
            '{"legacy": {"server": "https://legacy.example:32276"},'
            ' "petri": {"server": "https://petri.example:32276",'
            ' "docker_host": "tcp://petri.example:2376"}}'
        ),
    )
    commands: list[list[str]] = []

    def run(args, **kwargs):
        commands.append(args)
        _ = kwargs
        return Completed(returncode=0, stdout=_PETRI_RUNNING)

    assert "registry_path" in inspect.signature(liveness.remote_factory_run_present_with).parameters
    assert (
        liveness.remote_factory_run_present_with(
            repo=repo,
            record={"dispatch_factory": "petri", "work_item_id": "overseer-glundr"},
            target_id="dispatch-1",
            run=run,
            registry_path=registry_path,
        )
        is True
    )
    assert commands == [["fabro", "ps", "-a", "--json", "--server", "https://petri.example:32276"]]
    assert (
        liveness.factory_server(repo=repo, factory="legacy", registry_path=registry_path)
        == "https://legacy.example:32276"
    )


def test_a_committed_server_still_wins_over_the_supplied_registry(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _ = (repo / ".livespec.jsonc").write_text(
        '{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": '
        '{"petri": {"registry": true, "server": "https://committed.example:32276"}}}}}',
        encoding="utf-8",
    )
    registry_path = write_registry(
        path=tmp_path / "fabro-factories.json",
        text='{"petri": {"server": "https://registry.example:32276"}}',
    )

    assert "registry_path" in inspect.signature(liveness.factory_server).parameters
    assert (
        liveness.factory_server(repo=repo, factory="petri", registry_path=registry_path)
        == "https://committed.example:32276"
    )


def test_remote_liveness_uses_the_factorys_committed_carrier_client(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _ = (repo / ".livespec.jsonc").write_text(
        '{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": '
        '{"petri": {"server": "https://petri.example:32276", '
        '"bin": "/carrier/petri/fabro"}}}}}',
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def run(args, **kwargs):
        commands.append(args)
        _ = kwargs
        return Completed(returncode=0, stdout=_PETRI_RUNNING)

    assert (
        liveness.remote_factory_run_present_with(
            repo=repo,
            record={"dispatch_factory": "petri"},
            target_id="dispatch-1",
            run=run,
        )
        is True
    )
    assert commands == [
        ["/carrier/petri/fabro", "ps", "-a", "--json", "--server", "https://petri.example:32276"]
    ]


def test_factory_client_falls_back_to_path_fabro_without_a_declared_bin(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert liveness.factory_client(repo=repo, factory=None) == "fabro"
    assert liveness.factory_client(repo=repo, factory="petri") == "fabro"


def refuse_to_run(args, **kwargs):
    _ = kwargs
    raise AssertionError(f"fabro must not be queried without a resolved server: {args!r}")


def verdict_or_failure(*, call):
    """The liveness verdict, or a sentinel naming an exception it raised instead.

    A registry read that RAISES is the failure this test exists to rule out, so it
    is reported as a verdict rather than allowed to abort the comparison — every
    unusable registry must come back as "cannot answer".
    """
    try:
        return call()
    except (OSError, ValueError) as failed:
        return f"raised {type(failed).__name__}"


def test_an_unusable_supplied_registry_reports_that_the_factory_cannot_answer(*, tmp_path):
    repo = registry_backed_repo(tmp_path=tmp_path)
    unreadable = tmp_path / "unreadable-registry"
    unreadable.mkdir()
    cases = {
        "absent": tmp_path / "absent" / "fabro-factories.json",
        "unreadable": unreadable,
        "malformed": write_registry(path=tmp_path / "malformed.json", text="{"),
        "not-an-object": write_registry(path=tmp_path / "list.json", text="[]"),
        "another-factory": write_registry(
            path=tmp_path / "other.json", text='{"legacy": {"server": "https://legacy.example"}}'
        ),
        "entry-not-an-object": write_registry(path=tmp_path / "entry.json", text='{"petri": []}'),
        "server-not-a-string": write_registry(
            path=tmp_path / "server.json", text='{"petri": {"server": 32276}}'
        ),
    }

    verdicts = {
        name: verdict_or_failure(
            call=lambda path=path: liveness.remote_factory_run_present_with(
                repo=repo,
                record={"dispatch_factory": "petri", "work_item_id": "overseer-glundr"},
                target_id="dispatch-1",
                run=refuse_to_run,
                registry_path=path,
            )
        )
        for name, path in cases.items()
    }

    assert verdicts == dict.fromkeys(cases, None)
    assert False not in verdicts.values()


def test_an_object_shaped_dispatch_factory_is_read_by_name_and_recorded_server(*, tmp_path):
    """The dispatcher records `dispatch_factory` as an object on some runs.

    `livespec-orchestrator-beads-fabro` writes `{"name": ..., "server": ...}`
    there (e.g. on `bd-ib-wkfwtx`). Reading that with `string_field` yielded None,
    which the reader treated as "this record names no factory" and answered NO RUN
    for a live run — the unsafe direction, and without querying fabro at all.
    """
    repo = registry_backed_repo(tmp_path=tmp_path)
    registry_path = write_registry(
        path=tmp_path / "fabro-factories.json",
        text='{"petri": {"server": "https://petri.example:32276"}}',
    )
    commands: list[list[str]] = []

    def run(args, **kwargs):
        commands.append(args)
        _ = kwargs
        return Completed(returncode=0, stdout=_PETRI_RUNNING)

    def present(*, dispatch_factory):
        return liveness.remote_factory_run_present_with(
            repo=repo,
            record={"dispatch_factory": dispatch_factory, "work_item_id": "overseer-glundr"},
            target_id="dispatch-1",
            run=run,
            registry_path=registry_path,
        )

    recorded = present(dispatch_factory={"name": "petri", "server": "https://noted.example:32276"})
    by_name = present(dispatch_factory={"name": "petri"})
    nameless = present(dispatch_factory={})

    assert (recorded, by_name) == (True, True)
    assert nameless is False
    assert commands == [
        ["fabro", "ps", "-a", "--json", "--server", "https://noted.example:32276"],
        ["fabro", "ps", "-a", "--json", "--server", "https://petri.example:32276"],
    ]
