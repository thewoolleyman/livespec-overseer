"""An operator's `--session-model=<s>=auto` must survive the pass that performs it.

THE DEFECT. Clearing a session's model exception worked in memory and was never
written. The pass reported correctly -- the exceptions line disappeared, the
blocked-pin warnings disappeared, the sessions really were driven to the new
model -- and the state file kept the old entry, so the next scheduled tick read
it back and silently restored the exception within thirty minutes.

THE MECHANISM, measured rather than assumed. `model_messages` called
`enforce_models` without passing `state`, so `_loaded_state` fell through to
`load_state(state_path=...)` and handed enforcement a FRESH dict read from disk.
Every exception mutation landed on that dict. Enforcement then saved it, which is
why the file was briefly correct -- and the pass afterwards saved its OWN,
unmutated `context.state` from `decide`, overwriting the correct write with the
stale one. Two save paths, one pass, and the last writer held the old value.

That is why every assertion here reads what was WRITTEN, and why the pass is
driven end to end rather than by calling the apply function directly. An
assertion on the returned SessionModelExceptions, or on the state immediately
after enforcement, passes against the broken implementation: the in-memory clear
was never the broken half.

It is the same shape as the carrier N3a defect this plan already fixed once --
enforcement writing state that a caller then discarded.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from caam_decision import UsageRecord
from caam_enforcement import enforce_models as real_enforce_models
from caam_profile_state import STATE_REL
from caam_profile_state import save_state as real_save_state

from tests.test_caam_anthropic_loop import (
    FakeProcess,
    caam_loop_module,
    write_creds,
    write_snapshot,
)

_SESSION = "livespec-overseer-foreman"


def _usage() -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=80.0,
        seven_day_remaining=70.0,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


def _seed_state(*, home: Path, session_models: dict[str, str]) -> Path:
    state_path = home / STATE_REL
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"session_models": session_models}), encoding="utf-8")
    return state_path


def _saved_session_models(*, state_path: Path) -> dict[str, str]:
    """What the LAST writer of the pass left on disk -- the only thing a later tick reads."""
    stored = json.loads(state_path.read_text(encoding="utf-8"))
    return stored.get("session_models", {})


def _run_real_pass(*, home: Path, argv: list[str]) -> None:
    """Drive a whole pass with the REAL enforcement and a REAL save, as production does.

    Both save paths must be live for this to mean anything: enforcement's own
    save and the save `decide` performs at the end of the pass. Stubbing either
    one hides the ordering hazard that is the entire defect.
    """
    module = caam_loop_module()
    write_snapshot(home=home, name="active", credential="active", expires_at_s=30_000.0)
    write_creds(path=home / ".claude" / ".credentials.json", bearer="active", expires_at_s=30_000.0)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del creds_path, now
        return _usage(), None

    code = module.run_pass(
        flags=module.parse_flags(argv=argv),
        home=home,
        now=2_000.0,
        stdout=lambda line: None,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=real_save_state,
        agent_runner=None,
        enforce_models=real_enforce_models,
    )
    assert code == 0


@pytest.mark.parametrize("extra", [[], ["--no-models"]])
def test_clearing_an_exception_is_written_not_merely_applied(
    *, tmp_path: Path, extra: list[str]
) -> None:
    """Both paths, because they persist by DIFFERENT code.

    Only `--no-models` reaches `_persist_session_model_requests`; the ordinary
    path mutates and saves inside enforcement itself. A fix applied to one leaves
    the other reverting on the next tick, so neither may stand in for the other.
    """
    state_path = _seed_state(home=tmp_path, session_models={_SESSION: "fable"})

    _run_real_pass(home=tmp_path, argv=[f"--session-model={_SESSION}=auto", *extra])

    assert (
        _saved_session_models(state_path=state_path) == {}
    ), "the cleared exception is still on disk; the next tick will restore it"


@pytest.mark.parametrize("extra", [[], ["--no-models"]])
def test_setting_an_exception_is_written_not_merely_applied(
    *, tmp_path: Path, extra: list[str]
) -> None:
    """The same hazard in the other direction: a set that never reaches the file."""
    state_path = _seed_state(home=tmp_path, session_models={})

    _run_real_pass(home=tmp_path, argv=[f"--session-model={_SESSION}=fable", *extra])

    assert _saved_session_models(state_path=state_path) == {_SESSION: "fable"}


def test_the_last_write_of_the_pass_carries_the_enforcement_mutation(*, tmp_path: Path) -> None:
    """THE ORDERING LEG, stated as the hazard rather than as an outcome.

    Two save paths run in one pass: enforcement saves the state it mutated, and
    `decide` saves the pass's own `context.state` afterwards. Whichever object
    `decide` holds is what a later tick will read, so the mutation must be on
    THAT object and not merely on some dict that was correct at an earlier
    instant. Recording every write and asserting on the LAST one is what
    distinguishes a fix from a well-timed coincidence -- the broken code also
    wrote the right value at one point in the pass, and then overwrote it.
    """
    state_path = _seed_state(home=tmp_path, session_models={_SESSION: "fable"})
    writes: list[dict[str, str]] = []

    def recording_save(*, state: dict[str, object], state_path: Path) -> None:
        stored = state.get("session_models")
        writes.append(dict(stored) if isinstance(stored, dict) else {})
        real_save_state(state=state, state_path=state_path)

    module = caam_loop_module()
    write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=30_000.0)
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json",
        bearer="active",
        expires_at_s=30_000.0,
    )

    code = module.run_pass(
        flags=module.parse_flags(argv=[f"--session-model={_SESSION}=auto"]),
        home=tmp_path,
        now=2_000.0,
        stdout=lambda line: None,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=lambda *, creds_path, now=None: (_usage(), None),
        save_state=recording_save,
        agent_runner=None,
        enforce_models=real_enforce_models,
    )

    assert code == 0
    assert writes, "the pass saved nothing at all, so this leg proves nothing"
    assert writes[-1] == {}, f"the pass's last write restored the exception: {writes}"
    assert _saved_session_models(state_path=state_path) == {}
