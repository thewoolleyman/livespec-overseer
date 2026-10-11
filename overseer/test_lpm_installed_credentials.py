"""Credential-service and isolated-target fixtures for installed LPM subprocesses."""

import datetime
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from overseer.test_lpm_installed_services import MACHINE_ID, OP_STATE, install_services

__all__: list[str] = [
    "SeededCredential",
    "bind_target_lock",
    "install_credential_services",
    "register_target",
    "seed_credential",
    "write_decoy_target",
]

_UID = 1000
_GID = 1000
_STATE = "/home/fixture/.local/state/livespec-overseer/llm-provider-manager"
_METADATA = "llm-provider-manager-token-metadata"
_VALUES = "llm-provider-manager-token-values"


@dataclass(frozen=True, kw_only=True)
class SeededCredential:
    """Identity of one selectable record whose raw value remains in the fake vault."""

    record_id: str
    account_id: str
    value_generation: str


def install_credential_services(*, root: Path) -> None:
    """Install fixed prerequisites without adding any production configuration seam."""
    install_services(root=root)


def seed_credential(*, root: Path, value: bytes) -> SeededCredential:
    """Seed namespace-bound metadata and value items in the isolated `op` process."""
    now = _now()
    credential = SeededCredential(
        record_id=str(uuid.uuid4()),
        account_id="fixture-anthropic-account",
        value_generation=str(uuid.uuid4()),
    )
    reference = f"op://{_VALUES}/{credential.record_id}-{credential.value_generation}/credential"
    record = {
        "version": 1,
        "record_id": credential.record_id,
        "provider": "anthropic",
        "account_id": credential.account_id,
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": now,
        "expires_at": None,
        "last_validated": now,
        "value_generation": credential.value_generation,
        "value_ref": reference,
        "previous_value_ref": None,
    }
    record_text = _canonical(value=record)
    namespace = _namespace()
    effect = hashlib.sha256(record_text.encode()).hexdigest()
    items = [
        _namespace_item(vault=_METADATA, item_id="metadata-namespace", fields=namespace),
        _namespace_item(vault=_VALUES, item_id="values-namespace", fields=namespace),
        {
            "id": "metadata-revision-1",
            "title": f"{credential.record_id}-m{1:020d}-{effect}",
            "vault": _METADATA,
            "fields": {"predecessor_sha256": "0" * 64, "record": record_text},
        },
        {
            "id": "credential-generation-1",
            "title": f"{credential.record_id}-{credential.value_generation}",
            "vault": _VALUES,
            "fields": {"credential": value.decode("utf-8")},
        },
    ]
    _write_owned(
        path=root / OP_STATE.lstrip("/"),
        data=json.dumps({"items": items, "calls": [], "refuse": [], "garble": []}),
    )
    return credential


def register_target(*, root: Path, consumer_run_id: str) -> Path:
    """Write the operator-owned handoff at its deterministic manager-state path."""
    state = root / _STATE.lstrip("/")
    _owned_directory(path=state / "run-registrations")
    isolated = root / "isolated" / "registered"
    _owned_directory(path=isolated)
    destination = isolated / "credential"
    created = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)
    registration = {
        "version": 1,
        "consumer_run_id": consumer_run_id,
        "isolated_root": "/isolated/registered",
        "target_path": "/isolated/registered/credential",
        "created_at": _timestamp(moment=created),
        "expires_at": _timestamp(moment=created + datetime.timedelta(hours=1)),
    }
    digest = hashlib.sha256(consumer_run_id.encode()).hexdigest()
    _write_owned(
        path=state / "run-registrations" / f"{digest}.json",
        data=_canonical(value=registration),
    )
    return destination


def write_decoy_target(*, root: Path, value: bytes) -> Path:
    """Create a second writable destination outside the registered isolated root."""
    decoy = root / "isolated" / "decoy"
    _owned_directory(path=decoy)
    target = decoy / "credential"
    target.write_bytes(value)
    os.chown(target, _UID, _GID)
    target.chmod(0o600)
    return target


def bind_target_lock(*, root: Path, target_ref: str) -> None:
    """Make inherited lock descriptors resolve to the lock's chroot-absolute path."""
    encoded = len(target_ref.encode()).to_bytes(8, "big") + target_ref.encode()
    digest = hashlib.sha256(encoded).hexdigest()
    expected = f"{_STATE}/locks/target/{digest}.lock"
    descriptor_dir = root / "proc" / "self" / "fd"
    for descriptor in range(3, 256):
        (descriptor_dir / str(descriptor)).symlink_to(expected)


def _namespace() -> dict[str, str]:
    digest = hashlib.sha256(MACHINE_ID.encode("ascii")).hexdigest()
    return {
        "version": "1",
        "machine_id_sha256": digest,
        "effective_uid": str(_UID),
        "manager_state": _STATE,
    }


def _namespace_item(*, vault: str, item_id: str, fields: dict[str, str]) -> dict[str, object]:
    return {
        "id": item_id,
        "title": "llm-provider-manager-namespace",
        "vault": vault,
        "fields": fields,
    }


def _owned_directory(*, path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    boundary = path.parents[4]
    for directory in (path, *path.parents):
        if directory == boundary:
            break
        os.chown(directory, _UID, _GID)
        directory.chmod(0o700)


def _write_owned(*, path: Path, data: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    os.chown(path, _UID, _GID)
    path.chmod(0o600)


def _canonical(*, value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _now() -> str:
    return _timestamp(moment=datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0))


def _timestamp(*, moment: datetime.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
