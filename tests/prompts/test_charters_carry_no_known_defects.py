"""Gate every charter IN THIS REPO against the six known defect classes.

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

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_CHARTER_GLOBS = (
    "plan/*/supervisor-handoff.md",
    "plan/archive/*/supervisor-handoff.md",
)

# The charter that was hardened by hand and is what the generator must be able to
# produce. Accept either location: a plan thread moves into `plan/archive/` when
# it closes, and an unguarded read of the live path alone already made archiving
# a thread a CI-reddening act once.
_EXEMPLAR_CANDIDATES = (
    _REPO_ROOT / "plan" / "supervisor-prompt-quality" / "supervisor-handoff.md",
    _REPO_ROOT / "plan" / "archive" / "supervisor-prompt-quality" / "supervisor-handoff.md",
)

_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n(.*?)^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)

# Matches a shell binding whose value starts with "=", quoted or bare, with or
# without an `export`/`readonly`/`local` keyword, and TOLERATING a trailing
# comment. That tolerance is load-bearing rather than a nicety: the exemplar
# annotates its binding with a reminder that the trailing colon is required, and
# an earlier version of this pattern demanding end-of-line right after the value
# failed to see that binding — and so reported all ten of that charter's CORRECT
# targets as bare.
_BINDING = re.compile(
    r"""^\s*(?:export\s+|readonly\s+|local\s+)?([A-Za-z_][A-Za-z0-9_]*)="""
    r"""(['"]?)(=[^'"\s]*)\2\s*(?:#.*)?$""",
    re.MULTILINE,
)
_TARGET = re.compile(r"-t\s+((?:'[^']*')|(?:\"[^\"]*\")|(?:\S+))")
_TMUX_LINE = re.compile(r"\btmux\b")
_READLINK = re.compile(r"readlink\s+-f")
_NONEMPTY_GUARD = re.compile(r"(?:test\s+-n|\[\s+-n|\[\[\s+-n|-z\s)")

# Defect (c) is NOT "capture-pane -S -N appears". A bounded scrollback read is a
# legitimate read-only inspection and the exemplar performs one. The defect is
# history reaching the PICKER TEST or the PANE DIFF — `-S -N` output bound into a
# variable, or piped straight into the footer grep — because a picker that closed
# minutes ago is still in the buffer and the test then fires on stale history.
_CAPTURE_S_BOUND = re.compile(r"=\s*\$\(\s*[^)]*capture-pane[^)]*-S\s+-\d+")
_CAPTURE_S_PIPED = re.compile(r"capture-pane[^\n|]*-S\s+-\d+[^\n]*\|[^\n]*grep")

# `prev=""` equals the empty capture a DEAD session returns, so the watcher counts
# "unchanged" three times and reports idle for a session that does not exist. The
# exemplar seeds a sentinel that no capture can equal.
_PREV_EMPTY = re.compile(r"""prev=(?:''|""|\s*$)""", re.MULTILINE)

# (e) overseer-ejja5o. A charter that CHECKS the supervisor session must PROVE it
# holds a live agent, not merely that a session by that name exists. Observed
# 2026-07-28: a supervisor session created as a bare `zsh` returned PASS, so a
# session that could not supervise anything cleared the gate.
#
# Two spellings are in the wild and both count as "checks the supervisor" — the
# bound `SUPERVISOR_TARGET='=<name>-supervisor:'` form and the
# `list-sessions | grep ... '<name>-supervisor'` form. Matching only one would
# let the other evade.
#
# THE GREP FLAGS ARE MATCHED LOOSELY, and that is a fix for a real interaction
# bug rather than laziness. An earlier version pinned the literal `-qx`, so the
# moment defect (f) was remediated to `-Fqx` this detector went BLIND and (e)
# stopped firing on the very charters it had just flagged. A detector keyed to
# the exact spelling of a DIFFERENT defect's pre-fix state is a verifier that
# disarms itself when the other fix lands.
_SUPERVISOR_CHECK = re.compile(r"SUPERVISOR_TARGET=|grep\s+-\S+\s+'[^']*-supervisor'")
_SUPERVISOR_PROOF_PS = '--ppid "$supervisor_pane_pid"'
_SUPERVISOR_PROOF_GUARD = '[ -n "$supervisor_pane_pid" ]'
_SUPERVISOR_PROOF_DISTINCT = '"$supervisor_pane_pid" != "$pane_pid"'

# (f) A session-existence test written with `grep -qx` is exact-LINE but its
# pattern is still a REGEX, so "exact" is one character short of literal.
# PROVEN on a private socket: with a session named `axb` alive,
# `grep -qx 'a.b'` MATCHES and `grep -Fqx 'a.b'` refuses. Latent while topic
# slugs stay `[a-z0-9-]`, but the check exists to prove presence EXACTLY and it
# can say yes for a name that is not there.
#
# Scoped to the `list-sessions | grep -qx` idiom on purpose. The picker footer
# test deliberately uses `grep -qE` with a real regex, and flagging that would
# be the false-positive-on-correct-code failure that made the prototype
# unusable as a gate.
_LIST_SESSIONS_GREP = re.compile(r"list-sessions[^\n|]*\|[^\n]*grep\s+(-\S+)")


def _code_blocks(*, text: str) -> list[str]:
    """Every fenced block body, in document order. Prose is discarded."""
    return [match.group(2) for match in _FENCE.finditer(text)]


def _is_comment(*, line: str) -> bool:
    return line.lstrip().startswith("#")


def _strip_trailing_comment(*, line: str) -> str:
    """Drop a trailing `# ...` comment, RESPECTING QUOTES.

    Both halves are load-bearing and each was found by a real false result.
    Not stripping at all flagged this correct line, because the comment's own
    `-t` parsed as a second target:

        tmux paste-buffer -b sup -t "$WORKER_TARGET"   # -t REQUIRES the target

    Stripping naively is worse: tmux format strings are FULL of unquoted-looking
    hashes, so cutting at the first `#` would truncate this correct line into a
    bare target and flag it too:

        pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
    """
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def bare_targets(*, text: str) -> list[str]:
    """`tmux -t` arguments that do not resolve to the exact `'=name:'` form.

    Bindings are collected across the WHOLE document, not per block: the exemplar
    binds its target in the preconditions and uses `"$WORKER_TARGET"` in later
    blocks, so block-scoped resolution would report every correct downstream use.
    """
    blocks = _code_blocks(text=text)
    bound = {match.group(1) for match in _BINDING.finditer("\n".join(blocks))}
    found: list[str] = []
    for block in blocks:
        for raw in block.splitlines():
            if not _TMUX_LINE.search(raw) or _is_comment(line=raw):
                continue
            line = _strip_trailing_comment(line=raw)
            for match in _TARGET.finditer(line):
                token = match.group(1).strip("'\"")
                if token.startswith("="):
                    continue
                name = _variable_name(token=token)
                if name is not None and name in bound:
                    continue
                found.append(line.strip())
    return found


def _variable_name(*, token: str) -> str | None:
    if token.startswith("${") and token.endswith("}"):
        return token[2:-1]
    if token.startswith("$"):
        return token[1:]
    return None


def unguarded_readlink(*, text: str) -> list[str]:
    """`readlink -f` with no non-empty guard in the preceding three lines.

    `readlink -f ""` returns the CWD with exit 0 on GNU coreutils, so a
    containment check fed an empty `pane_current_path` renders as PASS against
    the repo root.
    """
    found: list[str] = []
    for block in _code_blocks(text=text):
        lines = block.splitlines()
        for index, line in enumerate(lines):
            if not _READLINK.search(line) or _is_comment(line=line):
                continue
            window = "\n".join(lines[max(0, index - 3) : index + 1])
            if not _NONEMPTY_GUARD.search(window):
                found.append(line.strip())
    return found


def history_fed_capture(*, text: str) -> list[str]:
    """`capture-pane -S -N` feeding the picker test or the pane diff."""
    found: list[str] = []
    for block in _code_blocks(text=text):
        for line in block.splitlines():
            if _is_comment(line=line):
                continue
            if _CAPTURE_S_BOUND.search(line) or _CAPTURE_S_PIPED.search(line):
                found.append(line.strip())
    return found


def empty_prev_watcher_init(*, text: str) -> list[str]:
    """Watcher seeded with `prev=""`, which an absent session's capture equals."""
    found: list[str] = []
    for block in _code_blocks(text=text):
        for line in block.splitlines():
            if _is_comment(line=line):
                continue
            if _PREV_EMPTY.search(line):
                found.append(line.strip())
    return found


def regex_session_existence_test(*, text: str) -> list[str]:
    """A `list-sessions | grep` presence test whose pattern is not LITERAL.

    `-x` anchors the whole line; it does not make the pattern literal. Only `-F`
    does. A name carrying a regex metacharacter therefore matches a DIFFERENT
    session, and the check reports present for something absent.
    """
    found: list[str] = []
    for block in _code_blocks(text=text):
        for raw in block.splitlines():
            if _is_comment(line=raw):
                continue
            match = _LIST_SESSIONS_GREP.search(raw)
            if match is not None and "F" not in match.group(1):
                found.append(raw.strip())
    return found


def supervisor_trusted_by_name(*, text: str) -> list[str]:
    """A supervisor existence check with no liveness proof anywhere (ejja5o).

    SCOPE, stated rather than hidden: this fires only on a charter that ACTUALLY
    EMITS a supervisor check. A charter that emits none at all is not flagged
    here — it has a different problem (no runnable precondition), and inventing
    a precondition block for a thread that never had one is a rewrite, not a
    remediation. Two archived charters in this repo are in that category.

    The proof is required somewhere in the charter rather than inside the same
    block, because the shipped charters spell the existence check four different
    ways and pinning the layout would flag correct variants.
    """
    blocks = _code_blocks(text=text)
    checks = [b for b in blocks if _SUPERVISOR_CHECK.search(b)]
    if not checks:
        return []
    joined = "\n".join(blocks)
    if all(
        needle in joined
        for needle in (
            _SUPERVISOR_PROOF_PS,
            _SUPERVISOR_PROOF_GUARD,
            _SUPERVISOR_PROOF_DISTINCT,
        )
    ):
        return []
    return ["supervisor existence checked but liveness never proven"]


_DETECTORS = (
    ("a-bare-tmux-target", bare_targets),
    ("b-unguarded-readlink", unguarded_readlink),
    ("c-history-fed-capture", history_fed_capture),
    ("d-empty-prev-watcher-init", empty_prev_watcher_init),
    ("e-supervisor-trusted-by-name", supervisor_trusted_by_name),
    ("f-regex-session-existence-test", regex_session_existence_test),
)


def defects_in(*, text: str) -> list[str]:
    """Every defect in one charter, as `<class>: <offending line>` strings."""
    return [f"{name}: {line}" for name, detector in _DETECTORS for line in detector(text=text)]


def _charters() -> list[Path]:
    found: list[Path] = []
    for glob in _CHARTER_GLOBS:
        found.extend(sorted(_REPO_ROOT.glob(glob)))
    return found


def test_this_repo_has_charters_to_scan():
    """A gate over an empty file set passes vacuously and proves nothing.

    Sabotage that reddens this: point `_CHARTER_GLOBS` at a path that matches
    nothing. Without this assertion that sabotage would look like a clean repo.
    """
    assert _charters() != []


def test_every_charter_in_this_repo_is_free_of_the_four_known_defects():
    """THE GATE. A charter carrying any of (a)-(d) fails here, in this repo's CI.

    Sabotage that reddens this: restore a bare `-t <session>` target in any
    charter under `plan/`.
    """
    offences = {
        str(path.relative_to(_REPO_ROOT)): defects_in(text=path.read_text(encoding="utf-8"))
        for path in _charters()
    }
    assert {path: found for path, found in offences.items() if found} == {}


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


def test_an_unguarded_readlink_is_flagged_and_a_guarded_one_is_not():
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
        'b-unguarded-readlink: case "$(readlink -f -- "$pane_cwd")" in'
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
