"""`audit-append`: the attempt evidence that must land before any credential-store mutation.

SPECIFICATION/contracts.md requires that "a credential-store mutation MUST occur only after its
required audit append succeeds. If the append fails, the credential-store mutation MUST NOT be
attempted", fixes the line at exactly `version`, `record_id`, `effect_id`, `actor`, `operation`
and `attempted_at`, and fixes `operation` as "exactly the attempted effect name
`secret-value-set` or `credential-conditional-set`".

THE ATTESTED EFFECT IS THE NEXT POSITION, NOT A CONSTANT. The contract orders an `audit-append`
immediately before the provisionable-token effect it attests, and an acquire `terminal` phase
appends twice for two different effects. So the attested name is READ from the array rather than
assumed — an append that named the wrong effect would be an append whose idempotency identity no
later retry of the real effect could match, which the append-only log makes permanent.

A COMPLETED NO-OP OF THE PAIRED EFFECT IS A COMPLETED NO-OP HERE. The contract makes both
positions no-ops together for `unknown`, a replaced generation and a terminal lifecycle state,
and the reason is what the log MEANS: entries attest adapter calls that were actually attempted.
An append in front of a transition nobody will attempt would assert an attempt that never
happened, and the log cannot be corrected afterwards.

`attempted_at` IS THE CALLER'S FIRST-ATTEMPT CLOCK SAMPLE, NEVER THE OPERATION'S `accepted_at`.
The contract fixes it as "manager time captured for the first adapter attempt represented by
that audit line", and acceptance is a different instant: every retry reuses `accepted_at`, so a
phase that crashed before this append and resumed later makes its first attempt at the RESUMING
clock. Dating the line at acceptance would assert an adapter call at an instant when none could
have occurred — and the log is append-only, so no later writer can ever correct it.

THE SAMPLE CANNOT DRIFT, WHICH IS WHY TAKING IT FROM THE CALLER IS SAFE. A replay hands in a
newer reading, but the append's idempotency match excludes `attempted_at` exactly so that a
retry which cannot reproduce the original instant still recognizes its own line — so this
executor finds the line its first attempt wrote and leaves that stored time untouched. Only the
pass that actually appends spends its sample.
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_audit import AuditEntry, append_audit_entry
from _lpm_engine_context import EffectContext, required_input
from _lpm_operation_replay import PERFORMED, SATISFIED
from _lpm_paths import AUDIT_LOG_NAME
from _lpm_report_credential import audited_actor, report_transition
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AUDITED_EFFECTS",
    "audit_append",
]

AUDITED_EFFECTS: Final = ("secret-value-set", "credential-conditional-set")


def audit_append(*, context: EffectContext) -> Result[str, ManagerError]:
    """Append this position's attempt evidence, or settle an already-recorded effect."""
    planned = _planned_entry(context=context)
    if isinstance(planned, Failure):
        return Failure(planned.failure())
    entry = planned.unwrap()
    if entry is None:
        return Success(SATISFIED)
    appended = append_audit_entry(
        path=context.engine.state_dir / AUDIT_LOG_NAME,
        entry=entry,
        owner_uid=context.engine.owner_uid,
    )
    if isinstance(appended, Failure):
        return Failure(appended.failure())
    return Success(PERFORMED if appended.unwrap().appended else SATISFIED)


def _planned_entry(*, context: EffectContext) -> Result[AuditEntry | None, ManagerError]:
    """The complete line this position owes, or None for the paired effect's completed no-op.

    Deciding the line is separated from writing it because the decision has FIVE ways to refuse
    while the write has one; keeping them in one function made the two sets of exits read as a
    single flat cascade, and the ordering below is load-bearing rather than incidental.
    """
    attested = _attested_effect(context=context)
    if isinstance(attested, Failure):
        return Failure(attested.failure())
    # Required before the authoritative reads, so a composition that omitted the sample refuses
    # the same way whatever the credential's current state is. A check placed after the no-op
    # decision would report the defect only on the passes that actually append.
    sample = required_input(value=context.inputs.audit, member="audit inputs")
    if isinstance(sample, Failure):
        return Failure(sample.failure())
    actor = audited_actor(context=context)
    if isinstance(actor, Failure):
        return Failure(actor.failure())
    transition = report_transition(context=context)
    if isinstance(transition, Failure):
        return Failure(transition.failure())
    planned = transition.unwrap()
    if planned is None:
        return Success(None)
    return Success(
        AuditEntry(
            record_id=planned.record_id,
            effect_id=context.position.effect_id,
            actor=actor.unwrap(),
            operation=attested.unwrap(),
            attempted_at=sample.unwrap().attempt_now,
        )
    )


def _attested_effect(*, context: EffectContext) -> Result[str, ManagerError]:
    effects = context.operation.ordered_effects
    following = context.position.index + 1
    attested = effects[following] if following < len(effects) else ""
    if attested not in AUDITED_EFFECTS:
        return Failure(
            internal_bug(
                message="an audit-append must sit immediately before the effect it attests"
            )
        )
    return Success(attested)
