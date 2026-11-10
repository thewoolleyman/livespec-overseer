"""Enrolled-host delivery: operator commands for the enrolment registry.

Ratified in SPECIFICATION contracts.md, cited at FILE level deliberately --
heading-level citations in source rot the first time a section is renamed.
The commands run on the role holder and write the registry that the delivery
service reads; they are not served to any enrolment credential.

Issuance shows the generated enrolment credential exactly once, on stdout, and
stores only its SHA-256 digest. The credential is high-entropy random, so an
unsalted one-way digest is enough to authenticate a presented credential while
leaving nothing recoverable in the registry.
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import caam_delivery_registry
import streams
from _foreman_vendor_path import VENDOR_PATHS_INSTALLED

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = ["Refusal", "issue_enrolment", "main", "revoke_enrolment"]


@dataclass(frozen=True, kw_only=True)
class Refusal:
    """An expected refusal, carried on the Result failure track."""

    message: str


def issue_enrolment(
    *,
    home: Path,
    label: str,
    network_identity: str,
    issued_at: str,
    credential: str,
) -> Result[None, Refusal]:
    """Write a new entry unless the registry's label and identity rules forbid it."""
    with caam_delivery_registry.registry_lock(home=home):
        entries = caam_delivery_registry.load_entries(home=home)
        unrevoked = [entry for entry in entries if not entry.revoked]
        if any(entry.label == label for entry in unrevoked):
            return Failure(Refusal(message=f"label {label!r} is held by an unrevoked enrolment"))
        if any(entry.network_identity == network_identity for entry in unrevoked):
            return Failure(
                Refusal(
                    message=(
                        f"network identity {network_identity!r} is held by an unrevoked enrolment"
                    )
                )
            )
        if any(
            entry.label == label and entry.network_identity != network_identity
            for entry in entries
            if entry.revoked
        ):
            return Failure(Refusal(message=f"label {label!r} belongs to another device"))
        issued = caam_delivery_registry.Entry(
            label=label,
            network_identity=network_identity,
            credential_digest=hashlib.sha256(credential.encode("utf-8")).hexdigest(),
            issued_at=issued_at,
            revoked=False,
            revoked_at=None,
        )
        caam_delivery_registry.save_entries(home=home, entries=(*entries, issued))
        caam_delivery_registry.append_audit(
            home=home, event="enrolment-issued", host_label=label, at=issued_at
        )
    return Success(None)


def revoke_enrolment(*, home: Path, label: str, revoked_at: str) -> Result[None, Refusal]:
    """Mark the one unrevoked entry holding `label` revoked, and no other entry."""
    with caam_delivery_registry.registry_lock(home=home):
        entries = caam_delivery_registry.load_entries(home=home)
        if not any(entry.label == label and not entry.revoked for entry in entries):
            return Failure(Refusal(message=f"no unrevoked enrolment is labelled {label!r}"))
        revoked = tuple(
            replace(entry, revoked=True, revoked_at=revoked_at)
            if entry.label == label and not entry.revoked
            else entry
            for entry in entries
        )
        caam_delivery_registry.save_entries(home=home, entries=revoked)
        caam_delivery_registry.append_audit(
            home=home, event="enrolment-revoked", host_label=label, at=revoked_at
        )
    return Success(None)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caam-delivery-enrol",
        description="Issue enrolments for enrolled-host credential delivery.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("issue", help="enrol a host and show its credential once")
    _ = issue.add_argument("--label", required=True)
    _ = issue.add_argument("--network-identity", required=True)
    revoke = commands.add_parser("revoke", help="revoke one host's enrolment")
    _ = revoke.add_argument("--label", required=True)
    return parser


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _refused(*, refusal: Refusal) -> int:
    streams.write_stderr(text=f"caam-delivery-enrol: refused: {refusal.message}\n")
    return 1


def _issue(*, args: argparse.Namespace, home: Path) -> int:
    credential = secrets.token_urlsafe(32)
    result = issue_enrolment(
        home=home,
        label=str(args.label),
        network_identity=str(args.network_identity),
        issued_at=_now(),
        credential=credential,
    )
    if isinstance(result, Failure):
        return _refused(refusal=result.failure())
    streams.write_stdout(text=f"{credential}\n")
    streams.write_stderr(
        text=f"caam-delivery-enrol: enrolled {args.label!r}; the credential is shown once\n"
    )
    return 0


def _revoke(*, args: argparse.Namespace, home: Path) -> int:
    result = revoke_enrolment(home=home, label=str(args.label), revoked_at=_now())
    if isinstance(result, Failure):
        return _refused(refusal=result.failure())
    streams.write_stderr(text=f"caam-delivery-enrol: revoked {args.label!r}\n")
    return 0


def main(*, argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "revoke":
        return _revoke(args=args, home=Path.home())
    return _issue(args=args, home=Path.home())
