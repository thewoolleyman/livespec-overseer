"""Secret-free factory-selection record application on an enrolled host.

The role holder supplies the exact bytes of its published record.  This module
does not read credentials or delivery-sequence state: the factory record is a
separate, identity-only replication channel.
"""

from __future__ import annotations

import base64
from pathlib import Path

__all__: list[str] = ["FACTORY_SELECTION_REL", "apply_program"]

FACTORY_SELECTION_REL = Path(".local/state/caam-usage-rotate/factory-selected-account.json")


def apply_program(*, record_bytes: bytes) -> str:
    """Return a remote program that atomically advances a factory-selection record.

    The encoded bytes are written unchanged after shape validation, making the
    receiving host's record byte-for-byte equal to the role holder's record.
    """
    encoded = base64.b64encode(record_bytes).decode("ascii")
    return f"""import base64
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

PAYLOAD = base64.b64decode({encoded!r})
TARGET = Path.home() / {str(FACTORY_SELECTION_REL)!r}

def parsed_record(raw):
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != {{
        "account_uuid", "profile", "reason", "written_at"
    }}:
        return None
    profile, account = value["profile"], value["account_uuid"]
    reason, written = value["reason"], value["written_at"]
    named = (
        isinstance(profile, str) and profile != "" and isinstance(account, str) and account != ""
    )
    unnamed = profile is None and account is None and isinstance(reason, str) and reason != ""
    if not (named or unnamed) or not isinstance(written, str) or (named and reason is not None):
        return None
    try:
        return value, datetime.fromisoformat(written.replace("Z", "+00:00"))
    except ValueError:
        return None

candidate = parsed_record(PAYLOAD)
if candidate is None:
    print("factory-selection failed invalid-record")
    raise SystemExit(2)
TARGET.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if TARGET.exists():
    try:
        existing = parsed_record(TARGET.read_bytes())
    except OSError:
        existing = None
    if existing is None:
        print("factory-selection failed invalid-existing-record")
        raise SystemExit(2)
    if candidate[1] <= existing[1]:
        print("factory-selection not-newer")
        raise SystemExit(0)
descriptor, temporary = tempfile.mkstemp(prefix=TARGET.name + ".", dir=TARGET.parent)
try:
    os.chmod(temporary, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(PAYLOAD)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, TARGET)
except OSError:
    try:
        os.unlink(temporary)
    except OSError:
        pass
    raise
print("factory-selection applied")
"""
