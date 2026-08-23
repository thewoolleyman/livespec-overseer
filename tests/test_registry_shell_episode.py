"""Tests for durable shell-only episode state in the stamp sidecar."""

import registry

__all__: list[str] = []


def test_shell_episode_roundtrip_preserves_injection_round(*, tmp_path):
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo="/r", topic="t", ts=500.0, stamp_path=stamp)

    registry.record_shell_episode(repo="/r", topic="t", since=1000.0, stamp_path=stamp)
    registry.record_shell_episode(repo="/r", topic="t", since=2000.0, stamp_path=stamp)

    assert registry.read_shell_episode(repo="/r", topic="t", stamp_path=stamp) == 1000.0
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 500.0
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []

    registry.clear_shell_episode(repo="/r", topic="t", stamp_path=stamp)

    assert registry.read_shell_episode(repo="/r", topic="t", stamp_path=stamp) is None
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 500.0
