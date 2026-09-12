# Context compaction restart latch — initial scope and code seams

Measured failure
----------------

The intake record overseer-nb7ok7 captures a live failure observed on
2026-09-11: a supervised session can remain busy while its remaining context
crosses the wind-down line, compact in place, and reappear above the line under
the same live session identity. The daemon currently reads the replenished
percentage as recovery and can close the starvation episode without opening a
restart round.

Maintainer ruling
-----------------

An in-place compaction is an exhausted context generation, not a healthy
continuation. Once detected, it creates a durable restart-required obligation
for either runtime. That obligation survives daemon restart and later
above-threshold readings until the ordinary cooperative protocol obtains a new
winding-down acknowledgement, a certifiable ready, and successful adoption of
a fresh successor session.

The cardinal safety rule remains unchanged: this latch never authorizes killing
a busy or undeclared session. It changes why the existing wind-down and restart
protocol remains owed; it does not bypass that protocol.

Implementation seams to verify
------------------------------

Tree enumeration points first at the runtime-neutral context observation and
decision seams in overseer/_supervisor_ctx_reading.py,
overseer/_supervisor_evaluate*.py, overseer/_supervisor_threshold.py, and the
durable per-track state in overseer/_supervisor_records.py. Restart-round
lifecycle, fresh-successor discrimination, persistence, and operator evidence
span the existing restart/lifecycle/snapshot modules and must be followed from
the tree rather than inferred from an inventory list.

Before product edits, the implementer must read the three authoritative module
documents: overseer/marker-protocol.md, overseer/SKILL.md, and
overseer/AGENTS.md. Beside-tests must cover both Codex and Claude, plus the
new-successor control and zero-respawn safety cases. Snapshot and event-history
output must make the same-session transition and latched obligation observable.

Scope boundary
--------------

This plan has one repository implementation child: overseer-nb7ok7. Product
code, beside-tests, package documentation, and required plugin mirrors are in
scope. SPECIFICATION/ edits and bouncing or validating the acting host daemon
are explicitly outside this child; contract ratification and live adoption are
separate obligations if later requested. The unrelated
plan/llm-provider-manager/ thread supplied the live observation but does not
own this supervision repair.
