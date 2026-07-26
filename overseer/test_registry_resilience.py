"""Fail-soft resilience of registry.py's mapping store (adversarial review B6/B7).

Split out of `test_registry.py` at the section banner it already carried, when
that module crossed the 250-LLOC hard ceiling. These tests own ONE property: a
corrupt, unreadable, or unwritable store degrades rather than crashing the daemon
that supervises every track. The happy-path store API lives in
`test_registry.py`.

Denial is injected at the `Path` method rather than via `chmod`, because CI runs
as a user for whom a mode-stripped file is still readable.

``import registry`` resolves via conftest.py.
"""

import fcntl
import json
import os
from pathlib import Path

import _registry_store
import pytest
import registry
from registry import Track

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Every test runs with cwd inside tmp_path (repo convention)."""
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Fail-soft store resilience (B6/B7): a corrupt, unreadable, or unwritable store
# must degrade ONE reader/writer and never crash the daemon that supervises all
# tracks. Every case asserts the fail-soft RESULT, not merely that nothing raised.
# --------------------------------------------------------------------------- #


def test_file_lock_proceeds_unlocked_when_the_lock_cannot_be_acquired(
    tmp_path, monkeypatch, capsys
):
    """B7: losing the lock race is better than losing the daemon — an unlockable
    store falls back to an UNLOCKED read-modify-write and the append still lands."""
    store = tmp_path / "map.jsonl"

    def _refuse_flock(_fd, _operation):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(fcntl, "flock", _refuse_flock)
    registry.append_mapping(track=Track(topic="a", repo="/r", tmux="r-a"), store_path=store)

    assert [t.topic for t in registry.read_mapping(store_path=store)] == ["a"]  # write still landed
    assert "could not acquire lock" in capsys.readouterr().err


def test_file_lock_proceeds_unlocked_when_the_lock_file_cannot_be_opened(
    tmp_path, monkeypatch, capsys
):
    """B7: the lock sidecar failing to OPEN (no handle was ever acquired) takes the
    same unlocked fallback — the caller runs and reports, and the daemon lives.

    The denial is injected at ``Path.open`` rather than via ``chmod``: CI runs its
    container steps as ROOT, where mode bits deny nothing, so a chmod-based version
    of this test passes locally and silently stops exercising the branch in CI.
    """
    unwritable = tmp_path / "unwritable"
    unwritable.mkdir()
    store = unwritable / "map.jsonl"
    real_open = Path.open

    def _deny(self, *args, **kwargs):
        if str(self).startswith(str(unwritable)):
            raise PermissionError(13, "Permission denied")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _deny)
    registry.append_mapping(track=Track(topic="a", repo="/r"), store_path=store)
    assert registry.read_mapping(store_path=store) == []  # the append itself also failed soft

    err = capsys.readouterr().err
    assert "could not acquire lock" in err
    assert "could not append to" in err
    assert not (unwritable / "map.jsonl.lock").exists()  # no lock sidecar was created


def test_read_mapping_fail_soft_on_an_unreadable_store(tmp_path, monkeypatch, capsys):
    """B7: a store that exists but cannot be read yields an EMPTY mapping (naming
    the offender), not a propagated PermissionError.

    Denial is injected at ``Path.read_text`` rather than via ``chmod`` — CI runs as
    root, where mode bits deny nothing (see the lock-open test above).
    """
    store = tmp_path / "map.jsonl"
    store.write_text(json.dumps({"topic": "a", "repo": "/r"}) + "\n", encoding="utf-8")

    def _deny(self, *args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", _deny)
    assert registry.read_mapping(store_path=store) == []
    assert "unreadable mapping store" in capsys.readouterr().err


def test_read_mapping_fail_soft_on_a_non_utf8_store(tmp_path, capsys):
    """B7 for a DIFFERENT exception class than the test above reaches.

    ``UnicodeDecodeError`` subclasses ``ValueError``, not ``OSError``, so the
    ``except OSError`` this store's read once carried let it propagate. Real bytes
    rather than a monkeypatched raise, so the assertion exercises the genuine decode
    path and cannot pass by mocking something production never does.

    Why it must fail soft: the daemon's per-iteration broad catch used to absorb it.
    That catch is removed under the "let it crash, systemd restarts" ruling, and a
    corrupt store is an ENVIRONMENTAL error — left unboundaried it would exit the
    daemon, systemd would restart it, the same bytes would be re-read, and the loop
    would never supervise anything again.
    """
    store = tmp_path / "map.jsonl"
    store.write_bytes(b'\xff\xfe{"topic": "a", "repo": "/r"}\n')

    assert registry.read_mapping(store_path=store) == []
    assert "unreadable mapping store" in capsys.readouterr().err


def test_watch_set_from_config_fail_soft_on_a_non_utf8_declaration(tmp_path):
    """A watch-set declaration of undecodable bytes yields the extras, like unparsable
    JSON does — the daemon still supervises what it was explicitly handed.

    Distinct from the malformed-JSON test above: that one raises
    ``json.JSONDecodeError``, this one raises ``UnicodeDecodeError`` BEFORE any parse
    is attempted, so the original ``(OSError, json.JSONDecodeError)`` tuple did not
    cover it.
    """
    declaration = tmp_path / "repos.json"
    declaration.write_bytes(b'\xff\xfe{"repos": []}')
    extra = tmp_path / "extra"
    extra.mkdir()

    result = registry.watch_set_from_config(config_path=declaration, extra_repos=[extra])

    assert [registry.repo_slug(repo=p) for p in result] == ["extra"]


def test_read_injection_stamp_is_none_on_a_non_utf8_sidecar(tmp_path):
    """An undecodable stamp sidecar reads as "no stamp", never raising.

    Fail-soft here is also fail-CLOSED in the safety sense: with no readable stamp
    there is no round-open timestamp, so no ready marker can be certified fresh
    against one, and nothing gets restarted on the strength of a corrupt file.
    """
    stamp = tmp_path / "stamps.json"
    stamp.write_bytes(b'\xff\xfe{"/r\\tt": {"at": 1000.0}}')

    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []


def test_atomic_write_fail_soft_leaves_the_store_intact_and_removes_the_temp(
    tmp_path, monkeypatch, capsys
):
    """B6/B7: a mid-write failure must never truncate the store nor leave a ``.tmp``
    turd behind — the temp file is unlinked and the old content survives whole."""
    store = tmp_path / "map.jsonl"
    store.write_text(json.dumps({"topic": "keep", "repo": "/r"}) + "\n", encoding="utf-8")

    def _boom(_fd):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", _boom)
    _registry_store._write_rows(rows=[{"topic": "replacement", "repo": "/r"}], store_path=store)

    assert [t.topic for t in registry.read_mapping(store_path=store)] == ["keep"]  # not truncated
    assert [p.name for p in tmp_path.iterdir()] == ["map.jsonl"]  # temp file cleaned up
    assert "could not write" in capsys.readouterr().err


def test_append_mapping_fail_soft_when_the_store_cannot_be_opened(tmp_path, capsys):
    """B7: an unopenable store path (here a DIRECTORY sitting where the file
    belongs) drops the append with a warning instead of crashing the caller."""
    store = tmp_path / "map.jsonl"
    store.mkdir()
    registry.append_mapping(track=Track(topic="a", repo="/r"), store_path=store)

    assert registry.read_mapping(store_path=store) == []  # nothing recorded, nothing raised
    assert "could not append to" in capsys.readouterr().err
