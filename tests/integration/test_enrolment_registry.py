"""Integration-tier enrolment registry: issuance, revocation and the audit log.

Drives the `caam-delivery-enrol` operator command in-process against a scratch
`HOME`, so the registry and the audit log land in a throwaway host state
directory. Every assertion reads the files the command wrote, never a value the
command returned.

The credential strings the command generates are random per call and are never
taken from a real credential, so nothing here is a credential fixture.
"""

import fcntl
import hashlib
import json
import os
import re
import stat
from pathlib import Path

import caam_delivery_registry
import pytest

from overseer import caam_delivery_enrol

__all__: list[str] = []

_STATE_DIR = Path(".local/state/caam-usage-rotate")
_REGISTRY = _STATE_DIR / "enrolment-registry.json"
_AUDIT = _STATE_DIR / "delivery-audit.log"


def _run(*, argv, home, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(home))
    try:
        code = caam_delivery_enrol.main(argv=argv)
    except SystemExit as stopped:
        code = stopped.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _issue(*, label, identity, home, monkeypatch, capsys):
    return _run(
        argv=["issue", "--label", label, "--network-identity", identity],
        home=home,
        monkeypatch=monkeypatch,
        capsys=capsys,
    )


def _registry_bytes(*, home):
    path = home / _REGISTRY
    return path.read_bytes() if path.exists() else None


def _audit_records(*, home):
    path = home / _AUDIT
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_enrolling_under_a_label_or_identity_already_in_use_is_refused(
    *, tmp_path, monkeypatch, capsys
):
    code, first_out, _ = _issue(
        label="laptop", identity="device-a", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    assert code == 0
    assert first_out.strip()
    before = _registry_bytes(home=tmp_path)
    audit_before = _audit_records(home=tmp_path)

    for label, identity in (("laptop", "device-b"), ("other", "device-a")):
        code, out, err = _issue(
            label=label, identity=identity, home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
        )
        assert code == 1
        assert out == ""
        assert "refus" in err.lower()
        assert _registry_bytes(home=tmp_path) == before
        assert _audit_records(home=tmp_path) == audit_before

    code, out, _ = _issue(
        label="desk", identity="device-c", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    assert code == 0
    assert out.strip() != first_out.strip()
    assert hashlib.sha256(first_out.strip().encode()).hexdigest() in (
        (tmp_path / _REGISTRY).read_text(encoding="utf-8")
    )


def _revoke(*, label, home, monkeypatch, capsys):
    return _run(
        argv=["revoke", "--label", label], home=home, monkeypatch=monkeypatch, capsys=capsys
    )


def _entries(*, home):
    document = json.loads((home / _REGISTRY).read_text(encoding="utf-8"))
    return document["entries"]


def _digest(*, credential):
    return hashlib.sha256(credential.encode()).hexdigest()


def test_a_revoked_device_can_be_enrolled_again(*, tmp_path, monkeypatch, capsys):
    _, old_out, _ = _issue(
        label="laptop", identity="device-a", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    old_credential = old_out.strip()
    code, out, _ = _revoke(label="laptop", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0
    assert out == ""

    code, new_out, _ = _issue(
        label="laptop", identity="device-a", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    new_credential = new_out.strip()
    assert code == 0
    assert new_credential
    assert new_credential != old_credential

    revoked_entry, new_entry = _entries(home=tmp_path)
    assert revoked_entry["revoked"] is True
    assert revoked_entry["credential_digest"] == _digest(credential=old_credential)
    assert new_entry["revoked"] is False
    assert new_entry["credential_digest"] == _digest(credential=new_credential)
    registry_text = (tmp_path / _REGISTRY).read_text(encoding="utf-8")
    assert old_credential not in registry_text
    assert new_credential not in registry_text

    before = _registry_bytes(home=tmp_path)
    for label in ("ghost", "laptop-never-enrolled"):
        code, out, err = _revoke(label=label, home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)
        assert code == 1
        assert out == ""
        assert "refus" in err.lower()
        assert _registry_bytes(home=tmp_path) == before


def test_a_revoked_hosts_label_cannot_be_reused_for_another_device(
    *, tmp_path, monkeypatch, capsys
):
    _issue(
        label="laptop", identity="device-a", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    _revoke(label="laptop", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)
    before = _registry_bytes(home=tmp_path)

    code, out, err = _issue(
        label="laptop", identity="device-b", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )

    assert code == 1
    assert out == ""
    assert "refus" in err.lower()
    assert _registry_bytes(home=tmp_path) == before

    code, out, _ = _issue(
        label="desk", identity="device-b", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    assert code == 0
    assert out.strip()


def test_revocation_marks_only_that_host_and_issue_and_revoke_are_audited(
    *, tmp_path, monkeypatch, capsys
):
    credentials = []
    for label, identity in (("a", "device-a"), ("b", "device-b"), ("c", "device-c")):
        _, out, _ = _issue(
            label=label, identity=identity, home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
        )
        credentials.append(out.strip())
    code, _, _ = _revoke(label="b", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0

    assert [(entry["label"], entry["revoked"]) for entry in _entries(home=tmp_path)] == [
        ("a", False),
        ("b", True),
        ("c", False),
    ]

    records = _audit_records(home=tmp_path)
    assert [(record["event"], record["host_label"]) for record in records] == [
        ("enrolment-issued", "a"),
        ("enrolment-issued", "b"),
        ("enrolment-issued", "c"),
        ("enrolment-revoked", "b"),
    ]
    for record in records:
        assert set(record) == {"event", "host_label", "time"}
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["time"])

    audit_text = (tmp_path / _AUDIT).read_text(encoding="utf-8")
    for credential in credentials:
        assert credential not in audit_text
        assert _digest(credential=credential) not in audit_text

    _revoke(label="ghost", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)
    _issue(label="a", identity="device-z", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)
    assert _audit_records(home=tmp_path) == records


def test_list_shows_labels_identities_issue_times_and_revocation_and_nothing_secret(
    *, tmp_path, monkeypatch, capsys
):
    credentials = []
    for label, identity in (("a", "device-a"), ("b", "device-b")):
        _, out, _ = _issue(
            label=label, identity=identity, home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
        )
        credentials.append(out.strip())
    _revoke(label="b", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)

    code, out, _ = _run(argv=["list"], home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)

    assert code == 0
    rows = [line.split("\t") for line in out.splitlines()]
    assert [(row[0], row[1], row[3]) for row in rows] == [
        ("a", "device-a", "active"),
        ("b", "device-b", "revoked"),
    ]
    assert [row[2] for row in rows] == [entry["issued_at"] for entry in _entries(home=tmp_path)]
    for credential in credentials:
        assert credential not in out
        assert _digest(credential=credential) not in out


def test_list_of_an_empty_registry_prints_nothing(*, tmp_path, monkeypatch, capsys):
    code, out, _ = _run(argv=["list"], home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)
    assert (code, out) == (0, "")


@pytest.mark.parametrize(("label", "identity"), [("", "device-a"), ("laptop", "  ")])
def test_an_empty_label_or_network_identity_is_refused_and_writes_nothing(
    *, tmp_path, monkeypatch, capsys, label, identity
):
    code, out, err = _issue(
        label=label, identity=identity, home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    assert code == 1
    assert out == ""
    assert "refus" in err.lower()
    assert _registry_bytes(home=tmp_path) is None
    assert _audit_records(home=tmp_path) == []


_CORRUPT_REGISTRIES = [
    "not json",
    '["entries"]',
    '{"entries": 5}',
    '{"entries": ["laptop"]}',
    '{"entries": [{"label": "laptop"}]}',
    json.dumps(
        {
            "entries": [
                {
                    "label": "laptop",
                    "network_identity": "device-a",
                    "credential_digest": "00",
                    "issued_at": "2026-01-01T00:00:00Z",
                    "revoked": "no",
                    "revoked_at": None,
                }
            ]
        }
    ),
]


@pytest.mark.parametrize("text", _CORRUPT_REGISTRIES)
@pytest.mark.parametrize(
    "argv",
    [["issue", "--label", "x", "--network-identity", "y"], ["revoke", "--label", "x"], ["list"]],
)
def test_a_corrupt_registry_is_never_overwritten(*, tmp_path, monkeypatch, capsys, text, argv):
    path = tmp_path / _REGISTRY
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")

    code, out, err = _run(argv=argv, home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)

    assert code == 1
    assert out == ""
    assert "corrupt" in err.lower()
    assert path.read_text(encoding="utf-8") == text
    assert _audit_records(home=tmp_path) == []


def test_issuance_and_revocation_write_the_registry_under_the_registry_lock(
    *, tmp_path, monkeypatch, capsys
):
    probes = []
    real_save = caam_delivery_registry.save_entries

    def probing_save(*, home, entries):
        descriptor = os.open(home / _STATE_DIR / "enrolment-registry.lock", os.O_RDWR)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            probes.append("held")
        else:
            probes.append("free")
        finally:
            os.close(descriptor)
        real_save(home=home, entries=entries)

    monkeypatch.setattr(caam_delivery_registry, "save_entries", probing_save)

    _issue(
        label="laptop", identity="device-a", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )
    _revoke(label="laptop", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys)

    assert probes == ["held", "held"]


def test_the_registry_and_the_audit_log_are_created_owner_only(*, tmp_path, monkeypatch, capsys):
    _issue(
        label="laptop", identity="device-a", home=tmp_path, monkeypatch=monkeypatch, capsys=capsys
    )

    assert stat.S_IMODE((tmp_path / _STATE_DIR).stat().st_mode) == 0o700
    for name in ("enrolment-registry.json", "delivery-audit.log", "enrolment-registry.lock"):
        assert stat.S_IMODE((tmp_path / _STATE_DIR / name).stat().st_mode) == 0o600
