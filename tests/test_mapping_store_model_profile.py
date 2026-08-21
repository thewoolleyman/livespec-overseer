"""Mapping-store model_profile schema plumbing."""

import dataclasses
import json

import _registry_track_row_parse as row_parse
import pytest
import registry
from registry import Track

__all__: list[str] = []


def test_track_accepts_optional_model_profile():
    model_profile = {"harness": "codex", "model": "gpt-5-codex", "wrapper": None}

    track = Track(topic="profiled", repo="/r", model_profile=model_profile)

    assert track.model_profile == model_profile
    assert dataclasses.fields(registry.PlanTrack)[-2].kw_only is True


def test_model_profile_roundtrips_through_append_and_rewrite(*, tmp_path):
    store = tmp_path / "map.jsonl"
    model_profile = {
        "harness": "codex",
        "model": "gpt-5-codex",
        "statusline_model": "gpt-5.5 high",
        "wrapper": None,
    }
    registry.append_mapping(
        track=Track(
            topic="profiled",
            repo="/r",
            tmux="profiled",
            model_profile=model_profile,
        ),
        store_path=store,
    )

    assert registry.rewrite_mapping(keep=lambda *, row: True, store_path=store) == 0

    rows = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    assert rows[0]["model_profile"] == model_profile
    assert registry.read_valid_mapping(store_path=store)[0].model_profile == model_profile


def test_model_profile_absent_key_stays_absent(*, tmp_path):
    store = tmp_path / "map.jsonl"
    registry.append_mapping(track=Track(topic="plain", repo="/r", tmux="plain"), store_path=store)

    rows = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    assert "model_profile" not in rows[0]
    assert registry.read_valid_mapping(store_path=store)[0].model_profile is None


def test_malformed_model_profile_is_dropped_fail_soft(*, tmp_path, capsys):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps(
            {
                "topic": "bad",
                "repo": "/r",
                "tmux": "bad",
                "model_profile": {
                    "harness": "codex",
                    "model": "gpt-5-codex",
                    "wrapper": 42,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    track = registry.read_valid_mapping(store_path=store)[0]

    assert track.model_profile is None
    assert "dropping malformed model_profile" in capsys.readouterr().err


def test_model_profile_carrying_an_unknown_key_is_dropped_and_leaks_no_value(*, tmp_path, capsys):
    """A profile carrying an EXTRA key is REFUSED whole rather than quietly narrowed.

    This is the subset clause's own guard, and nothing else in the suite exercised it.
    Verified by deleting that clause on 2026-08-21: the entire suite stayed green at
    100% coverage, because the compound condition's branch was still taken by the
    wrong-TYPE case above. A sub-clause of a compound condition is invisible to branch
    coverage, so the leg needs a test that targets it specifically.

    BE PRECISE ABOUT WHAT THIS PROVES. The no-secrets property has two layers, and
    removing the subset clause does not by itself leak a value: the decoder rebuilds
    the profile from three NAMED keys, so an unknown key is stripped on the way out
    either way. What the subset clause adds is REFUSAL -- a row carrying anything
    unexpected is dropped entirely and warned about, instead of being silently
    accepted minus the surprise. That distinction matters because silent narrowing
    would let a row that someone believed carried more than it does pass as valid.

    The leak assertion below is therefore belt-and-braces on the second layer, not the
    discriminating leg; the discriminating leg is that the profile is None.
    """
    planted = "PLANTED-NOT-A-REAL-CREDENTIAL-0123456789"
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps(
            {
                "topic": "leaky",
                "repo": "/r",
                "tmux": "leaky",
                "model_profile": {
                    "harness": "claude",
                    "model": "opus[1m]",
                    "wrapper": "/opt/bin/claude-local-llm",
                    "auth_token": planted,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    track = registry.read_valid_mapping(store_path=store)[0]

    assert track.model_profile is None
    assert "dropping malformed model_profile" in capsys.readouterr().err
    # The whole profile is refused, so the planted value reaches no field of the Track.
    assert planted not in repr(dataclasses.asdict(track))


@pytest.mark.parametrize(
    ("label", "profile"),
    [
        ("missing the wrapper key", {"harness": "claude", "model": "opus[1m]"}),
        ("missing the model key", {"harness": "claude", "wrapper": None}),
        ("missing the harness key", {"model": "opus[1m]", "wrapper": None}),
        ("harness is not a string", {"harness": 7, "model": "opus[1m]", "wrapper": None}),
        ("model is not a string", {"harness": "claude", "model": [], "wrapper": None}),
        (
            "statusline_model is not a string",
            {"harness": "claude", "model": "opus[1m]", "wrapper": None, "statusline_model": 5},
        ),
        ("profile is not an object", "opus[1m]"),
    ],
)
def test_every_model_profile_validation_clause_drops_the_row(*, tmp_path, capsys, label, profile):
    """One case per validation clause, because branch coverage cannot see inside a compound `if`.

    `model_profile_from_row` refuses a row through a single seven-clause condition.
    Branch coverage records only that the condition evaluated both ways, never which
    disjunct decided it — so one malformed case marks the whole predicate covered while
    every other clause sits unexercised and could be deleted silently.

    Measured on 2026-08-21 by deleting each clause in turn and running the FULL suite:
    four of the six survived green (the two required-key clauses, both remaining type
    clauses, and the statusline type clause), while only the wrapper-type and
    no-extra-keys clauses were held by a test. This table closes that gap and is
    discriminating by construction: each row is decided by a different clause, so
    removing any one of them turns exactly one row red.

    These are FAIL-SOFT guards. A malformed row must degrade to "no profile recorded"
    and relaunch as it does today, never crash the daemon and never half-apply a
    profile — which is the epic's fourth property, and it rests on these clauses.
    """
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps({"topic": "t", "repo": "/r", "tmux": "t", "model_profile": profile}) + "\n",
        encoding="utf-8",
    )

    track = registry.read_valid_mapping(store_path=store)[0]

    assert track.model_profile is None, label
    assert "dropping malformed model_profile" in capsys.readouterr().err, label


def test_track_variant_helpers_and_unassigned_properties_are_covered():
    unassigned = registry.UnassignedPlan.make(repo="/r", topic="t")
    assert unassigned.added_at is None
    assert unassigned.model_profile is None
    assert unassigned.ctx_threshold is None
    assert unassigned.pinned_session_id is None
    assert unassigned.observed_session_identity is None
    assert registry.Track.make_unassigned(repo="/r", topic="t").kind == "unassigned_plan"
    assert registry.Track(topic="t", repo="/r", assigned=False).kind == "unassigned_plan"
    assert registry.track_with_epic(track=unassigned, epic="overseer-t") is unassigned
    assert registry.unresolved_plan_epic(topic="t") == "legacy-unresolved:t"
    assert registry.epic_is_resolved(epic="overseer-real") is True
    assert registry.epic_is_resolved(epic="legacy-unresolved:t") is False
    assert registry.epic_is_resolved(epic=None) is False

    assert row_parse.optional_model_profile(value=None) is None
    assert row_parse.optional_model_profile(value={"model": 1}) is None
    assert row_parse.optional_model_profile(value={"model": "gpt", "wrapper": None}) == {
        "model": "gpt",
        "wrapper": None,
    }


def test_track_variant_constructor_failures_are_covered():
    with pytest.raises(ValueError, match="missing_topic"):
        row_parse.require_str(row={}, key="topic")
    with pytest.raises(ValueError, match="missing_tmux"):
        row_parse.require_str(row={"tmux": ""}, key="tmux")
    with pytest.raises(ValueError, match="missing_epic"):
        row_parse.require_str(row={"epic": None}, key="epic")
    with pytest.raises(ValueError, match="plan track requires tmux"):
        registry.PlanTrack(topic="t", repo="/r", tmux="", epic="overseer-t")
    with pytest.raises(ValueError, match="plan track requires epic"):
        registry.PlanTrack(topic="t", repo="/r", tmux="t", epic="")
    with pytest.raises(ValueError, match="supervisor seat requires tmux"):
        registry.SupervisorSeat(
            topic="t-supervisor",
            repo="/r",
            tmux="",
            epic="overseer-t",
            supervised_topic="t",
        )
    with pytest.raises(ValueError, match="supervisor seat requires epic"):
        registry.SupervisorSeat(
            topic="t-supervisor",
            repo="/r",
            tmux="t-supervisor",
            epic="",
            supervised_topic="t",
        )
    with pytest.raises(ValueError, match="supervisor seat requires supervised topic"):
        registry.SupervisorSeat(
            topic="t-supervisor",
            repo="/r",
            tmux="t-supervisor",
            epic="overseer-t",
            supervised_topic="",
        )
    supervisor = registry.SupervisorSeat(
        topic="t-supervisor",
        repo="/r",
        tmux="t-supervisor",
        epic="overseer-t",
        supervised_topic="t",
    )
    assert supervisor.assigned is True
    with pytest.raises(ValueError, match="foreman seat requires tmux"):
        registry.ForemanSeat(topic="repo-foreman", repo="/r", tmux="", epic="overseer-f")
    foreman = registry.ForemanSeat(
        topic="repo-foreman",
        repo="/r",
        tmux="repo-foreman",
        epic="overseer-f",
    )
    assert foreman.assigned is True
    assert foreman.is_unassigned is False


def test_track_from_mapping_row_rejects_unknown_and_malformed_reserved_kinds():
    extras = row_parse.RowExtras(
        resume=None,
        ctx_threshold=None,
        pinned_session_id=None,
        observed_session_identity=None,
        added_at=None,
        model_profile=None,
    )
    with pytest.raises(ValueError, match="missing_supervised_topic"):
        row_parse.track_from_mapping_row(
            row={
                "kind": "supervisor",
                "topic": "plain",
                "repo": "/r",
                "tmux": "plain",
                "epic": "overseer-t",
            },
            extras=extras,
        )
    with pytest.raises(ValueError, match="unknown_kind:mystery"):
        row_parse.track_from_mapping_row(
            row={
                "kind": "mystery",
                "topic": "plain",
                "repo": "/r",
                "tmux": "plain",
                "epic": "overseer-t",
            },
            extras=extras,
        )
