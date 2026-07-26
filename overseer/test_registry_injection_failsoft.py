"""Tests for registry.py — the injection-stamp sidecar's fail-soft behaviour.

Split from `test_registry_injection.py` at the second of the two section banners
that module carried. Those two sections were deliberately kept together when
`test_registry.py` was first cut up, on the ground that both cover the same module
surface; the keyword-only conversion (`overseer-bg2.9`) re-wrapped enough call sites
to take the combined module past the 200-LLOC soft ceiling, so the cheaper of the two
cohesion arguments gives way. The seam is unchanged — it is the banner the module
already drew.

Its sibling owns the sidecar working AS INTENDED: repo-qualified stamp round-trips,
notified bands, resume-pending, atomic row writes. THIS module owns what happens when
the value on disk is corrupt, legacy, or half-shaped — a bare JSON array where an
object belongs, a round dict with no `at`, a non-numeric stamp, a non-list `bands`,
a band or resume-pending write against a track with no open round, and the legacy
bare-scalar upgrade path.

``import registry`` resolves via conftest.py.
"""

import json

import pytest
import registry

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    """Every test runs with cwd inside tmp_path (repo convention)."""
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Injection-stamp sidecar: fail-soft over a corrupt / legacy / half-shaped value.
# --------------------------------------------------------------------------- #


def test_injection_stamp_fail_soft_when_the_sidecar_is_not_a_json_object(*, tmp_path, capsys):
    """Well-formed JSON of the WRONG shape (a bare array) is reported distinctly
    from malformed JSON, and every reader degrades to its empty answer."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(json.dumps([1, 2]), encoding="utf-8")

    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []
    assert registry.read_resume_pending(repo="/r", topic="t", stamp_path=stamp) is False
    assert "is not a JSON object" in capsys.readouterr().err


def test_read_injection_stamp_is_none_when_the_round_dict_has_no_at(*, tmp_path):
    """A dict-shaped value that never opened a round (no ``at``) has no timestamp —
    but the rest of the entry is still readable, so it is not discarded wholesale."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(
        json.dumps({"/r\tt": {"bands": [45], "resume_pending": True}}), encoding="utf-8"
    )
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == [45]
    assert registry.read_resume_pending(repo="/r", topic="t", stamp_path=stamp) is True


def test_read_injection_stamp_warns_and_returns_none_on_a_non_numeric_stamp(*, tmp_path, capsys):
    """Both sidecar shapes name the offending track on an unusable ``at``. ``true``
    is deliberately NOT numeric (jsonio.as_float rejects bool, which is an int
    subclass), so it must not silently read back as 1.0."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(
        json.dumps({"/r\tdict": {"at": True}, "/r\tlegacy": "not-a-number"}), encoding="utf-8"
    )
    assert registry.read_injection_stamp(repo="/r", topic="dict", stamp_path=stamp) is None
    assert registry.read_injection_stamp(repo="/r", topic="legacy", stamp_path=stamp) is None

    err = capsys.readouterr().err
    assert "non-numeric injection stamp for /r::dict" in err
    assert "non-numeric injection stamp for /r::legacy" in err


def test_read_notified_bands_ignores_a_non_list_bands_member(*, tmp_path):
    """A ``bands`` member of the wrong type reads as "nothing notified yet" without
    costing the entry its still-usable ``at``."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(json.dumps({"/r\tt": {"at": 500.0, "bands": "45"}}), encoding="utf-8")
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 500.0


def test_add_notified_band_on_a_track_with_no_open_round(*, tmp_path):
    """Part 2: an absent key yields a bare bands-only entry — the band is recorded
    without inventing an ``at`` (no round was opened, so none may certify)."""
    stamp = tmp_path / "stamps.json"
    registry.add_notified_band(repo="/r", topic="t", band=45, stamp_path=stamp)
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == [45]
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None


def test_set_resume_pending_on_a_track_with_no_open_round(*, tmp_path):
    """R1: the retry keys on the FLAG, not on ``at`` — an absent key is written as a
    bare {"resume_pending": true} so the submit still retries."""
    stamp = tmp_path / "stamps.json"
    registry.set_resume_pending(repo="/r", topic="t", stamp_path=stamp)
    assert registry.read_resume_pending(repo="/r", topic="t", stamp_path=stamp) is True
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None


def test_set_resume_pending_upgrades_a_legacy_bare_scalar_value(*, tmp_path):
    """R1 back-compat: a legacy bare-float value is upgraded to the dict shape with
    the float preserved as ``at``; a legacy bare NON-numeric value is unusable, so
    the upgrade keeps only the flag."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(
        json.dumps({"/r\tnumeric": 321.0, "/r\tjunk": "not-a-number"}), encoding="utf-8"
    )
    registry.set_resume_pending(repo="/r", topic="numeric", stamp_path=stamp)
    registry.set_resume_pending(repo="/r", topic="junk", stamp_path=stamp)

    assert registry.read_resume_pending(repo="/r", topic="numeric", stamp_path=stamp) is True
    assert (
        registry.read_injection_stamp(repo="/r", topic="numeric", stamp_path=stamp) == 321.0
    )  # `at` preserved
    assert registry.read_resume_pending(repo="/r", topic="junk", stamp_path=stamp) is True
    assert (
        registry.read_injection_stamp(repo="/r", topic="junk", stamp_path=stamp) is None
    )  # unusable → dropped
