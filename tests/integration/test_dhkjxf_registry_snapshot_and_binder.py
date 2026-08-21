"""Integration coverage for snapshot and generated-binder scenario TODO rows."""

from __future__ import annotations

import re
from pathlib import Path

import _supervisor_snapshot
import pytest
from test_supervisor_builders import make_plan

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BINDER = _REPO_ROOT / "tests" / "prompts" / "fixtures" / "exemplar-supervisor-handoff.md"


def _shell_blocks(*, text: str) -> list[str]:
    fence = re.compile(
        r"^[ \t]*(`{3,}|~{3,})([^\n]*)\n(.*?)^[ \t]*\1[ \t]*$",
        re.MULTILINE | re.DOTALL,
    )
    blocks: list[str] = []
    for match in fence.finditer(text):
        language = match.group(2).strip().split(maxsplit=1)[0]
        if language in {"sh", "bash"}:
            blocks.append(match.group(3))
    return blocks


@pytest.mark.integration
def test_scenario_snapshot_writer_failure_does_not_stop_supervision(*, tmp_path, capsys):
    from tests.integration.test_supervisor_status_snapshot import make_live_mapped_supervisor

    repo, topic = make_plan(
        tmp_path=tmp_path,
        repo_name="repo",
        topic="snapshot-writer-failure",
    )

    def raising_writer(*, path: Path, body: str) -> None:
        raise OSError(f"cannot write {path.name}")

    sup, _session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=tmp_path / "status.json",
        status_writer=raising_writer,
        ctx=74,
    )

    rows = sup.tick(act=True)
    second = sup.tick(act=True)
    err = capsys.readouterr().err

    assert rows[0].status == "idle-with-context-left"
    assert second[0].status == "idle-with-context-left"
    assert sup.tick_generation == 2
    assert err.count("status snapshot write failed") == 1
    assert _supervisor_snapshot.read_status_snapshot(path=tmp_path / "status.json") is None


@pytest.mark.integration
def test_scenario_consumer_fails_closed_on_unknown_snapshot_schema(*, tmp_path):
    status_path = tmp_path / "status.json"
    status_path.write_text(
        '{"schema_version": 999, "tick_generation": 1, "rows": []}\n',
        encoding="utf-8",
    )

    assert _supervisor_snapshot.read_status_snapshot(path=status_path) is None


@pytest.mark.integration
def test_scenario_missing_supervisor_role_layer_halts_binder_with_remedy(*, tmp_path):
    del tmp_path
    binder = _BINDER.read_text(encoding="utf-8")
    boot = next(block for block in _shell_blocks(text=binder) if "supervisor-protocol.md" in block)

    assert 'test -f ".ai/supervisor-protocol.md"' in boot
    assert "HALT: missing shared supervisor protocol .ai/supervisor-protocol.md" in boot
    assert "REMEDY: regenerate the two-layer supervisor handoff before driving" in boot
    assert "exit 1" in boot
