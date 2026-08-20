"""Coverage for resume-retry attempt counters in the stamp store."""

import registry

__all__: list[str] = []


def test_resume_retry_attempts_are_zero_without_pending_episode(*, tmp_path):
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo="/r", topic="t", ts=1000.0, stamp_path=stamp)

    assert registry.read_resume_retry_attempts(repo="/r", topic="t", stamp_path=stamp) == 0
    assert registry.record_resume_retry_attempt(repo="/r", topic="t", stamp_path=stamp) == 0
    assert registry.read_resume_retry_attempts(repo="/r", topic="t", stamp_path=stamp) == 0


def test_resume_retry_attempts_increment_only_while_pending(*, tmp_path):
    stamp = tmp_path / "stamps.json"
    registry.set_resume_pending(repo="/r", topic="t", stamp_path=stamp)

    assert registry.read_resume_retry_attempts(repo="/r", topic="t", stamp_path=stamp) == 0
    assert registry.record_resume_retry_attempt(repo="/r", topic="t", stamp_path=stamp) == 1
    assert registry.read_resume_retry_attempts(repo="/r", topic="t", stamp_path=stamp) == 1
