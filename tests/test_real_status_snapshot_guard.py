import pytest


def test_real_status_snapshot_guard_fails_on_default_snapshot_write(
    *,
    real_status_snapshot_guard,
) -> None:
    with pytest.raises(pytest.fail.Exception, match="real overseer status snapshot"):
        real_status_snapshot_guard.assert_snapshot_write_allowed(
            path=real_status_snapshot_guard.path
        )


def test_real_status_snapshot_guard_has_no_external_file_state_check(
    *,
    real_status_snapshot_guard,
) -> None:
    assert not hasattr(real_status_snapshot_guard, "assert_unchanged")
