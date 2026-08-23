"""Gates for the LLM half of the shipped foreman product.

The foreman runtime is split: deterministic Python computes fields such as
``exit_reason``, while the model consumes ``prose/foreman.md`` to decide what to
do with those fields. These tests keep the two halves connected.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import TypeAlias, cast

from foreman_act_types import ACTION_IDS

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / ".claude-plugin"
PROSE = PLUGIN_ROOT / "prose" / "foreman.md"
RUNTIME = PLUGIN_ROOT / "bin" / "foreman-runtime"
PROHIBITIONS = Path(__file__).with_name("foreman_contract_prohibitions.json")


def _scrubbed_env() -> dict[str, str]:
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }
    assert "PYTHONPATH" not in env
    return env


def _tmux(*, socket: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["tmux", "-S", str(socket), *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
        timeout=15.0,
    )


def _pane_pid(*, socket: Path, session: str) -> str:
    completed = _tmux(
        socket=socket,
        args=["display-message", "-p", "-t", session, "#{pane_pid}"],
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _snapshot(*, repo: Path, tick_generation: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "daemon_instance_id": "daemon-contract",
        "tick_generation": tick_generation,
        "written_at": "2026-08-06T10:00:00Z",
        "needs_attention": {
            "schema_version": 1,
            "generated_at": "2026-08-06T10:00:00Z",
            "items": [],
        },
        "rows": [
            {
                "repo": str(repo),
                "topic": "alpha",
                "tmux": "alpha",
                "runtime": "codex",
                "status": "session-gone",
                "session_identity": f"none:{repo}:alpha",
            }
        ],
    }


def _register_foreman_session(*, repo: Path, home: Path, socket: Path) -> None:
    created = _tmux(
        socket=socket,
        args=["new-session", "-d", "-s", "repo-foreman", "-c", str(repo), "sleep 60"],
    )
    assert created.returncode == 0, created.stderr
    pane_pid = _pane_pid(socket=socket, session="repo-foreman")
    proc_start = (Path("/proc") / pane_pid / "stat").read_text(encoding="utf-8").split()[21]
    sessions_dir = home / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / f"{pane_pid}.json").write_text(
        json.dumps(
            {
                "pid": int(pane_pid),
                "name": "repo-foreman",
                "cwd": str(repo),
                "status": "idle",
                "procStart": proc_start,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _run_runtime(
    *, repo: Path, home: Path, socket: Path, snapshot: dict[str, object], now: float
) -> dict[str, object]:
    snapshot_path = home / "runtime-status.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    env = {
        **_scrubbed_env(),
        "HOME": str(home),
        "TMUX": f"{socket},0,0",
    }
    completed = subprocess.run(  # noqa: S603
        [
            str(RUNTIME),
            "--repo",
            str(repo),
            "--watch-set-path",
            str(home / ".livespec-overseer-repos.json"),
            "--snapshot-path",
            str(snapshot_path),
            "--now-epoch",
            str(now),
        ],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    return parsed


def _missing_action_ids(*, text: str) -> list[str]:
    return [action_id for action_id in ACTION_IDS if action_id not in text]


CANONICAL_ESCALATION_PATH = "tmp/overseer/foreman/escalations/<repo-slug>-foreman.json"
AMBIGUOUS_ESCALATION_PATH = "escalations/<topic>.json"


def _escalation_filename_errors(*, text: str) -> list[str]:
    """Both defects that make a foreman escalation land somewhere unread.

    `_supervisor_foreman_escalation` resolves the file by the foreman track's topic,
    and `foreman_runtime_identity.canonical_session_name` makes that topic
    `<repo-slug>-foreman`. So that filename is the ONLY one the daemon reads. A
    contract that names `<topic>.json` invites a plan-topic name or a bare
    `foreman.json`, either of which is written and never surfaced — a silent loss,
    strictly worse than the blocking picker this path replaces.
    """
    errors: list[str] = []
    if CANONICAL_ESCALATION_PATH not in text:
        errors.append("canonical-escalation-path-absent")
    if AMBIGUOUS_ESCALATION_PATH in text:
        errors.append("ambiguous-escalation-path-present")
    return errors


CONVERGED_PICKER_PROHIBITION = "Do not raise a blocking picker for this decision"
CONVERGED_PROHIBITION_REASON = "no in-session clock left to bound it"
TermGroup: TypeAlias = tuple[str, ...]
RequiredProhibition: TypeAlias = tuple[str, tuple[TermGroup, ...]]
DeletionControl: TypeAlias = tuple[str, str]


def _normalised_contract_text(*, text: str) -> str:
    return " ".join(text.lower().replace("`", "").split())


def _load_required_prohibitions() -> tuple[RequiredProhibition, ...]:
    data = json.loads(PROHIBITIONS.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    prohibitions = data["required_prohibitions"]
    assert isinstance(prohibitions, list)
    return tuple(
        (
            cast(str, entry["id"]),
            tuple(
                tuple(cast(str, term) for term in group)
                for group in cast(list[list[object]], entry["term_groups"])
            ),
        )
        for entry in cast(list[dict[str, object]], prohibitions)
    )


def _load_deletion_controls() -> tuple[DeletionControl, ...]:
    data = json.loads(PROHIBITIONS.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    controls = data["deletion_controls"]
    assert isinstance(controls, list)
    return tuple(
        (cast(str, entry["id"]), cast(str, entry["deleted_text"]))
        for entry in cast(list[dict[str, object]], controls)
    )


def _required_prohibition_errors(*, text: str) -> list[str]:
    normalised = _normalised_contract_text(text=text)
    errors: list[str] = []
    for prohibition_id, term_groups in _load_required_prohibitions():
        for group in term_groups:
            if not any(_normalised_contract_text(text=term) in normalised for term in group):
                errors.append(prohibition_id)
                break
    return errors


def _contract_with_normalised_fragment_removed(*, text: str, fragment: str) -> str:
    normalised = _normalised_contract_text(text=text)
    normalised_fragment = _normalised_contract_text(text=fragment)
    assert normalised_fragment in normalised
    return normalised.replace(normalised_fragment, "", 1)


def _converged_prohibition_errors(*, text: str) -> list[str]:
    """The converged exit must FORBID a blocking picker, not merely offer an alternative.

    On `converged` the tick CANCELS its armed cron before surfacing the resume
    decision, so an unanswered blocking question leaves NO schedule at all — a
    strictly worse failure than the suppression this contract's other paragraph
    exists to prevent, which at least left the cron armed. The positive half (route
    the decision through the escalation marker) is already gated by
    `_exit_contract_errors`; deleting the PROHIBITION leaves every one of its
    required terms intact, so nothing catches its removal. The reason clause is
    gated with it because it is what makes the rule non-negotiable rather than a
    stylistic preference.
    """
    errors: list[str] = []
    if CONVERGED_PICKER_PROHIBITION not in text:
        errors.append("converged-picker-prohibition-absent")
    if CONVERGED_PROHIBITION_REASON not in text:
        errors.append("converged-prohibition-reason-absent")
    return errors


def _exit_contract_errors(*, text: str) -> list[str]:
    required = (
        "/loop",
        "hourly",
        "foreman-runtime",
        "exit_reason",
        "converged",
        "hard-tick-budget",
        "tmp/overseer/foreman/escalations/<repo-slug>-foreman.json",
        "foreman-escalated",
        "resume the loop",
        "token-free watcher remains armed",
        "O14/C5/O13/C6",
    )
    return [term for term in required if term not in text]


def test_all_shipped_action_ids_are_discoverable_from_the_contract() -> None:
    text = PROSE.read_text(encoding="utf-8")

    assert _missing_action_ids(text=text) == []
    sabotaged = text.replace("human_valve", "")
    assert _missing_action_ids(text=sabotaged) == ["human_valve"]


def test_runtime_exit_reason_is_carried_to_the_resume_question_contract(*, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "alpha").mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    socket = tmp_path / "tmux.sock"
    (home / ".livespec-overseer-repos.json").write_text(
        json.dumps({"repos": [str(repo)]}) + "\n", encoding="utf-8"
    )
    _register_foreman_session(repo=repo, home=home, socket=socket)
    try:
        first = _run_runtime(
            repo=repo,
            home=home,
            socket=socket,
            snapshot=_snapshot(repo=repo, tick_generation=1),
            now=1000.0,
        )
        assert first["exit_reason"] is None
        assert (
            _run_runtime(
                repo=repo,
                home=home,
                socket=socket,
                snapshot=_snapshot(repo=repo, tick_generation=1),
                now=1001.0,
            )["exit_reason"]
            is None
        )
        changed = _snapshot(repo=repo, tick_generation=2)
        assert (
            _run_runtime(repo=repo, home=home, socket=socket, snapshot=changed, now=4600.0)[
                "exit_reason"
            ]
            == "converged"
        )
        assert (
            _run_runtime(repo=repo, home=home, socket=socket, snapshot=changed, now=8200.0)[
                "exit_reason"
            ]
            == "converged"
        )
    finally:
        _tmux(socket=socket, args=["kill-server"])

    text = PROSE.read_text(encoding="utf-8")
    assert _exit_contract_errors(text=text) == []
    sabotaged = text.replace("foreman-escalated", "")
    assert _exit_contract_errors(text=sabotaged) == ["foreman-escalated"]


def test_the_contract_names_only_the_escalation_filename_the_daemon_reads() -> None:
    text = PROSE.read_text(encoding="utf-8")

    assert _escalation_filename_errors(text=text) == []

    # Discriminating control: the check must FAIL on each defect it exists to catch,
    # or it is a check that cannot fail and proves nothing about the contract.
    assert _escalation_filename_errors(text=text.replace(CANONICAL_ESCALATION_PATH, "")) == [
        "canonical-escalation-path-absent"
    ]
    assert _escalation_filename_errors(text=text + AMBIGUOUS_ESCALATION_PATH) == [
        "ambiguous-escalation-path-present"
    ]


def test_load_bearing_prohibitions_are_registered_as_a_contract_class() -> None:
    assert PROHIBITIONS.is_file()
    text = PROSE.read_text(encoding="utf-8")

    assert _required_prohibition_errors(text=text) == []

    for prohibition_id, deleted_text in _load_deletion_controls():
        without_prohibition = _contract_with_normalised_fragment_removed(
            text=text, fragment=deleted_text
        )
        assert _required_prohibition_errors(text=without_prohibition) == [prohibition_id]


def test_required_prohibitions_allow_cosmetic_contract_edits() -> None:
    text = PROSE.read_text(encoding="utf-8")
    original = (
        "Work state is whether\nfactory runs are in flight for that plan's children, sourced "
        "from the dispatch\njournal, never from the pane and never from local process views. "
    )
    reworded = (
        "Work state is sourced from the dispatch journal for that plan's children,\n"
        "never from local process views and never from the pane, and records whether\n"
        "factory runs are in flight. "
    )

    cosmetically_edited = text.replace(original, reworded)

    assert original in text
    assert _required_prohibition_errors(text=cosmetically_edited) == []


def test_deletion_controls_allow_cosmetic_contract_rewraps() -> None:
    text = PROSE.read_text(encoding="utf-8")
    original = (
        "Work state is whether\nfactory runs are in flight for that plan's children, sourced "
        "from the dispatch\njournal, never from the pane and never from local process views. "
    )
    rewrapped = (
        "Work state is whether factory runs are in flight for that plan's children,\n"
        "sourced from the dispatch journal, never from the pane and never from local\n"
        "process views. "
    )
    cosmetically_edited = text.replace(original, rewrapped)

    assert original in text
    assert _required_prohibition_errors(text=cosmetically_edited) == []
    for prohibition_id, deleted_text in _load_deletion_controls():
        without_prohibition = _contract_with_normalised_fragment_removed(
            text=cosmetically_edited, fragment=deleted_text
        )
        assert _required_prohibition_errors(text=without_prohibition) == [prohibition_id]


def test_the_converged_exit_forbids_a_blocking_picker_and_says_why() -> None:
    text = PROSE.read_text(encoding="utf-8")

    assert _converged_prohibition_errors(text=text) == []

    # Discriminating control. Each defect must produce its OWN failure, and the
    # control is written against the exact regression this gate exists for: the
    # positive terms `_exit_contract_errors` requires all survive deleting the
    # prohibition, so that check reports clean on a contract that has lost it.
    without_prohibition = text.replace(CONVERGED_PICKER_PROHIBITION, "")
    assert _converged_prohibition_errors(text=without_prohibition) == [
        "converged-picker-prohibition-absent"
    ]
    assert _exit_contract_errors(text=without_prohibition) == []

    assert _converged_prohibition_errors(text=text.replace(CONVERGED_PROHIBITION_REASON, "")) == [
        "converged-prohibition-reason-absent"
    ]
