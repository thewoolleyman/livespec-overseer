"""Mapping-store model_profile schema plumbing."""

import dataclasses
import json

import registry
from registry import Track

__all__: list[str] = []


def test_track_accepts_optional_model_profile():
    model_profile = {"harness": "codex", "model": "gpt-5-codex", "wrapper": None}

    track = Track(topic="profiled", repo="/r", model_profile=model_profile)

    assert track.model_profile == model_profile
    assert dataclasses.fields(Track)[-2].kw_only is True


def test_model_profile_roundtrips_through_append_and_rewrite(*, tmp_path):
    store = tmp_path / "map.jsonl"
    model_profile = {
        "harness": "codex",
        "model": "gpt-5-codex",
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
