"""A host ahead of the delivery counter (overseer-ceehcd, proposal #3094).

A host whose apply step refuses with `stale-sequence <seq> host-applied <n>` and
n greater than the pushed sequence is AHEAD: the service's counter is behind the
host, for example after the counter was lost. The host is shown `ahead`, is not
recorded as a failed push, and is resolved by moving the counter FORWARD past
it and reissuing the current delivery with the next sequence. It is never
exempted from retry, and never moved backwards.
"""

from __future__ import annotations

import ast
import importlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

TOKEN = "tok-" + "secret-ahead"


def _at_once(*, task: Callable[[], None]) -> None:
    task()


def _write(*, path: Path, body: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(body), encoding="utf-8")


def _live(*, home: Path) -> None:
    _write(
        path=home / ".claude/.credentials.json",
        body={
            "claudeAiOauth": {
                "accessToken": TOKEN,
                "expiresAt": 9_999_999_999_000,
                "refreshToken": "r",
            }
        },
    )
    _write(
        path=home / ".claude.json", body={"oauthAccount": {"accountUuid": "acct-a"}, "userID": "u"}
    )


def _hosts(*, home: Path, text: str) -> None:
    push = importlib.import_module("caam_delivery_push")
    (home / push.HOSTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    _ = (home / push.HOSTS_FILE).write_text(text, encoding="utf-8")


def _counter(*, home: Path) -> object:
    push = importlib.import_module("caam_delivery_push")
    path = home / push.STATE_DIR / "delivery-sequence.json"
    return json.loads(path.read_text(encoding="utf-8")).get("sequence")


def _sequence_sent(*, program: str) -> int | None:
    """The delivery sequence an apply program carries; None for any other program."""
    push = importlib.import_module("caam_delivery_push")
    if not program.startswith(push.APPLY_SCRIPT):
        return None
    call = program[len(push.APPLY_SCRIPT) :].strip()
    assert call.startswith("main(") and call.endswith(")")
    payload = ast.literal_eval(call[len("main(") : -1])
    return int(json.loads(payload)["sequence"])


def test_a_host_ahead_of_the_counter_is_shown_ahead_not_failed(*, tmp_path: Path) -> None:
    push = importlib.import_module("caam_delivery_push")
    service = importlib.import_module("caam_delivery_service")
    status = importlib.import_module("caam_delivery_push_status")
    delivery = service.Delivery(
        sequence=31, account_id="acct-a", identity={}, oauth={"accessToken": TOKEN, "expiresAt": 9}
    )
    _hosts(home=tmp_path, text="ahead u@ahead linux\n")

    def fake_run(*, target: str, **_: object) -> tuple[int, str]:
        assert target == "u@ahead"
        return 0, "stale-sequence 31 host-applied 40"

    _ = push.push_due(home=tmp_path, delivery=delivery, now=50.0, run=fake_run)
    entry = push.load_state(home=tmp_path)["ahead"]
    assert entry["state"] == "ahead"
    assert entry["host_applied"] == 40
    assert "last_success" not in entry
    assert (
        status.host_state(entry=entry, current_sequence=31, now=60.0, stale_after=900.0) == "ahead"
    )
    # Once the counter has moved past the host, it is no longer ahead.
    assert (
        status.host_state(entry=entry, current_sequence=41, now=60.0, stale_after=900.0) != "ahead"
    )
    # not-converted still takes precedence over ahead.
    assert (
        status.host_state(
            entry={**entry, "state": "not-converted"},
            current_sequence=31,
            now=60.0,
            stale_after=900.0,
        )
        == "not-converted"
    )
    service.write_private_json(
        path=tmp_path / push.STATE_DIR / "delivery-sequence.json", value={"sequence": 31}
    )
    text = "\n".join(status.status_lines(home=tmp_path, now=60.0, reissue_available=True))
    assert "ahead  u@ahead  linux  ahead host-applied 40  " in text


def test_a_host_ahead_moves_the_counter_forward_and_never_the_host_back(*, tmp_path: Path) -> None:
    push = importlib.import_module("caam_delivery_push")
    entry = importlib.import_module("caam_delivery_push_entry")
    status = importlib.import_module("caam_delivery_push_status")
    _live(home=tmp_path)
    _hosts(home=tmp_path, text="ahead u@ahead linux\nbehind u@behind linux\n")
    host_applied = {"u@ahead": 40, "u@behind": 0}
    sent: list[tuple[str, int]] = []

    def fake_run(*, target: str, program: str, **_: object) -> tuple[int, str]:
        sequence = _sequence_sent(program=program)
        if sequence is None:
            return 0, '{"reissued": []}'
        sent.append((target, sequence))
        if sequence <= host_applied[target]:
            return 0, f"stale-sequence {sequence} host-applied {host_applied[target]}"
        host_applied[target] = sequence
        return 0, f"applied {sequence}"

    loop = entry.PushLoop()
    run = {"confirm": lambda **_: "acct-a", "run": fake_run, "start": _at_once}
    entry.run_once(home=tmp_path, now=100.0, loop=loop, **run)

    # The first delivery is sequence 1; the host ahead at 40 refuses it, so the
    # counter is moved to 40 and the current delivery is reissued as 41 to every host.
    assert ("u@ahead", 1) in sent and ("u@behind", 1) in sent
    assert ("u@ahead", 41) in sent and ("u@behind", 41) in sent
    assert _counter(home=tmp_path) == 41
    assert loop.last is not None and loop.last.sequence == 41
    assert host_applied == {"u@ahead": 41, "u@behind": 41}
    state = push.load_state(home=tmp_path)
    for label in ("ahead", "behind"):
        assert state[label]["state"] == "ok" and state[label]["sequence"] == 41
        assert (
            status.host_state(entry=state[label], current_sequence=41, now=100.0, stale_after=900.0)
            == "current"
        )
    # Every delivery the host ahead was sent after the refusal is above what it held.
    assert all(sequence > 40 for target, sequence in sent if target == "u@ahead" and sequence != 1)


def test_a_host_ahead_is_never_exempted_from_retry(*, tmp_path: Path) -> None:
    entry = importlib.import_module("caam_delivery_push_entry")
    _live(home=tmp_path)
    _hosts(home=tmp_path, text="ahead u@ahead linux\n")
    replies = ["stale-sequence 1 host-applied 40", "failed timeout", "failed timeout", "applied 41"]
    sent: list[int] = []

    def fake_run(*, program: str, **_: object) -> tuple[int, str]:
        sequence = _sequence_sent(program=program)
        if sequence is None:
            return 0, '{"reissued": []}'
        sent.append(sequence)
        return 0, replies[len(sent) - 1]

    loop = entry.PushLoop()
    run = {"confirm": lambda **_: "acct-a", "run": fake_run, "start": _at_once}
    entry.run_once(home=tmp_path, now=100.0, loop=loop, **run)
    assert sent == [1, 41]
    entry.run_once(home=tmp_path, now=110.0, loop=loop, **run)
    assert sent == [1, 41]
    # The default retry interval is 60 s: the host is pushed again, not exempted.
    entry.run_once(home=tmp_path, now=161.0, loop=loop, **run)
    assert sent == [1, 41, 41]
    entry.run_once(home=tmp_path, now=222.0, loop=loop, **run)
    assert sent == [1, 41, 41, 41]


def test_a_corrupt_applied_sequence_file_reads_as_zero(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    host = tmp_path / "host"
    _write(path=host / ".claude/.credentials.json", body={})
    _write(path=host / ".claude.json", body={})
    _ = (host / ".claude/.caam-delivery-sequence").write_text("not-a-number", encoding="utf-8")
    monkeypatch.setenv("HOME", str(host))
    payload = json.dumps(
        {
            "sequence": 5,
            "account_id": "a",
            "identity": {"oauthAccount": {"accountUuid": "a"}, "userID": "u"},
            "oauth": {"accessToken": "t5", "expiresAt": 1},
        }
    )
    code = 0
    try:
        program = push.apply_program(payload=payload)
        exec(compile(program, "<apply>", "exec"), {"__name__": "__main__"})  # noqa: S102
    except SystemExit as stop:
        code = int(stop.code or 0)
    assert (code, capsys.readouterr().out.strip()) == (0, "applied 5")
    assert (host / ".claude/.caam-delivery-sequence").read_text(encoding="utf-8") == "5"
