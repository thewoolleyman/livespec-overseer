"""Gate every charter IN THIS REPO against the fourteen known defect classes.

The nine groom slices fix the GENERATOR, so the NEXT charter is correct. None of
them remediates the charters already emitted, and nothing schedules regeneration
— a thread that never re-runs `supervise-plan` keeps its defect indefinitely.
Measured 2026-07-29 across the fleet: 130 bare targets in 18 files across 6
repos, with six threads ARMED (both sessions alive, so the defect is dormant and
fires the moment the worker exits). `plan/archive/ship-overseer-to-fleet/` is the
instructive case — its charter is ARCHIVED and both its sessions still run, so
archiving a thread does NOT disarm it.

This module is the repo-local half of that: it stops the population growing here.
It is a pytest module rather than a new `just check-<slug>` deliberately —
`check-aggregate-completeness` means wiring one canonical slug forces wiring
every other, and `tests/prompts/` is already an enforced surface.

THE DETECTORS READ FENCED CODE ONLY. The prototype this replaces scanned whole
files and counted PROSE mentions of a hazard as instances of it: the hand-
hardened exemplar scored 3 on (b) with zero defective code, because the section
intro says "readlink -f first" and Correction C2 quotes `readlink -f ""` while
EXPLAINING the bug. A detector that fires on the documentation of a fix makes
hardening a charter raise its score, which is unusable as a gate. Hence
`test_the_hardened_exemplar_is_clean` below: the exemplar is a POSITIVE CONTROL,
and any hit on it is a defect in this module, not in the charter.

WHY CLASS (e) EXISTS, AND WHY IT IS URGENT RATHER THAN TIDY. Fixing the
generator in this repo does NOT fix the generator that RUNS. Measured
2026-07-29 across all nine cached plugin versions under
`~/.claude/plugins/cache/livespec-overseer/`: ZERO contain the exact-target
mandate and ZERO contain the supervisor liveness proof. A charter generated on
this host 17h after the exact-target fix merged still carried 12 bare targets —
it came from the stale cache, and this gate is what turned master red on it.
So until a release is cut, every newly generated charter arrives defective and
hand-hardening the deployed ones is the only thing that helps. Gating the
RUNNING generator is a release-lane question and is deliberately not attempted
here.
"""

from __future__ import annotations

from pathlib import Path

from livespec_dev_tooling.charters import CHARTER_GLOBS, DETECTORS, defects_in
from livespec_dev_tooling.charters.charters import charters_in

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CHARTER_GLOBS = CHARTER_GLOBS
_DETECTORS = DETECTORS

# The charter that was hardened by hand and is what the generator must be able to
# produce. Accept either location: a plan moves into `plan/archive/` when
# it closes, and an unguarded read of the live path alone already made archiving
# a thread a CI-reddening act once.
_EXEMPLAR_CANDIDATES = (
    _REPO_ROOT / "plan" / "supervisor-prompt-quality" / "supervisor-handoff.md",
    _REPO_ROOT / "plan" / "archive" / "supervisor-prompt-quality" / "supervisor-handoff.md",
)


def _charters() -> list[Path]:
    return charters_in(root=_REPO_ROOT)


def test_the_shipped_detector_table_is_loaded():
    """A detector-less shipped table would make this gate vacuous."""
    assert len(DETECTORS) == 14


def test_this_repo_has_charters_to_scan():
    """A gate over an empty file set passes vacuously and proves nothing.

    Sabotage that reddens this: point `CHARTER_GLOBS` at a path that matches
    nothing. Without this assertion that sabotage would look like a clean repo.
    """
    assert _charters() != []


def test_every_charter_in_this_repo_is_free_of_the_known_defects():
    """THE GATE. A charter carrying any registered class fails here, in this repo's CI.

    The name carries NO COUNT on purpose. It said "four" while there were seven,
    because a count in a name goes stale the moment a detector is added and
    nothing forces it to be updated — the same drift class this module gates.

    Sabotage that reddens this: restore a bare `-t <session>` target in any
    charter under `plan/`.
    """
    offences = {
        str(path.relative_to(_REPO_ROOT)): defects_in(text=path.read_text(encoding="utf-8"))
        for path in _charters()
    }
    assert {path: found for path, found in offences.items() if found} == {}


def test_the_globs_reach_every_charter_shaped_file_in_the_repo():
    """A NARROWED glob silently reduces coverage, and non-empty does not catch it.

    `test_this_repo_has_charters_to_scan` asserts only that the set is non-empty,
    so it still passes with ONE charter of eight. That is the weaker half of the
    guard: it catches a glob that matches nothing, never a glob that quietly
    stopped matching most things. This module's own docstring records why that
    gap matters -- the two-layer split moved half of every deployed charter into
    `.ai/supervisor-protocol.md`, the glob was not widened to follow it, and the
    gate went on reporting a clean repo while the larger half went unexamined.
    **A gate's SCOPE is as load-bearing as its detectors**, so the scope gets a
    rule rather than a floor.

    KEYED ON A PROPERTY, NOT A COUNT, deliberately: asserting "eight charters"
    would drift the moment this repo grows a plan, and the reflex would be
    to edit the number. The rule is that every charter-shaped file ON DISK is in
    the scanned set, so it self-adjusts as threads come and go while still
    failing if the globs stop reaching one.

    SCOPE, stated rather than hidden. It looks under `plan/**` at ANY depth plus
    the shared layer -- the SAME recursive shape `CHARTER_GLOBS` now uses, after
    a fourth instance of this drift (2026-08-16, a `plan/<topic>/research/`
    charter one level deeper than either of the two fixed-depth patterns that
    preceded it) collapsed those two patterns into one recursive glob. The two
    are computed independently ON PURPOSE — this test's own `on_disk` scan is not
    derived from `CHARTER_GLOBS` — so a FUTURE narrowing of `CHARTER_GLOBS` back
    to a fixed depth still reddens here even though today the two constructions
    happen to agree. It does NOT look outside `plan/`, which correctly ignores
    the gitignored working copy at `tmp/<topic>-supervisor/supervisor-handoff.md`
    (measured: that is the only charter-shaped file outside the globs, and it is
    untracked scratch).

    Sabotage that reddens this: narrow `plan/**/supervisor-handoff.md` in
    `CHARTER_GLOBS` back to a fixed-depth pattern such as
    `plan/*/supervisor-handoff.md`, which drops any charter nested one level
    deeper while leaving the set non-empty.
    """
    scanned = {path.resolve() for path in _charters()}
    # Both halves are GLOBS, not a path plus an `is_file()` test. A conditional
    # here carries a branch that can never be taken while the shared layer
    # exists, so it can never be covered; a glob over an absent file simply
    # yields nothing and needs no branch.
    on_disk = {path.resolve() for path in _REPO_ROOT.glob("plan/**/supervisor-handoff.md")}
    on_disk |= {path.resolve() for path in _REPO_ROOT.glob(".ai/supervisor-protocol.md")}

    unscanned = sorted(str(path.relative_to(_REPO_ROOT)) for path in on_disk - scanned)
    assert unscanned == [], (
        f"charter-shaped files exist that no glob reaches: {unscanned}. "
        "Widen CHARTER_GLOBS rather than deleting this assertion -- an "
        "unscanned charter is indistinguishable from a clean one."
    )


def test_the_disk_scan_this_rule_depends_on_actually_finds_charters():
    """POSITIVE CONTROL. If the disk scan found nothing the rule above is vacuous.

    Its assertion is a SUBSET check, so an empty `on_disk` satisfies it trivially
    and every narrowing would pass. That is the same vacuous shape the rule was
    written to close, one level up.

    Sabotage that reddens this: point the glob at a directory that does not exist.
    """
    assert len(list(_REPO_ROOT.glob("plan/**/supervisor-handoff.md"))) > 1


def test_the_hardened_exemplar_is_clean():
    """POSITIVE CONTROL: a hit here is a defect in the DETECTORS, not the charter.

    The exemplar was hardened by hand and is what the generator must be able to
    produce. It performs a bounded `capture-pane -S -40` inspection and it quotes
    `readlink -f ""` in a Correction while explaining that bug — both correct.
    A detector that flags either would make hardening a charter raise its score.
    """
    exemplar = next((path for path in _EXEMPLAR_CANDIDATES if path.is_file()), None)
    assert exemplar is not None, (
        "the exemplar charter is at neither its live nor its archived location — "
        + ", ".join(str(path) for path in _EXEMPLAR_CANDIDATES)
        + ". Add its new location to _EXEMPLAR_CANDIDATES rather than deleting "
        "this assertion."
    )
    assert defects_in(text=exemplar.read_text(encoding="utf-8")) == []


def test_prose_describing_a_hazard_is_not_counted_as_the_hazard():
    """The exact failure that made the prototype unusable as a gate.

    Every line below is prose ABOUT a defect, outside any fenced block. A
    whole-file scanner counts all four; this one must count none.
    """
    charter = """
Verify the worker with `tmux has-session -t supervisor-prompt-quality` — no,
that prefix-matches. Resolve with `readlink -f "$pane_cwd"` only AFTER guarding.
Correction C2: `readlink -f ""` returns the CWD with exit 0.
The watcher used to seed prev="" and read a dead session as idle.
It also piped `tmux capture-pane -p -S -40 | grep -qE 'Enter to select'`.
"""
    assert defects_in(text=charter) == []


def test_a_commented_out_defect_is_not_counted():
    """A hazard shown inside a code block as a `#` comment is documentation too.

    Sabotage that reddens this: drop the `_is_comment` guard from the detectors.
    """
    charter = """
```sh
# tmux send-keys -t my-session -- 'do not do this'
# readlink -f "$pane_cwd"
# prev=""
# pane=$(tmux capture-pane -p -t my-session -S -40)
```
"""
    assert defects_in(text=charter) == []


def test_an_incomplete_adoptable_runtime_contract_is_flagged():
    """RED control: a runtime section that drops a leg is not enforceable."""
    charter = """
## Adoptable runtime launch and restart

Claude fresh launch: `claude --dangerously-skip-permissions`.
Claude live repair: `/rename <topic>`.
"""
    assert [d for d in defects_in(text=charter) if d.startswith("m-")] != []


def test_an_unattended_charter_missing_the_unblock_clause_is_flagged():
    """RED control: an unattended charter cannot offer a picker with no unblock rule."""
    charter = """
# Supervisor Protocol

Shared role-level instructions for every generated supervisor handoff.

## AskUserQuestion presentation rules

Every maintainer-facing action is an AskUserQuestion call. Put --- as the final
line before the picker.
"""
    assert defects_in(text=charter) == [
        "n-unattended-charter-missing-perform-the-unblock: "
        "unattended charter presents a picker without perform-the-unblock authority"
    ]


def test_an_unattended_charter_with_the_unblock_clause_is_not_flagged():
    """DISCRIMINATION for (n): the detector accepts the shipped authorization."""
    charter = """
# Supervisor Protocol

Shared role-level instructions for every generated supervisor handoff.

## AskUserQuestion presentation rules

Every maintainer-facing action is an AskUserQuestion call. Put --- as the final
line before the picker.

If the SUPERVISOR can perform the unblock, PERFORM IT.
"""
    assert [d for d in defects_in(text=charter) if d.startswith("n-")] == []


def test_an_interactive_charter_with_a_picker_and_no_unblock_clause_is_not_flagged():
    """DISCRIMINATION for (n): interactive plan-track picker rules are allowed."""
    charter = """
# Interactive Plan Track

## AskUserQuestion presentation rules

Every maintainer-facing action is an AskUserQuestion call. Put --- as the final
line before the picker.
"""
    assert [d for d in defects_in(text=charter) if d.startswith("n-")] == []


def test_the_adoptable_runtime_contract_accepts_reformatted_correct_content():
    """The detector checks the contract, not one markdown line wrapping."""
    charter = """
## Adoptable runtime launch and restart

Claude fresh launch:
`claude --dangerously-skip-permissions
-n <topic>`.
Claude live repair: `/rename <topic>` only after confirming
`signals.is_structured_gate` is false.
Codex restart:
`codex resume --dangerously-bypass-approvals-and-sandbox <session-id>
"<kick>"`, recovered from `~/.codex/session_index.jsonl` by `thread_name`.
Codex fresh launch immediately uses `/rename <topic>`.
Never send `/rename` into a numbered cursor or a permission question.
A tmux session name is not an adoption key. Keep the daemon's own launch paths
unchanged; do not use fuzzy matching, tmux-name matching, live killing, or
blocking.
"""
    assert [d for d in defects_in(text=charter) if d.startswith("m-")] == []


def test_a_topic_named_agent_in_a_differently_named_tmux_session_is_accepted():
    """The adoption key is the runtime identity, not the tmux window name."""
    charter = """
## Adoptable runtime launch and restart

Claude fresh launch: `claude --dangerously-skip-permissions -n <topic>`.
Claude live repair: `/rename <topic>` after checking
`signals.is_structured_gate` is false.
Codex restart: `codex resume
--dangerously-bypass-approvals-and-sandbox <session-id> "<kick>"` by the
`thread_name` in `~/.codex/session_index.jsonl`.
Codex fresh launch immediately uses `/rename <topic>`.
Never send `/rename` into a numbered cursor or a permission question.
The topic-named agent runs in tmux session `operator-window`, which is not the
topic name. A tmux session name is not an adoption key. The daemon's own launch
paths are unchanged; no fuzzy matching, tmux-name matching, live killing, or
blocking.
"""
    assert [d for d in defects_in(text=charter) if d.startswith("m-")] == []


def test_the_adoptable_runtime_contract_requires_structured_gate_safety():
    """A live `/rename` instruction must preserve the picker/permission guard."""
    charter = """
## Adoptable runtime launch and restart

Claude fresh launch: `claude --dangerously-skip-permissions -n <topic>`.
Claude live repair: `/rename <topic>` only after confirming
`signals.is_structured_gate` is false.
Codex restart: `codex resume
--dangerously-bypass-approvals-and-sandbox <session-id> "<kick>"` by the
`thread_name` in `~/.codex/session_index.jsonl`.
Codex fresh launch immediately uses `/rename <topic>`.
A tmux session name is not an adoption key. The daemon's own launch paths are
unchanged; no fuzzy matching, tmux-name matching, live killing, or blocking.
"""
    assert [d for d in defects_in(text=charter) if d.startswith("m-")] != []


def test_a_bare_tmux_target_is_flagged():
    """RED demonstration for (a): the defect the whole cut exists to remove."""
    charter = """
```sh
tmux send-keys -t my-session -- 'echo hi'
```
"""
    assert defects_in(text=charter) == [
        "a-bare-tmux-target: tmux send-keys -t my-session -- 'echo hi'"
    ]


def test_an_exact_target_and_a_variable_bound_to_one_are_both_accepted():
    """DISCRIMINATION for (a). Without this, a detector flagging everything passes.

    Covers all three accepted spellings: the literal, `$VAR` and `${VAR}`.
    """
    charter = """
```sh
WORKER_TARGET='=my-session:'   # trailing colon REQUIRED
tmux has-session -t '=my-session:'
tmux send-keys -t "$WORKER_TARGET" -- 'echo hi'
tmux capture-pane -p -t "${WORKER_TARGET}"
```
"""
    assert defects_in(text=charter) == []


def test_a_correct_target_is_not_flagged_by_its_own_trailing_comment():
    """Found by sweeping a real charter, not by imagining a case.

    The first line is CORRECT — the target is exact — but its comment happens to
    contain `-t`, which parsed as a second, bare target. The second line is the
    reason the fix cannot simply cut at the first `#`: a tmux format string is a
    quoted hash, and truncating there would leave a bare target behind.
    """
    charter = """
```sh
WORKER_TARGET='=my-session:'
tmux paste-buffer -b sup -t "$WORKER_TARGET"   # -t REQUIRES the target
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
```
"""
    assert defects_in(text=charter) == []


def test_a_bare_target_hidden_after_a_quoted_hash_is_still_flagged():
    """The quote-aware stripper must not become a way to smuggle a defect past.

    Sabotage that reddens this: make `_strip_trailing_comment` cut at the first
    `#` regardless of quoting — the bare target then lands in the discarded tail.
    """
    charter = """
```sh
tmux display-message -p '#{pane_pid}' -t my-session
```
"""
    assert defects_in(text=charter) == [
        "a-bare-tmux-target: tmux display-message -p '#{pane_pid}' -t my-session"
    ]


def test_an_unguarded_path_resolution_is_flagged_and_a_guarded_one_is_not():
    """RED demonstration and discrimination for (b)."""
    unguarded = """
```sh
pane_cwd=$(tmux display-message -p -t '=my-session:' '#{pane_current_path}')
case "$(readlink -f -- "$pane_cwd")" in
```
"""
    guarded = """
```sh
pane_cwd=$(tmux display-message -p -t '=my-session:' '#{pane_current_path}')
[ -n "$pane_cwd" ] || { echo "HALT: empty pane_current_path"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
```
"""
    assert defects_in(text=unguarded) == [
        'b-unguarded-path-resolution: case "$(readlink -f -- "$pane_cwd")" in'
    ]
    assert defects_in(text=guarded) == []


def test_a_history_fed_capture_is_flagged_and_a_bounded_inspection_is_not():
    """RED demonstration and discrimination for (c).

    The bound and piped forms are the defect; a standalone bounded read is the
    exemplar's own legitimate inspection and must stay clean.
    """
    bound = """
```sh
pane=$(tmux capture-pane -p -t '=my-session:' -S -40)
```
"""
    piped = """
```sh
tmux capture-pane -p -t '=my-session:' -S -40 | grep -qE 'Enter to (select|confirm)'
```
"""
    inspection = """
```sh
tmux capture-pane -p -t '=my-session:' -S -40
pane=$(tmux capture-pane -p -t '=my-session:')
```
"""
    assert defects_in(text=bound) == [
        "c-history-fed-capture: pane=$(tmux capture-pane -p -t '=my-session:' -S -40)"
    ]
    assert len(defects_in(text=piped)) == 1
    assert defects_in(text=inspection) == []


def test_an_empty_prev_watcher_init_is_flagged_and_a_sentinel_is_not():
    """RED demonstration and discrimination for (d).

    This is the defect that reports a session that DOES NOT EXIST as idle.
    """
    empty = """
```sh
prev=""; stable=0
```
"""
    sentinel = """
```sh
prev="__OVERSEER_NO_CAPTURE_YET__"; stable=0
```
"""
    assert defects_in(text=empty) == ['d-empty-prev-watcher-init: prev=""; stable=0']
    assert defects_in(text=sentinel) == []


_PROOF = """
WORKER_TARGET='=demo:'
SUPERVISOR_TARGET='=demo-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET"
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] || { echo "HALT"; echo "REMEDY: retarget"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] || { echo "HALT"; echo "REMEDY: retarget"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
"""


def test_a_supervisor_checked_without_a_liveness_proof_is_flagged():
    """RED demonstration for (e) — the shipped shape, which says yes to a shell.

    Observed 2026-07-28: a supervisor session created as a bare `zsh` returned
    PASS, so a session that could not supervise anything cleared the gate.
    """
    charter = """
```sh
SUPERVISOR_TARGET='=demo-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" || { echo "HALT"; echo "REMEDY: bootstrap"; exit 1; }
```
"""
    assert defects_in(text=charter) == [
        "e-supervisor-trusted-by-name: supervisor existence checked but liveness never proven"
    ]


def test_the_list_sessions_spelling_is_also_in_scope():
    """ANTI-EVASION. Four spellings of the existence check ship in this repo.

    Matching only `SUPERVISOR_TARGET=` would let the `grep -qx` form through,
    and two live charters use exactly that form.

    Uses `-Fqx` deliberately so this leg isolates (e). With the bare `-qx` the
    sample would carry defect (f) as well, and the assertion would stop meaning
    "exactly the supervisor-liveness finding".
    """
    charter = """
```sh
tmux list-sessions -F '#{session_name}' | grep -Fqx 'demo-supervisor' \\
  || { echo "HALT"; echo "REMEDY: bootstrap it"; exit 1; }
```
"""
    assert defects_in(text=charter) == [
        "e-supervisor-trusted-by-name: supervisor existence checked but liveness never proven"
    ]


def test_a_full_liveness_proof_is_not_flagged():
    """THE CONTROL. Without it, a detector that always says yes would pass."""
    assert defects_in(text=f"\n```sh{_PROOF}```\n") == []


def test_a_partial_proof_is_still_flagged():
    """The toothless shape one level down: the `ps` line without its guards.

    A charter can run a real process-tree command and still be unsound — without
    the distinct-pane guard a prefix match runs it against the WORKER's pane and
    finds the worker's agent.
    """
    partial = _PROOF.replace('[ "$supervisor_pane_pid" != "$pane_pid" ]', "true")
    assert partial != _PROOF, "fixture mutation was a no-op"
    assert len(defects_in(text=f"\n```sh{partial}```\n")) == 1


def test_a_charter_that_checks_no_supervisor_is_out_of_scope():
    """THE DOCUMENTED SCOPE LIMIT, asserted rather than left implicit.

    Two archived charters in this repo mention the supervisor in prose and emit
    no supervisor command at all. They have a different problem — no runnable
    precondition — and inventing a precondition block for a closed thread is a
    rewrite, not a remediation. Stating the limit in a test keeps it honest.
    """
    charter = """
```sh
WORKER_TARGET='=demo:'
tmux has-session -t "$WORKER_TARGET" || { echo "HALT"; echo "REMEDY: start it"; exit 1; }
```
"""
    assert defects_in(text=charter) == []


def test_a_regex_session_existence_test_is_flagged():
    """RED demonstration for (f), proven on real tmux before being written.

    With a session named `axb` alive on a private socket, `grep -qx 'a.b'`
    MATCHES and `grep -Fqx 'a.b'` refuses. `-x` anchors the whole LINE; only
    `-F` makes the pattern literal, so a check written to prove presence exactly
    was one character short of doing it.
    """
    charter = """
```sh
tmux list-sessions -F '#{session_name}' | grep -qx 'demo-supervisor' || exit 1
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("f-")] == [
        "f-regex-session-existence-test: "
        "tmux list-sessions -F '#{session_name}' | grep -qx 'demo-supervisor' || exit 1"
    ]


def test_the_literal_session_existence_test_is_accepted():
    """THE CONTROL — `-F` is what the remedy needs, and it must pass."""
    charter = """
```sh
tmux list-sessions -F '#{session_name}' | grep -Fqx 'demo-supervisor' || exit 1
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("f-")] == []


def test_the_picker_footer_regex_is_not_flagged_as_a_session_test():
    """THE FALSE-POSITIVE GUARD, and the reason (f) is scoped to `list-sessions`.

    The picker test uses `grep -qE` with a DELIBERATE regex — anchored
    alternation over the footer strings. Flagging every non-`-F` grep would
    reject correct code, which is exactly what made the whole-file prototype
    unusable as a gate.
    """
    charter = """
```sh
tmux capture-pane -p -t '=demo:' | tail -8 \\
  | grep -qE '^[[:space:]]*Enter to (select|confirm)[[:space:]]*(·.*)?$'
```
"""
    assert defects_in(text=charter) == []


def test_remediating_f_does_not_disarm_e():
    """A detector must not key on another defect's PRE-FIX spelling.

    Found the hard way: `_SUPERVISOR_CHECK` originally pinned the literal `-qx`,
    so rewriting a charter to the correct `-Fqx` made (e) stop seeing it. The
    charter below still proves no supervisor liveness, so (e) must fire whichever
    spelling the existence check uses — otherwise landing one fix silently
    disarms the gate for the other.
    """
    for flags in ("-qx", "-Fqx", "-qFx"):
        charter = f"""
```sh
tmux list-sessions -F '#{{session_name}}' | grep {flags} 'demo-supervisor' || exit 1
```
"""
        found = defects_in(text=charter)
        assert any(d.startswith("e-") for d in found), f"(e) went blind on {flags}: {found}"


def test_realpath_cannot_evade_the_guard_requirement():
    """The self-disarm rule applied BEFORE the evasion appears in a charter.

    (b) used to key on the literal `readlink -f`, so resolving the same path with
    `realpath` carried no guard requirement at all. That is the shape that let
    (e) go blind when (f) landed; the lesson is to key on the ABSENCE OF THE
    GUARD rather than on one spelling of the guarded operation.

    No charter uses `realpath` today. Closing it now is cheap; discovering it
    after a charter adopts the spelling is not.
    """
    unguarded = """
```sh
pane_cwd=$(tmux display-message -p -t '=demo:' '#{pane_current_path}')
case "$(realpath -- "$pane_cwd")" in /data/projects/demo) ;; esac
```
"""
    guarded = """
```sh
pane_cwd=$(tmux display-message -p -t '=demo:' '#{pane_current_path}')
[ -n "$pane_cwd" ] || { echo "HALT"; echo "REMEDY: retarget"; exit 1; }
case "$(realpath -- "$pane_cwd")" in /data/projects/demo) ;; esac
```
"""
    assert [d for d in defects_in(text=unguarded) if d.startswith("b-")] == [
        "b-unguarded-path-resolution: "
        'case "$(realpath -- "$pane_cwd")" in /data/projects/demo) ;; esac'
    ]
    assert [d for d in defects_in(text=guarded) if d.startswith("b-")] == []


_WATCHER = """
```sh
{seed}
for i in $(seq 1 180); do
  pane=$(tmux capture-pane -p -t '=demo:')
  if [ "$pane" = "{var}" ]; then stable=$((stable+1)); else stable=0; {var}="$pane"; fi
done
```
"""


def test_a_differently_named_watcher_variable_cannot_evade_the_seed_rule():
    """THE EVASION (d) was flagged as carrying, now closed.

    The original rule keyed on the literal name `prev`, so a watcher spelling it
    anything else was invisible — the last instance in this module of keying on a
    spelling rather than on the property. `previous=""` is the same defect: an
    empty seed equals the empty capture an ABSENT session returns, so the watcher
    reports idle for a session that does not exist.
    """
    evasive = _WATCHER.format(seed='previous=""; stable=0', var="$previous")
    found = [d for d in defects_in(text=evasive) if d.startswith("d-")]
    assert found == ['d-empty-prev-watcher-init: previous=""; stable=0']
    # ONE finding, not two. Both the literal-`prev` rule and the property rule
    # describe this line; deduping by the full line is what keeps the count equal
    # to the number of real defects.
    assert len(found) == 1


def test_a_sentinel_seed_is_accepted_under_any_variable_name():
    """THE CONTROL, and it must hold for a renamed variable too.

    Without this, a rule that flagged every seeded variable would pass the test
    above while rejecting every correct watcher.
    """
    ok = _WATCHER.format(seed='previous="__NO_CAPTURE_YET__"; stable=0', var="$previous")
    assert [d for d in defects_in(text=ok) if d.startswith("d-")] == []


def test_the_original_literal_prev_rule_is_retained_not_replaced():
    """ADDITIVE, not a narrowing. Both rules must still catch the shipped shape.

    Widening a detector is a chance to accidentally REMOVE what it already
    caught. `prev=""` is the exact text the fleet shipped, so it is asserted
    directly rather than trusted to fall out of the new rule.
    """
    shipped = _WATCHER.format(seed='prev=""; stable=0', var="$prev")
    found = [d for d in defects_in(text=shipped) if d.startswith("d-")]
    assert 'd-empty-prev-watcher-init: prev=""; stable=0' in found


def test_a_block_with_no_stability_comparison_is_not_flagged():
    """An empty variable that no watcher reads is not this defect.

    Keying on the property means an unrelated `x=""` must stay clean, or the gate
    starts failing correct code — the failure that made the prototype unusable.
    """
    charter = """
```sh
x=""
echo "unrelated to any watcher"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("d-")] == []


def test_bash_pipestatus_in_emitted_code_is_flagged():
    """RED demonstration for (g), proven in both shells before being written.

    `zsh -c 'false | true; echo "${PIPESTATUS[0]}"'` prints EMPTY; the same line
    under bash prints 1. The fleet's shell is `/usr/bin/zsh`, so the bash
    spelling makes the remedy for the pipe trap fail in the same silent way as
    the trap — and an empty string reads like a pass.
    """
    charter = """
```sh
just check | tail -5; echo "EXIT=${PIPESTATUS[0]}"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("g-")] == [
        'g-bash-pipestatus-under-zsh: just check | tail -5; echo "EXIT=${PIPESTATUS[0]}"'
    ]


def test_the_zsh_spelling_is_accepted():
    """THE CONTROL: `$pipestatus[1]` is correct here and must not be flagged."""
    charter = """
```sh
just check | tail -5; echo "EXIT=$pipestatus[1]"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("g-")] == []


def test_prose_explaining_the_pipestatus_hazard_is_not_flagged():
    """Correction C14 EXPLAINS this hazard in prose and must stay clean.

    Flagging it would make documenting a fix raise a charter's score — the exact
    property that made the whole-file prototype unusable as a gate.
    """
    charter = """
C14 — the charter's own anti-pipe-trap advice silently does nothing in the shell
we run. `PIPESTATUS` is bash; this fleet's shell is zsh, where the array is
`$pipestatus[1]`. Writing `echo "EXIT=${PIPESTATUS[0]}"` here yields an EMPTY
string, which reads like a pass when skimmed.
"""
    assert defects_in(text=charter) == []


# --------------------------------------------------------------------------
# (h) the ledger read that cannot SUCCEED — the mirror of every detector above.
# --------------------------------------------------------------------------


def test_a_wrapper_less_ledger_read_is_flagged():
    """The shipped form. Measured to exit 1 with "Access denied" on 2026-07-30."""
    charter = """
```sh
ledger_anchor='overseer-d4t'
bd show "$ledger_anchor" --json \\
  || { echo "HALT: cannot re-measure"; exit 1; }
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("h-")] != []


def test_a_detected_wrapper_with_a_bare_fallback_is_accepted():
    """THE CONTROL. Detection must be accepted, including its bare `else` branch.

    An adopter with no wrapper must still be able to re-measure, so the bare call
    inside the fallback is CORRECT and flagging it would force a hard-coded path —
    trading one false HALT for another.
    """
    charter = """
```sh
ledger_show() {
  if command -v with-livespec-env.sh >/dev/null 2>&1; then
    with-livespec-env.sh -- bd show "$1" --json
  else
    bd show "$1" --json
  fi
}
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("h-")] == []


def test_a_direct_wrapper_invocation_is_accepted():
    """The spelling livespec-dev-tooling's rop-railway-enforcement already used.

    Two correct forms exist in the fleet and the gate must accept both, or it
    would redden a charter that was right before this detector was written.
    """
    charter = """
```sh
/usr/local/bin/with-livespec-env.sh -- bd show livespec-dev-tooling-8o8e --json
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("h-")] == []


def test_prose_describing_the_bare_ledger_hazard_is_not_flagged():
    """Prose ABOUT the defect must stay clean — the C4 lesson, re-applied."""
    charter = """
The generator emitted `bd show "$ledger_anchor" --json` with no credential
wrapper, so a bare `bd` returned "Access denied" and the REMEDY misdirected at a
healthy ledger.
"""
    assert defects_in(text=charter) == []


# --------------------------------------------------------------------------
# (i) a fixed cap that hides a retraction, and (j) a read that cannot fail.
# --------------------------------------------------------------------------


def test_a_fixed_cap_marker_read_without_a_notice_is_flagged():
    """`sed -n '1,220p'` against a 697-line marker showed 31.6% and said nothing."""
    charter = """
```sh
test ! -f "$supervisor_marker" || sed -n '1,220p' "$supervisor_marker"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("i-")] != []


def test_a_truncating_read_that_announces_itself_is_accepted():
    """THE CONTROL: the NOTICE is what makes truncation acceptable, not the size.

    A bigger constant is stale tomorrow; an announced cut is not silent.
    """
    charter = """
```sh
[ -n "${supervisor_marker:-}" ] || { echo "HALT: unset"; exit 1; }
marker_lines=$(wc -l < "$supervisor_marker")
sed -n '1,160p' "$supervisor_marker"
printf 'TRUNCATED: lines 161-%d of %d NOT SHOWN\\n' "$((marker_lines - 160))" "$marker_lines"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("i-")] == []


def test_an_unguarded_marker_binding_is_flagged():
    """`test ! -f ""` is TRUE, so the read no-ops and still exits 0.

    This is (b)'s empty-string false-pass in a different command in the same file.
    """
    charter = """
```sh
test ! -f "$supervisor_marker" || cat "$supervisor_marker"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("j-")] != []


def test_a_marker_binding_guarded_non_empty_first_is_accepted():
    """THE CONTROL: guard non-empty BEFORE the file test, exactly as C2 requires."""
    charter = """
```sh
[ -n "${supervisor_marker:-}" ] \\
  || { echo "HALT: supervisor_marker is unset or empty"; exit 1; }
test ! -f "$supervisor_marker" || cat "$supervisor_marker"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("j-")] == []


# --------------------------------------------------------------------------
# (k) a file mtime printed as LOCAL time and labelled UTC — the C19 trap.
# --------------------------------------------------------------------------


def test_a_file_mtime_read_labelled_utc_is_flagged():
    """RED demonstration for (k), measured on this host before being written.

    `date -u -r pyproject.toml '+%Y-%m-%dT%H:%M:%SZ'` printed `15:40:10Z` while
    the file's true UTC mtime was `13:40:10Z`. `-r` does not honour `-u` under
    uutils coreutils, local is CEST, and the appended `Z` hides the two hours.
    """
    charter = """
```sh
worker_state_at=$(date -u -r "$supervisor_marker" '+%Y-%m-%dT%H:%M:%SZ')
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("k-")] == [
        'k-local-time-labelled-utc: worker_state_at=$(date -u -r "$supervisor_marker" '
        "'+%Y-%m-%dT%H:%M:%SZ')"
    ]


def test_the_epoch_form_that_honours_u_is_accepted():
    """THE ACCEPTED-FORM CONTROL: `date -u -d @<epoch>` DOES apply `-u`.

    Measured on the same file in the same shell: `-d @1785418810` printed
    `13:40:10Z`, the true UTC mtime. Only the `-r` form is defective, so flagging
    the correct remedy would leave a charter no spelling it could use.
    """
    charter = """
```sh
mtime_epoch=$(stat -c %Y "$supervisor_marker")
worker_state_at=$(date -u -d @"$mtime_epoch" '+%Y-%m-%dT%H:%M:%SZ')
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("k-")] == []


def test_a_plain_utc_now_is_accepted():
    """THE SECOND ACCEPTED FORM, and the one both real charters already carry.

    `.ai/supervisor-protocol.md` and this thread's binder each close their ledger
    re-measure with `date -u '+MEASURED_AT: ...Z'`. That reads no file, so `-u` is
    honoured and the `Z` is true — measured 2026-07-30, the only two `date` lines
    in fenced code across all eight tracked charters.
    """
    charter = """
```sh
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("k-")] == []


def test_prose_documenting_the_date_trap_is_not_flagged():
    """THE PROSE CONTROL, and it is mandatory rather than decorative.

    C19 QUOTES the defective command inside `.ai/supervisor-protocol.md`, which
    this gate scans as of PR #358. A detector that fired on it would redden the
    charter that documents the fix — the exact property that made the whole-file
    prototype unusable as a gate. The wording below is C19's own.
    """
    charter = """
C19 — this host runs **uutils coreutils, not GNU**, and `date -u -r <file>`
**does not apply `-u`** here: it prints LOCAL time, so the `Z` you append is a
lie, and local being CEST makes it a silent two-hour error. I compared it against
a cache-directory mtime read with `date -u -d @<epoch>` — which DOES honour `-u`.
"""
    assert defects_in(text=charter) == []


def test_flag_order_bundling_and_the_long_form_cannot_evade_the_rule():
    """The property is file-read-plus-UTC-claim, not the token sequence `-u -r`.

    Keying on the literal spelling is what made (e) go blind the moment (f) was
    remediated, so every arrangement of the same defect is asserted here.
    """
    charter = """
```sh
a=$(date -r "$f" -u '+%FT%TZ')
b=$(date -ur "$f" '+%FT%TZ')
c=$(date --utc --reference="$f" '+%FT%TZ')
```
"""
    flagged = [d for d in defects_in(text=charter) if d.startswith("k-")]
    assert len(flagged) == 3, flagged


def test_a_z_labelled_file_read_is_flagged_without_any_u_flag():
    """Dropping `-u` does not make it honest — the format still asserts UTC.

    This is the shorter route to the same lie, and a detector demanding `-u`
    would report the more obviously wrong charter as clean.
    """
    charter = """
```sh
stamp=$(date -r "$f" '+%Y-%m-%dT%H:%M:%SZ')
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("k-")] != []


def test_an_honestly_labelled_local_file_read_is_accepted():
    """THE THIRD CONTROL: `%Z` PRINTS the zone, it does not assert UTC.

    A charter may legitimately show a file's local mtime as long as it says so.
    Flagging this would be flagging correct code, and `%Z` is one character from
    the literal `Z` the rule is about.
    """
    charter = """
```sh
printf 'marker last written: %s\\n' "$(date -r "$supervisor_marker" '+%H:%M %Z')"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("k-")] == []


def test_a_later_commands_own_r_flag_is_not_read_as_this_ones():
    """Argument runs stop at a shell separator, so `test -r` next door is clean.

    Without that cut the accepted form above would be flagged whenever any `-r`
    appeared later on the line — a false positive on correct code.
    """
    charter = """
```sh
date -u '+%Y-%m-%dT%H:%M:%SZ' && test -r "$supervisor_marker"
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("k-")] == []


def test_a_commented_out_date_trap_is_not_counted():
    """Comments are stripped, so documenting the hazard beside the fix is safe.

    Both halves matter: a full-line comment and a trailing one on a CORRECT
    command, which is where a charter would most naturally warn about it.
    """
    charter = """
```sh
# never: date -u -r "$f" '+%FT%TZ'
stamp=$(date -u -d @"$epoch" '+%FT%TZ')   # not date -u -r "$f" — that prints local
```
"""
    assert [d for d in defects_in(text=charter) if d.startswith("k-")] == []
