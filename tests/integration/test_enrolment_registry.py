"""Integration-tier enrolment registry: issuance, revocation and the audit log.

Drives the `caam-delivery-enrol` operator command in-process against a scratch
`HOME`, so the registry and the audit log land in a throwaway host state
directory. Every assertion reads the files the command wrote, never a value the
command returned.

The credential strings the command generates are random per call and are never
taken from a real credential, so nothing here is a credential fixture.
"""

import hashlib
import json
from pathlib import Path

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
