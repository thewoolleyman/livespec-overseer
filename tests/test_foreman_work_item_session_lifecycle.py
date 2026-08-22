"""Tests for bounded foreman work-item one-shot sessions."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
EXECUTABLE_PATH = OVERSEER_DIR / "foreman-act"


def foreman_act():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act")


def document(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {
            "snapshot": {"status": "ok", "mode": "daemon-snapshot"},
            "dispatch_journal": {"status": "ok", "records_read": 1},
        },
        "snapshot": {"daemon_instance_id": "daemon-1", "tick_generation": 7, "rows": []},
        "needs_attention": {"items": [{"id": "overseer-vts4lo", "kind": "work-item"}]},
        "dispatch_journal": [],
    }


def unattended_document(*, repo: Path) -> dict[str, object]:
    return {**document(repo=repo), "needs_attention": {"items": []}}


def proposal(
    *,
    repo: Path,
    action_id: str,
    classifier_action: str,
    terminal_status: str | None = None,
) -> dict[str, object]:
    work_item_id = "overseer-vts4lo"
    payload: dict[str, object] = {
        "work_item_id": work_item_id,
        "session_name": work_item_id,
        "handoff": "durable handoff\n",
    }
    if terminal_status is not None:
        payload["terminal"] = {"status": terminal_status, "reason": "measured terminal state"}
    classifier: dict[str, object] = {"action": classifier_action}
    if classifier_action == "start":
        classifier["start"] = {
            "repo": str(repo),
            "topic": work_item_id,
            "session_name": work_item_id,
        }
    if classifier_action == "exact_resume":
        classifier["resume"] = {
            "runtime": "codex",
            "repo": str(repo),
            "topic": work_item_id,
            "session_name": work_item_id,
            "session_id": "019fc11c-68c4-78c3-824b-d9b97de55a78",
            "transcript_path": "/home/me/.codex/sessions/rollout.jsonl",
        }
    return {
        "schema_version": 1,
        "action_id": action_id,
        "repo": str(repo),
        "topic": work_item_id,
        "session_name": work_item_id,
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": None,
        },
        "classifier": classifier,
        "work_item_session": payload,
    }


def proposal_for(
    *,
    repo: Path,
    work_item_id: str,
    action_id: str = "work_item_session_start",
    classifier_action: str = "start",
) -> dict[str, object]:
    original = proposal(repo=repo, action_id=action_id, classifier_action=classifier_action)
    original["topic"] = work_item_id
    original["session_name"] = work_item_id
    payload = original["work_item_session"]
    assert isinstance(payload, dict)
    payload["work_item_id"] = work_item_id
    payload["session_name"] = work_item_id
    return original


def state_dir(*, repo: Path) -> Path:
    return repo / "tmp" / "overseer" / "foreman" / "work-items" / "overseer-vts4lo"


def read_json(*, path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_repo_config(*, repo: Path, prefix: str = "overseer") -> None:
    repo.joinpath(".livespec.jsonc").write_text(
        json.dumps({"livespec-orchestrator-beads-fabro": {"connection": {"prefix": prefix}}}),
        encoding="utf-8",
    )


def write_fake_bd(*, directory: Path, statuses: dict[str, str]) -> None:
    script = directory / "bd"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        f"statuses = {json.dumps(statuses, sort_keys=True)}\n"
        "if len(sys.argv) == 4 and sys.argv[1] == 'show' and sys.argv[3] == '--json':\n"
        "    item_id = sys.argv[2]\n"
        "    if item_id in statuses:\n"
        "        print(json.dumps({'id': item_id, 'status': statuses[item_id]}))\n"
        "        raise SystemExit(0)\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def write_fake_tmux(*, directory: Path) -> Path:
    log = directory / "tmux-argv.jsonl"
    script = directory / "tmux"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"log = Path({json.dumps(str(log))})\n"
        "log.open('a', encoding='utf-8').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return log


def prepend_path(*, monkeypatch, directory: Path) -> None:
    monkeypatch.setenv("PATH", f"{directory}:{os.environ['PATH']}")


def act_with(
    *,
    repo: Path,
    proposal_payload: dict[str, object],
    calls: list[list[str]] | None = None,
) -> dict[str, object]:
    module = foreman_act()
    return module.act(
        proposal=proposal_payload,
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: document(repo=Path(repo)),
            run=lambda *, argv: (calls.append(argv) if calls is not None else None) or 0,
            append_journal=lambda *, repo, record: None,
        ),
    )


def test_work_item_session_start_accepts_own_tenant_item_without_attention_surface(
    *, tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_repo_config(repo=repo)
    write_fake_bd(directory=tmp_path, statuses={"overseer-vts4lo": "pending-approval"})
    prepend_path(monkeypatch=monkeypatch, directory=tmp_path)
    calls: list[list[str]] = []

    result = foreman_act().act(
        proposal=proposal(
            repo=repo,
            action_id="work_item_session_start",
            classifier_action="start",
        ),
        seams=foreman_act().ActSeams(
            gather=lambda *, repo, snapshot_path: unattended_document(repo=Path(repo)),
            run=lambda *, argv: (calls.append(argv) if calls is not None else None) or 0,
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result["reason"] == "work_item_session_started"
    assert calls != []


def test_work_item_session_refuses_missing_foreign_and_unadmitted_work_items(
    *, tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_repo_config(repo=repo)
    write_fake_bd(
        directory=tmp_path,
        statuses={
            "overseer-closed": "closed",
            "livespec-dev-tooling-real": "ready",
        },
    )
    prepend_path(monkeypatch=monkeypatch, directory=tmp_path)
    module = foreman_act()

    cases = [
        ("overseer-missing", "work_item_not_found"),
        ("overseer-closed", "work_item_status_not_admitted"),
        ("livespec-dev-tooling-real", "foreign_work_item_id"),
    ]

    for work_item_id, reason in cases:
        result = module.act(
            proposal=proposal_for(repo=repo, work_item_id=work_item_id),
            seams=module.ActSeams(
                gather=lambda *, repo, snapshot_path: unattended_document(repo=Path(repo)),
                run=lambda *, argv: 0,
                append_journal=lambda *, repo, record: None,
            ),
        )

        assert result["outcome"] == "refused"
        assert result["reason"] == reason


def test_foreman_act_executable_starts_fresh_ledger_item_without_attention_surface(
    *, tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_repo_config(repo=repo)
    write_fake_bd(directory=tmp_path, statuses={"overseer-vts4lo": "pending-approval"})
    tmux_log = write_fake_tmux(directory=tmp_path)
    prepend_path(monkeypatch=monkeypatch, directory=tmp_path)
    snapshot = {
        "schema_version": 1,
        "daemon_instance_id": "daemon-1",
        "tick_generation": 7,
        "written_at": "2026-08-22T00:00:00Z",
        "rows": [],
    }
    proposal_path = tmp_path / "proposal.json"
    snapshot_path = tmp_path / "snapshot.json"
    proposal_path.write_text(
        json.dumps(
            proposal(
                repo=repo,
                action_id="work_item_session_start",
                classifier_action="start",
            )
        ),
        encoding="utf-8",
    )
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    completed = subprocess.run(  # noqa: S603
        [
            str(EXECUTABLE_PATH),
            "--proposal",
            str(proposal_path),
            "--snapshot-path",
            str(snapshot_path),
        ],
        cwd=repo,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["reason"] == "work_item_session_started"
    assert json.loads(tmux_log.read_text(encoding="utf-8").splitlines()[0])[0:3] == [
        "new-session",
        "-d",
        "-s",
    ]


def test_work_item_session_create_to_terminal_cleanup_preserves_outcome(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    start = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo, action_id="work_item_session_start", classifier_action="start"
        ),
        calls=calls,
    )
    finish = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_finish",
            classifier_action="report_only",
            terminal_status="completed",
        ),
        calls=calls,
    )

    assert start["reason"] == "work_item_session_started"
    assert finish["reason"] == "work_item_session_completed"
    assert not (state_dir(repo=repo) / "claim.json").exists()
    assert read_json(path=state_dir(repo=repo) / "outcome.json")["status"] == "completed"
    assert read_json(path=state_dir(repo=repo) / "handoff.json")["work_item_id"] == (
        "overseer-vts4lo"
    )


def test_work_item_session_resume_refreshes_the_durable_handoff(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []
    start = proposal(repo=repo, action_id="work_item_session_start", classifier_action="start")
    resume = proposal(
        repo=repo,
        action_id="work_item_session_resume",
        classifier_action="exact_resume",
    )
    work_item = resume["work_item_session"]
    assert isinstance(work_item, dict)
    work_item["handoff"] = "fresh resume handoff\n"

    assert act_with(repo=repo, proposal_payload=start, calls=calls)["outcome"] == "acted"
    result = act_with(repo=repo, proposal_payload=resume, calls=calls)

    handoff = state_dir(repo=repo) / "handoff.md"
    assert result["reason"] == "work_item_session_resumed"
    assert handoff.read_text(encoding="utf-8") == "fresh resume handoff\n"
    assert str(handoff) in " ".join(calls[-1])


def test_work_item_session_retry_after_journaled_terminal_failure(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert (
        act_with(
            repo=repo,
            proposal_payload=proposal(
                repo=repo, action_id="work_item_session_start", classifier_action="start"
            ),
        )["outcome"]
        == "acted"
    )
    assert (
        act_with(
            repo=repo,
            proposal_payload=proposal(
                repo=repo,
                action_id="work_item_session_finish",
                classifier_action="report_only",
                terminal_status="failed",
            ),
        )["reason"]
        == "work_item_session_failed"
    )

    retry = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo, action_id="work_item_session_start", classifier_action="start"
        ),
    )

    assert retry["reason"] == "work_item_session_started"
    assert read_json(path=state_dir(repo=repo) / "claim.json")["attempt"] == 2


def test_work_item_session_queued_run_eviction_records_cleanup_evidence(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert (
        act_with(
            repo=repo,
            proposal_payload=proposal(
                repo=repo, action_id="work_item_session_start", classifier_action="start"
            ),
        )["outcome"]
        == "acted"
    )
    eviction = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_finish",
            classifier_action="report_only",
            terminal_status="evicted",
        ),
    )

    outcome = read_json(path=state_dir(repo=repo) / "outcome.json")
    assert eviction["reason"] == "work_item_session_evicted"
    assert outcome["status"] == "evicted"
    assert not Path(str(outcome["claim_path"])).exists()
