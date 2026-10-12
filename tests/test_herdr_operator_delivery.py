"""Delivery contract for the dual-backend overseer operator surface."""

from __future__ import annotations

from pathlib import Path

import _supervisor_table_layout
import _supervisor_view
import herdr_identity

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
OPERATOR_CONTRACT = ROOT / ".claude-plugin" / "prose" / "overseer.md"
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"


def test_the_shipped_contract_bootstraps_the_nearest_verified_backend_without_an_override() -> None:
    prose = OPERATOR_CONTRACT.read_text(encoding="utf-8")

    assert "Linux with either tmux or Herdr" in prose
    assert "nearest positively verified terminal owner" in prose
    assert '"$OVERSEER_START"' in prose
    assert '"$OVERSEER_START" --backend' not in prose
    assert "same original LLM pane" in prose
    assert "running bootstrap again" in prose


def test_the_live_table_names_the_backend_instance_and_exact_herdr_pane() -> None:
    coordinate = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/user/1000/herdr/ops.sock",
            server_pid=4127,
            server_starttime="811092",
            pane_id="w3:p8",
        )
    )
    row = _supervisor_view.RowView(
        topic="backend-parity",
        repo="/work/livespec-overseer",
        tmux=coordinate,
        ctx=37,
        status="blocked:human",
        runtime="codex",
    )
    target = _supervisor_view.tmux_cell(row=row)
    table = _supervisor_table_layout.render_lines(
        rows=[("blocked:human", row.topic, target, "37%", "livespec-overseer")],
        columns=None,
    )

    assert table[0].split() == ["Status", "Topic", "Target", "Ctx%", "Repo"]
    assert target == (
        "herdr /run/user/1000/herdr/ops.sock · server 4127/811092 · " "pane w3:p8 (codex)"
    )


def test_the_live_exercise_plan_isolates_every_operator_resource() -> None:
    assert LIVE_EXERCISE.is_file()
    source = LIVE_EXERCISE.read_text(encoding="utf-8")

    scratch_creation = (
        'scratch_root="$(mktemp -d "${TMPDIR:-/tmp}/livespec-overseer-exercise.XXXXXX")"'
    )
    assert scratch_creation in source
    assert "trap cleanup EXIT HUP INT TERM" in source
    assert 'rm -rf -- "$scratch_root"' in source
    assert '--bind "$scratch_home" "$operator_home"' in source
    assert '--bind "$scratch_tmp" /tmp' in source
    assert '--bind "$scratch_runtime" "/run/user/$operator_uid"' in source
    assert '"repos": ["/tmp/livespec-overseer-exercise-repo"]' in source
    assert 'backend_instance="livespec-overseer-exercise-${backend}-' in source
    assert "-u TMUX_PANE" in source
    assert "-u HERDR_SOCKET_PATH" in source
    assert "HOME=" not in source
