"""Canonical manager configuration, state and local-record paths.

SPECIFICATION/contracts.md resolves `<home>` from the
effective user's OPERATING-SYSTEM ACCOUNT-DATABASE entry, independently of `HOME`,
`XDG_CONFIG_HOME` and `XDG_STATE_HOME`, and fixes the configuration file at
``<home>/.config/livespec-overseer/llm-provider-manager.json`` and `<manager-state>` at
``<home>/.local/state/livespec-overseer/llm-provider-manager/``.

That invoker-independence is the whole point and is easy to lose: every manager process
for one effective user must share ONE operation, worker, lock, lease, assignment,
attention, selection and proof namespace. A consumer that exports a different `HOME` —
which this fleet's sandboxes and credential-role children do on purpose — would otherwise
get a private, silently-empty state directory and re-acquire credentials that already
exist. Reading the account database is what makes the namespace a property of the USER
rather than of the invocation.

The same contract then fixes each remaining local file at a
DETERMINISTIC owner-only path keyed by a digest over length-prefixed identity values.
Those forms are transcribed into one table here so that no call site spells a directory
name or re-derives a digest: a single mis-typed directory would make an existing lease,
assignment or fence invisible, and "absent" is defined to MEAN "that entity does not
exist" — the failure would read as normal empty state rather than as an error.

TWO FAMILIES ARE DELIBERATELY NOT LENGTH-PREFIXED. A run registration hashes the UTF-8
`consumer_run_id` and a worker record hashes the UTF-8 `record_id`, both stated that way
by the contract. They are single-value identities, so there is no concatenation boundary
for an embedded separator to forge, and transcribing them as `LP` would put every existing
record at a path the contract does not name.
"""

from __future__ import annotations

import pwd
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import length_prefixed_digest, sha256_hex
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AUDIT_LOG_NAME",
    "CONFIG_RELATIVE_PATH",
    "LOCAL_PATH_FAMILIES",
    "PROOF_RECORD_NAME",
    "SELECTION_STATE_NAME",
    "STATE_RELATIVE_PATH",
    "LocalPathFamily",
    "account_database_home",
    "config_file",
    "local_record_path",
    "manager_state_dir",
]

CONFIG_RELATIVE_PATH: Final = (".config", "livespec-overseer", "llm-provider-manager.json")
STATE_RELATIVE_PATH: Final = (".local", "state", "livespec-overseer", "llm-provider-manager")

SELECTION_STATE_NAME: Final = "selection-state.json"
PROOF_RECORD_NAME: Final = "coexistence-proof.json"
AUDIT_LOG_NAME: Final = "audit.jsonl"


@dataclass(frozen=True, kw_only=True)
class LocalPathFamily:
    """One deterministic local-record family: its directory and identity digest form."""

    directory: str
    identity_fields: tuple[str, ...]
    uses_length_prefix: bool
    suffix: str


LOCAL_PATH_FAMILIES: Final[dict[str, LocalPathFamily]] = {
    "issuance": LocalPathFamily(
        directory="issuances",
        identity_fields=("target_ref",),
        uses_length_prefix=True,
        suffix=".json",
    ),
    "target-commit": LocalPathFamily(
        directory="target-commits",
        identity_fields=("target_ref",),
        uses_length_prefix=True,
        suffix=".json",
    ),
    "lease": LocalPathFamily(
        directory="leases",
        identity_fields=("provider", "account_id"),
        uses_length_prefix=True,
        suffix=".json",
    ),
    "assignment": LocalPathFamily(
        directory="assignments",
        identity_fields=("consumer_run_id",),
        uses_length_prefix=True,
        suffix=".json",
    ),
    "tombstone": LocalPathFamily(
        directory="tombstones",
        identity_fields=("consumer_run_id",),
        uses_length_prefix=True,
        suffix=".json",
    ),
    "operation": LocalPathFamily(
        directory="operations",
        identity_fields=("command", "idempotency_key"),
        uses_length_prefix=True,
        suffix=".json",
    ),
    "pending-metadata-effect": LocalPathFamily(
        directory="pending-metadata-effects",
        identity_fields=("record_id",),
        uses_length_prefix=True,
        suffix=".json",
    ),
    "run-registration": LocalPathFamily(
        directory="run-registrations",
        identity_fields=("consumer_run_id",),
        uses_length_prefix=False,
        suffix=".json",
    ),
    "worker": LocalPathFamily(
        directory="workers",
        identity_fields=("record_id",),
        uses_length_prefix=False,
        suffix=".json",
    ),
}


def account_database_home(*, uid: int) -> Path | None:
    """The effective user's account-database home, or None when the uid has no entry.

    `HOME` is never consulted. A uid with no account-database entry is an absence this
    manager cannot substitute for: there is no second source for the one namespace every
    manager process must share.
    """
    try:
        entry = pwd.getpwuid(uid)
    except KeyError:
        return None
    return Path(entry.pw_dir)


def config_file(*, home: Path) -> Path:
    """The one configuration path; an absent file means the default object."""
    return home.joinpath(*CONFIG_RELATIVE_PATH)


def manager_state_dir(*, home: Path) -> Path:
    """`<manager-state>` — the one mode-`0700` local state directory for this user."""
    return home.joinpath(*STATE_RELATIVE_PATH)


def local_record_path(
    *, state_dir: Path, family: str, identity: Sequence[str]
) -> Result[Path, ManagerError]:
    """The deterministic path for one local record of `family`.

    An unregistered family or a wrong identity arity is a caller BUG rather than an
    operator-correctable request, so it returns `internal-bug`: every call site derives
    both from the closed table above, and a mismatch means the code asked for a record
    shape this operation does not have.
    """
    row = LOCAL_PATH_FAMILIES.get(family)
    if row is None:
        return Failure(internal_bug(message=f"unregistered local-record family: {family}"))
    if len(identity) != len(row.identity_fields):
        return Failure(
            internal_bug(
                message=(
                    f"{family} identity needs {len(row.identity_fields)} value(s): "
                    f"{', '.join(row.identity_fields)}"
                )
            )
        )
    digest = (
        length_prefixed_digest(values=identity)
        if row.uses_length_prefix
        else sha256_hex(data=identity[0].encode("utf-8"))
    )
    return Success(state_dir / row.directory / f"{digest}{row.suffix}")
