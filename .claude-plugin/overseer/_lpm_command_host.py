"""What every manager command needs from the world, and how each one answers.

SPECIFICATION/contracts.md requires each manager invocation to "write exactly one single-line
UTF-8 JSON object to standard output" and maps each error type onto one exit status. This
module owns that encoding, the one input seam (`<path|->`), and the small bundle of host facts
the three consumer commands are built over.

THE HOST IS A PARAMETER, NOT AN AMBIENT. Every fact a command needs -- the state directory,
the validated configuration, the manager's current time, the credential records, the
privileged writers -- arrives on one frozen record, so a command is a pure function of its
request and its host. That is what lets the whole consumer surface be exercised with no
SecretStore, no credential, no `op` executable and no clock. It is also why the invocation
surface stays knob-free: these are constructor seams, never flags.

TWO PORTS ARE DELIBERATELY NARROW, AND THE NARROWNESS IS THE POINT.

* `CredentialRecords` reads metadata. It hands back records that carry a `value_ref`, never a
  credential VALUE, so a command module cannot read a secret even by accident.
* `CredentialStatusWriter` performs the one metadata WRITE a report can require. The contract
  routes that write through the lifecycle-writer role, whose service-account token comes only
  from the kernel user keyring, so the real composition lives in `_lpm_manager_host` behind the
  ratified prerequisite closure rather than here. Dropping a required transition and reporting
  success is the one thing it must never do: that would leave a credential the provider has just
  rejected sitting at `valid` for the next consumer to select.

`read_command_object` TREATS `-` AS STANDARD INPUT, which the contract requires, and refuses
with the CALLER'S error type rather than a fixed one: the same unreadable-input failure is
`invalid-report` for a recognized `report` and `invalid-request` everywhere else, so the type
is a parameter. It rejects duplicate member names by parsing through
`parse_canonical_json`, and rejects trailing non-whitespace because `json` does.

NO INPUT VALUE REACHES A MESSAGE. A command's input is caller-controlled and may contain
anything, including the credential the caller should never have put there, so every refusal
below names the defect rather than quoting what carried it.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import length_prefixed_digest, parse_canonical_json
from _lpm_config import ManagerConfig
from _lpm_eligibility import AccountObservation, EligibilityPolicy
from _lpm_leases import lease_is_live, read_lease
from _lpm_localstate import ensure_state_directory
from _lpm_locks import HeldLock, take_lock
from _lpm_paths import LOCAL_PATH_FAMILIES, SELECTION_STATE_NAME, local_record_path
from _lpm_provision import CredentialValueReader
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, error_object, exit_status_for

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "LOCK_DIRECTORY",
    "MANAGER_STATE_DIRECTORIES",
    "RESULT_VERSION",
    "RUN_LOCK_FAMILY",
    "SUCCESS_STATUS",
    "TARGET_DIRECTORY",
    "TARGET_FILE_NAME",
    "CommandOutcome",
    "CredentialRecords",
    "CredentialStatusWriter",
    "LeaseSurvey",
    "ManagerHost",
    "eligibility_policy",
    "error_outcome",
    "establish_manager_state",
    "lease_survey",
    "manager_lock_path",
    "read_command_object",
    "run_serialization",
    "selection_state_path",
    "success_outcome",
    "target_destination",
]

RESULT_VERSION: Final = 1
SUCCESS_STATUS: Final = "ok"
LOCK_DIRECTORY: Final = "locks"
RUN_LOCK_FAMILY: Final = "run"
TARGET_DIRECTORY: Final = "targets"
TARGET_FILE_NAME: Final = "credential"

_STANDARD_INPUT: Final = "-"

# Every directory the manager writes directly beneath `<manager-state>`. The local-record
# families supply their own names, and the three that are not record families are named here.
MANAGER_STATE_DIRECTORIES: Final = (
    *sorted(row.directory for row in LOCAL_PATH_FAMILIES.values()),
    LOCK_DIRECTORY,
    TARGET_DIRECTORY,
)


class CredentialRecords(Protocol):
    """The injected port that reads every credential record this manager knows about."""

    def __call__(self) -> Result[tuple[CredentialRecord, ...], ManagerError]:
        """Every stored credential record, or a typed failure. Never a credential VALUE."""
        ...


class CredentialStatusWriter(Protocol):
    """The injected port that moves one credential record to a new lifecycle status."""

    def __call__(
        self, *, record: CredentialRecord, next_status: str, now: str
    ) -> Result[None, ManagerError]:
        """Persist the transition, or report why it could not be persisted."""
        ...


@dataclass(frozen=True, kw_only=True)
class CommandOutcome:
    """One manager invocation's single JSON line and the exit status that goes with it."""

    stdout: str
    exit_status: int


@dataclass(frozen=True, kw_only=True)
class LeaseSurvey:
    """One pass over the lease records: the eligibility observations, and each account's path."""

    observations: Mapping[str, AccountObservation]
    paths: Mapping[str, Path]


@dataclass(frozen=True, kw_only=True)
class ManagerHost:
    """Every fact and port the consumer commands are built over, in one injectable record."""

    state_dir: Path
    config: ManagerConfig
    owner_uid: int
    now: str
    read_input: Callable[[], str]
    records: CredentialRecords
    read_value: CredentialValueReader
    write_status: CredentialStatusWriter
    new_reference: Callable[[], str]
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]


def establish_manager_state(*, state_dir: Path, owner_uid: int) -> Result[None, ManagerError]:
    """Create or validate `<manager-state>` and each directory beneath it at mode `0700`.

    `ensure_state_directory` modes only the LEAF it is given, and `Path.mkdir(parents=True)`
    leaves every INTERMEDIATE directory at the process umask -- so a first write of
    `<manager-state>/targets/<digest>/credential` would mode the digest directory `0700` and
    leave `<manager-state>` and `<manager-state>/targets` world-readable. The contract requires
    the provisioned destination to "sit beneath registered parent directories no broader than
    `0700`", and a 0755 directory on that path breaks it however tight the file itself is. So
    every directory the manager writes under is established explicitly, before the first write.

    It is called after a command has validated its request, never before: a refused request must
    change nothing, and creating this tree is a change.
    """
    for directory in (state_dir, *(state_dir / name for name in MANAGER_STATE_DIRECTORIES)):
        ensured = ensure_state_directory(path=directory, owner_uid=owner_uid)
        if isinstance(ensured, Failure):
            return Failure(ensured.failure())
    return Success(None)


def run_serialization(*, host: ManagerHost, consumer_run_id: str) -> Result[HeldLock, ManagerError]:
    """Take the per-run lock every `consumer_run_id`-carrying command must hold.

    SPECIFICATION/contracts.md: "a command carrying `consumer_run_id` MUST first take per-run
    serialization and finish any pending ... operation". It is what makes the write-ahead records
    below meaningful -- two concurrent invocations of the same run would otherwise read the same
    pending operation and each resume it, applying every remaining effect twice. The bound is
    `external_call_timeout_seconds`, and a contended lock is `store-unavailable` "without
    substantive mutation", which is why it is taken before anything is written.
    """
    established = establish_manager_state(state_dir=host.state_dir, owner_uid=host.owner_uid)
    if isinstance(established, Failure):
        return Failure(established.failure())
    return take_lock(
        path=manager_lock_path(
            state_dir=host.state_dir, family=RUN_LOCK_FAMILY, identity=[consumer_run_id]
        ),
        owner_uid=host.owner_uid,
        timeout_seconds=float(host.config.external_call_timeout_seconds),
        monotonic=host.monotonic,
        sleep=host.sleep,
    )


def success_outcome(*, payload: dict[str, object]) -> CommandOutcome:
    """The one success line: the ratified envelope plus this operation's own members."""
    body: dict[str, object] = {"version": RESULT_VERSION, "status": SUCCESS_STATUS}
    body.update(payload)
    return CommandOutcome(stdout=json.dumps(body, separators=(",", ":")), exit_status=0)


def error_outcome(*, error: ManagerError) -> CommandOutcome:
    """The one failure line, with the contract's exit status for its error type."""
    return CommandOutcome(
        stdout=json.dumps(error_object(error=error), separators=(",", ":")),
        exit_status=exit_status_for(error_type=error.error_type),
    )


def read_command_object(
    *,
    source: str,
    read_input: Callable[[], str],
    refuse: Callable[..., ManagerError],
) -> Result[object, ManagerError]:
    """Read exactly one UTF-8 JSON object from `<path|->`, refused with the caller's type."""
    if source == _STANDARD_INPUT:
        text = read_input()
    else:
        try:
            text = Path(source).read_text(encoding="utf-8")
        except (OSError, ValueError):
            # The path and the decoding error are both caller-controlled, so neither the
            # operating-system message nor the offending bytes may be quoted back out.
            return Failure(refuse(message="the command input could not be read as UTF-8"))
    parsed = parse_canonical_json(text=text)
    if isinstance(parsed, Failure):
        return Failure(refuse(message="the command input is not exactly one JSON object"))
    return Success(parsed.unwrap())


def selection_state_path(*, state_dir: Path) -> Path:
    """`<manager-state>/selection-state.json` — the one durable selection record."""
    return state_dir / SELECTION_STATE_NAME


def manager_lock_path(*, state_dir: Path, family: str, identity: Sequence[str]) -> Path:
    """`<manager-state>/locks/<family>/<digest>.lock` for one of the contract's lock families.

    Lock paths are deliberately NOT part of `_lpm_paths`'s local-record table: a lock file
    "MUST contain no authoritative state", so it is not a record, and keeping it out of that
    table is what stops a reader from mistaking one for one.
    """
    return state_dir / LOCK_DIRECTORY / family / f"{length_prefixed_digest(values=identity)}.lock"


def target_destination(*, state_dir: Path, reference: str) -> Path:
    """The isolated-run destination one issued reference resolves to.

    It sits beneath the manager's own owner-only state rather than anywhere the consumer
    names, which is how the adapter's "writable only within that run's isolated execution
    target" requirement is met structurally: the consumer supplies a run identity, never a
    path, and the digest of the reference is the only thing that selects the directory.
    """
    digest = length_prefixed_digest(values=[reference])
    return state_dir / TARGET_DIRECTORY / digest / TARGET_FILE_NAME


def eligibility_policy(*, config: ManagerConfig, now: str) -> EligibilityPolicy:
    """The selection policy this invocation runs under, read entirely from configuration."""
    return EligibilityPolicy(
        now=now,
        maximum_validation_age_seconds=config.maximum_validation_age_seconds,
        health_strategy=config.health_strategy,
        health_floor_percent=config.health_floor_percent,
        account_reservations=config.account_reservations,
    )


def lease_survey(
    *,
    state_dir: Path,
    records: Sequence[CredentialRecord],
    owner_uid: int,
    now: str,
    consumer_run_id: str,
) -> Result[LeaseSurvey, ManagerError]:
    """One pass over the lease records: who is leased, and where each account's lease lives.

    THE PATHS ARE RETURNED RATHER THAN RE-DERIVED, and that is the point of surveying rather
    than just observing. `provision` needs the selected account's lease path, and deriving it a
    second time would be a second chance to fail on a question this pass has already answered
    for every account in `records` -- an error rail that nothing could ever reach, since the
    selected record is by construction one of the records surveyed here.

    This run's OWN live lease is deliberately not an exclusion. An identical provision retry
    must be able to reach the account it already holds -- `acquire_lease` is what decides
    whether the claim is this run's -- and excluding it here would turn a safe replay into
    `retryable-exhaustion`.
    """
    observations: dict[str, AccountObservation] = {}
    paths: dict[str, Path] = {}
    for record in records:
        if record.account_id in observations:
            continue
        path = local_record_path(
            state_dir=state_dir, family="lease", identity=[record.provider, record.account_id]
        )
        if isinstance(path, Failure):
            return Failure(path.failure())
        lease = read_lease(path=path.unwrap(), owner_uid=owner_uid)
        if isinstance(lease, Failure):
            return Failure(lease.failure())
        held = lease.unwrap()
        leased = (
            held is not None
            and held.consumer_run_id != consumer_run_id
            and lease_is_live(lease=held, now=now)
        )
        observations[record.account_id] = AccountObservation(leased=leased)
        paths[record.account_id] = path.unwrap()
    return Success(LeaseSurvey(observations=observations, paths=paths))
