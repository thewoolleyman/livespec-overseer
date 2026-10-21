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
