"""Gate every charter IN THIS REPO against the thirteen known defect classes.

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

import json
import re
from pathlib import Path, PurePosixPath

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# `.ai/supervisor-protocol.md` is HALF OF EVERY DEPLOYED CHARTER and was going
# unscanned. The two-layer split moved the role contract — preconditions, the
# ledger re-measure, the watcher shapes — out of the per-thread binder and into
# this shared file, and the glob was never widened to follow it. So the gate went
# on reporting a clean repo while the larger half of what a supervisor actually
# reads was never examined. Measured 2026-07-30: it carried the (h) defect.
#
# This is the epic's own defect class opened by the epic's own refactor, which is
# the third instance in this thread. A gate's SCOPE is as load-bearing as its
# detectors: widening the detectors while the glob stays behind buys nothing.
_CHARTER_GLOBS = (
    ".ai/supervisor-protocol.md",
    "plan/*/supervisor-handoff.md",
    "plan/archive/*/supervisor-handoff.md",
)

# The charter that was hardened by hand and is what the generator must be able to
# produce. Accept either location: a plan moves into `plan/archive/` when
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
# Any path-resolution command whose empty-input behaviour is
# implementation-dependent. `realpath` is included so an alternative
# spelling cannot evade the guard requirement (see docstring below).
_PATH_RESOLVE = re.compile(r"readlink\s+-f|\brealpath\b")
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

# (d) continued. The rule above keys on the literal name `prev`, so a watcher
# using any other variable name evaded it — the last instance in this module of
# keying on a spelling instead of on the property. The property is: the variable
# the stability comparison treats as the PREVIOUS capture must be seeded with
# something no real capture can equal. An empty seed equals the empty capture an
# ABSENT session returns, so the watcher counts "unchanged" and reports idle for
# a session that does not exist.
#
# ADDITIVE, NOT A REPLACEMENT. `_PREV_EMPTY` is retained and still checked, so
# this cannot quietly narrow what was already caught; the name-agnostic rule only
# adds. All six tracked charters seed a sentinel, so neither rule fires today.
_STABILITY_CMP = re.compile(r'\[\s*"\$(\w+)"\s*=\s*"\$(\w+)"\s*\]')
_EMPTY_SEED = re.compile(r"""^\s*(\w+)=(?:""|''|)\s*(?:;|$)""", re.MULTILINE)

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

# (g) `PIPESTATUS` is BASH. This fleet's shell is zsh, where the array is
# `$pipestatus[1]` -- lowercase and 1-INDEXED. Proven: `zsh -c 'false | true;
# echo "${PIPESTATUS[0]}"'` prints an EMPTY string while `${pipestatus[1]}`
# prints 1. Empty reads like a pass, so the remedy for the pipe trap fails in
# the same silent way as the trap it is meant to catch.
#
# PREVENTIVE: zero charters carry this in code today. It is gated now for the
# same reason `realpath` was -- closing a hole before a charter walks through it
# is cheap, and discovering it afterwards is not. Fenced code only, so the
# Corrections entries that EXPLAIN the hazard (C14 among them) stay clean; a
# detector that flagged the documentation of a fix is what made the whole-file
# prototype unusable.
_BASH_PIPESTATUS = re.compile(r"\bPIPESTATUS\b")

# (h) A ledger re-measure that CANNOT SUCCEED. This fleet's `bd` reaches a
# per-repo TENANT database and needs the fleet credential wrapper; a bare `bd`
# returns "Access denied". Measured 2026-07-30 in this repo: bare
# `bd show <anchor> --json` exits 1 with Access denied, the same call through the
# wrapper exits 0 with real JSON, and bare `bd` fails in the orchestrator tenant
# too.
#
# THIS IS THE MIRROR OF (a)-(g). Every detector above catches a check that cannot
# FAIL. This one catches a command that cannot PASS — and the shipped charter
# then advised "REMEDY: fix ledger access", pointing the reader at a ledger that
# was already healthy. It cost a supervisor its own cold-open boot.
#
# BOTH CORRECT SPELLINGS ARE ACCEPTED, because two exist in the fleet: detection
# with a fallback (`command -v with-livespec-env.sh`), which an adopter WITHOUT a
# wrapper needs, and a direct wrapper invocation, which is what
# livespec-dev-tooling's rop-railway-enforcement charter already carried. A
# hard-coded path is not required and must not be, or the gate would trade one
# false HALT for another on an adopter that has no wrapper.
_BD_INVOCATION = re.compile(r"(?<![-\w])bd\s+(?:show|list|update|create|close)\b")

# THE WRAPPER IS A PROPERTY, NOT A NAME. This pinned the literal
# `with-livespec-env.sh` and therefore scored `homelab`'s CORRECT charters as
# defective — four times, across two files. `homelab` declared a different
# wrapper and resolved it from its own `.livespec.jsonc` instead of hard-coding
# any name, which is STRICTLY BETTER than the form this detector demanded. The
# gate punished the best implementation in the fleet, and it failed quietly and
# in the wrong direction.
#
# `plan/fleet-charter-remediation/` records the consequence: remediating against
# the uncorrected rule would have meant rewriting a config-driven lookup into a
# hard-coded name, in the one fleet repo that consumes no pin and so cannot be
# corrected by a later release.
#
# THE FIRST FIX WIDENED THE LITERAL INTO A NAME PATTERN, AND THAT WAS STILL A
# NAME. `with-[...]-env\.sh` is a convention, not a contract, and `homelab`
# left the convention: its `credential_wrapper` is now a multi-element
# scoped-injection argv headed by `with-homelab-aws.sh` — an `-aws.sh`, not an
# `-env.sh`. Measured 2026-08-06: the pattern below scored that CORRECT
# invocation as a defect, which is the ORIGINAL false positive returning under
# a new spelling. Widening the pattern again (`-(env|aws)\.sh`) would buy one
# more rename and re-arm the same trap, so the resolution does not name at all:
#
# A `bd` call is wrapped when the charter EITHER
#   * invokes `bd` through the wrapper THE REPO ITSELF DECLARES in its own
#     `.livespec.jsonc` — resolved at scan time, whatever it is called, and
#     however many argv elements it has;
#   * or names a `with-<repo>-env.sh` wrapper — any member's — which remains a
#     real fleet convention and a regression control, no longer the only key;
#   * or binds one to a VARIABLE, proves it with `command -v`, and invokes `bd`
#     THROUGH THAT SAME VARIABLE.
# The variable form requires both halves of one binding on purpose: probing for
# some unrelated binary must not clear the detector, or `(h)` becomes unfailable.
_WRAPPER_NAME = r"with-[A-Za-z0-9_.-]+-env\.sh"
_WRAPPER_DETECTED = re.compile(rf"command\s+-v\s+\"?{_WRAPPER_NAME}")
_WRAPPER_DIRECT = re.compile(rf"{_WRAPPER_NAME}[^\n]*\bbd\b")
_WRAPPER_VAR_DETECTED = re.compile(r"command\s+-v\s+\"?\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
_WRAPPER_VAR_INVOKED = re.compile(r"\"?\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?\"?\s+(?:--\s+)?bd\b")

_JSONC_COMMENT = re.compile(r"^\s*//.*$", flags=re.MULTILINE)


def declared_wrapper_tokens(*, repo_root: Path = _REPO_ROOT) -> frozenset[str]:
    """The wrapper THIS repo declares, as spellings a charter might use.

    Read from `.livespec.jsonc` at scan time rather than pinned here, so a repo
    that renames or restructures its wrapper does not become defective by
    default. Only the HEAD of the argv is a wrapper: the remaining elements are
    that wrapper's own flags (`--role`, `--bind`, `--`) and would match far too
    much. Both the declared path and its basename are returned, because charters
    legitimately write either.

    An empty set is the honest answer for a repo that declares no wrapper — an
    adopter without one must not be scored against a wrapper it does not have,
    and the other two clauses still apply.
    """
    config = repo_root / ".livespec.jsonc"
    if not config.is_file():
        return frozenset()
    declared = json.loads(_JSONC_COMMENT.sub("", config.read_text(encoding="utf-8"))).get(
        "credential_wrapper"
    )
    if not isinstance(declared, list) or not declared:
        return frozenset()
    head = str(declared[0])
    return frozenset({head, PurePosixPath(head).name})


def _declared_wrapper_wraps(*, joined: str, tokens: frozenset[str]) -> bool:
    """A declared wrapper token precedes a `bd` call on the same logical line."""
    return any(
        _BD_INVOCATION.search(line) and any(token in line for token in tokens)
        for line in joined.splitlines()
    )


# (i) A FIXED-CAP read of the supervisor marker, with no truncation notice.
# Observed 2026-07-30: a charter emitted `sed -n '1,220p'` against a marker that
# was 528 lines, then 697 within hours. No constant survives an append-only file.
#
# SILENTLY SHOWING LESS IS NOT THE HARM. The harm is SEVERING A RETRACTION FROM
# ITS CLAIM: that marker carried an OPEN OBLIGATIONS block assigning
# `holder: worker` inside the visible window while its retraction sat below the
# cut, so a cold-open reader was handed a discharged obligation as live work.
# Corrections land at the END of an append-only file, which makes a head-only
# read the worst possible cut.
#
# WHAT MAKES IT PASS is the NOTICE, not the size — a bigger constant is stale
# tomorrow. A charter that truncates must say so.
_FIXED_CAP_READ = re.compile(r"sed\s+-n\s+['\"]?1,\s*\d+\s*p['\"]?")
_TRUNCATION_NOTICE = re.compile(r"TRUNCATED")

# (j) A marker read that SILENTLY NO-OPS when the binding is unset. `test ! -f ""`
# is TRUE for the empty string, so `test ! -f "$m" || sed ... "$m"` short-circuits
# and prints NOTHING at rc 0. The binding is supplied by a markdown TABLE, never
# by a shell assignment, so a reader who pastes the block verbatim gets silence
# and a success exit.
#
# This is (b)'s empty-string false-pass — the one that made `readlink -f ""`
# resolve to the CWD and render as PASS — reappearing in a different command in
# the same generated file. The same fix applies: guard non-empty FIRST.
_MARKER_FILE_TEST = re.compile(r"(?:test|\[)\s+!?\s*-f\s+\"?\$\{?supervisor_marker")
_MARKER_NONEMPTY_GUARD = re.compile(r"-[nz]\s+\"?\$\{?supervisor_marker")

# (k) `date -u -r <file>` DOES NOT APPLY `-u`. This host runs uutils coreutils
# 0.2.2, not GNU — the same divergence already recorded for `readlink`/`realpath`
# in (b). Measured 2026-07-30 on `pyproject.toml`:
#
#     date -u -r pyproject.toml '+%Y-%m-%dT%H:%M:%SZ'  ->  2026-07-30T15:40:10Z
#     datetime.fromtimestamp(mtime, timezone.utc)      ->  2026-07-30T13:40:10Z
#     date -u -d @1785418810 '+%Y-%m-%dT%H:%M:%SZ'     ->  2026-07-30T13:40:10Z
#
# So `-r` prints LOCAL time, local is CEST, and the `Z` the charter appends is a
# silent TWO-HOUR lie. `-d @<epoch>` honours `-u` and is correct.
#
# THIS IS (g)'s SHAPE AND IT HAS ALREADY BEEN WALKED THROUGH. (g) gates a command
# correct on the fleet's documented assumptions and silently wrong on this host's
# actual tooling, producing a value that reads like a pass. On 2026-07-30 a
# supervisor timestamped the worker's state file with exactly this command,
# compared it against a cache mtime read with `date -u -d @<epoch>`, and published
# that the worker's measurement was made 69 minutes AFTER the event. The true
# ordering was 51 minutes BEFORE — the accusation was backwards. Both values
# carried a `Z`, so the disagreement was invisible. Recorded as correction C19.
#
# KEYED ON THE PROPERTY, NOT ON THE `-u -r` SPELLING: a `date` invocation that
# reads a FILE must not claim UTC. Flag order, short-flag bundling, an attached
# value and the `--reference` long form therefore cannot evade it, and a `-r` with
# no `-u` at all but a literal `Z` in its format is the same lie by a shorter
# route. An honest `date -r "$f" '+%H:%M %Z'` — local time wearing its own zone
# name — stays clean, and so does `%Z` anywhere, because that conversion PRINTS
# the real zone rather than asserting UTC.
_DATE_ARGS = re.compile(r"\bdate\b((?:[ \t]+(?:'[^']*'|\"[^\"]*\"|[^\s;|&)]+))*)")
_DATE_TOKEN = re.compile(r"'[^']*'|\"[^\"]*\"|\S+")
_DATE_SHORT_BUNDLE = re.compile(r"\A-([A-Za-z]+)")
_DATE_FILE_LONG = re.compile(r"\A--reference(?:=|\Z)")
_DATE_UTC_LONG = re.compile(r"\A--(?:utc|universal)\Z")
_DATE_UTC_LABEL = re.compile(r"(?<!%)Z|UTC")

# (l) A WATCHER BUSY TEST THAT MATCHES AN IDLE PANE, so its idle branch is
# unreachable and the watcher can only ever report busy. Work-item `overseer-c45`.
#
# Observed 2026-08-02: `rop-railway-enforcement-supervisor` reported
# `working (background shell)` for DAYS while its worker sat motionless. Its
# watcher had added a content grep on top of the canonical stability test:
#
#     grep -qE '[0-9]+[hms] |tokens|esc to interrupt|Running|Doing|…|monitor'
#
# An idle agent pane PERMANENTLY renders its completed-turn summary, and `14m `
# in `Worked for 14m 56s` satisfies `[0-9]+[hms] `. So `busy=1` on every poll,
# the loop ran its ceiling, printed "STILL BUSY, RE-ARM", and the supervisor
# re-armed forever. SELF-SEALING: the live background shell made the session
# report `shell` to the daemon, which by contract will not keystroke into a busy
# pane, so the wedged watcher suppressed its own rescue.
#
# THE RULE IS RUN THE PATTERN, NOT MATCH THE PATTERN. `overseer-c45` asks for
# "idle exit rests on stability alone, or at minimum any busy regex must be shown
# NOT to match an idle pane". The first is not statically decidable in the
# direction that matters — the CORRECTED charter also computes `busy` from a
# content grep, it simply does not gate the idle exit with it — so a rule keyed
# on "a content grep sits near a watcher" would flag the shape the fleet is
# supposed to ADOPT. The second is a pure function of the pattern and a fixture,
# and that is what this detector implements.
#
# THE PIPELINE IS MODELLED, NOT THE PATTERN IN ISOLATION, and that is
# LOAD-BEARING. The corrected test is safe only BECAUSE of its `grep -v`
# exclusion: an idle pane whose scrollback holds a completed `⎿  $ … (6m 50s)`
# line carries the very `… (` shape the live-marker test keys on, and the
# charter records that the 16-line window and the `⎿` exclusion "only work as a
# PAIR". A detector that extracted `esc to interrupt|…[[:space:]]*\(` and ran it
# against the raw fixture would flag the corrected form. So `-v` greps FILTER the
# fixture and `tail`/`head` NARROW it, exactly as the shell would.
#
# THE FIXTURES ARE CAPTURED, NOT IMAGINED — live fleet panes, 2026-08-02. Both
# renderers are represented because they differ, and the idle one carries the
# `⎿  $ … (` hazard line on purpose.
_IDLE_PANE_RENDER = "\n".join(
    (
        "  main is clean and matches origin/main; the worktree and both refs are gone.",
        "  ⎿  $ git worktree list --porcelain | head -40 (6m 50s · 4 lines)",
        "",
        "─ Worked for 24m 01s ────────────────────────────────────────────────────",
        "",
        "✻ Worked for 14m 56s",
        "",
        "※ recap: the thread is fully complete; nothing remains.",
        "                       new task? /clear to save 625.9k tokens",
        "──────────────────────────────── 06-resilience-acceptance ──",
        "❯ ",
        "─────────────────────────────────────────────────────────────",
        "  Opus 5 (1M context) | /data/projects/livespec-overseer | master | Ctx: 49% left",
        "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents",
    )
)

# The other direction. A busy test that matches NOTHING satisfies this detector
# trivially, and a watcher whose busy probe never fires wakes a supervisor into a
# pane that is still working. This module does not gate that — a pattern's
# reach on a BUSY pane is asserted in `test_busy_test_discriminates.py`, which is
# where both controls live — but the fixture belongs beside its twin.
_BUSY_PANE_RENDER = "\n".join(
    (
        "    … +29 lines (ctrl + t to view transcript)",
        "",
        "• The pre-revision static doctor is clean. I am taking the final",
        "  measurement now and will let the CLI re-run that guard atomically.",
        "",
        "◦ Working (14s • esc to interrupt)",
        "",
        "● Running 1 shell command · 12s…",
        "  ⎿  $ with-livespec-env.sh -- bd show livespec-dev-tooling-8sc1 (10s)",
        "",
        "· Roosting… (54s · ↓ 2.2k tokens)",
    )
)

# A variable whose name says it holds a busy/working verdict. Narrow on purpose:
# keying on "any variable assigned from a grep" would sweep in every unrelated
# probe a charter runs.
_BUSY_FLAG = re.compile(r"\b(?:is_)?(?:busy|working)\b\s*=", re.IGNORECASE)

# (m) The attended launch/restart contract must preserve both runtime idioms
# and the adoption identity they join. This is deliberately DOCUMENT-SCOPED:
# the contract is a section-level promise, not a shell spelling, and the
# generated shared protocol is the canonical place where it is emitted.
_ADOPTABLE_RUNTIME_HEADING = "## Adoptable runtime launch and restart"
_ADOPTABLE_RUNTIME_REQUIREMENTS = (
    "claude --dangerously-skip-permissions -n <topic>",
    "/rename <topic>",
    "signals.is_structured_gate",
    "numbered cursor",
    "permission question",
    'codex resume --dangerously-bypass-approvals-and-sandbox <session-id> "<kick>"',
    "session_index.jsonl",
    "thread_name",
    "tmux session name is not an adoption key",
    "daemon's own launch paths unchanged",
    "fuzzy matching",
    "tmux-name matching",
    "live killing",
    "blocking",
)


def adoptable_runtime_contract(*, text: str) -> list[str]:
    """Require the shared launch/restart contract when a charter declares it."""
    if _ADOPTABLE_RUNTIME_HEADING not in text:
        return []
    normalized = " ".join(text.split()).casefold()
    missing = [
        requirement
        for requirement in _ADOPTABLE_RUNTIME_REQUIREMENTS
        if (
            not re.search(
                r"daemon's own launch paths(?: \w+){0,2} unchanged",
                normalized,
            )
            if requirement == "daemon's own launch paths unchanged"
            else requirement.casefold() not in normalized
        )
    ]
    if not missing:
        return []
    return [f"missing required adoption rule(s): {', '.join(missing)}"]


# A `grep` call: its flag run, then its first quoted pattern argument.
_GREP_CALL = re.compile(r"\bgrep\b((?:[ \t]+-{1,2}[A-Za-z][A-Za-z-]*)*)[ \t]+('[^']*'|\"[^\"]*\")")
_TAIL_HEAD = re.compile(r"\b(tail|head)\b[ \t]+-(?:n[ \t]*)?(\d+)")

# POSIX bracket expressions are not Python regex. `[[:space:]]` must become
# `[\s]` or the pattern raises rather than matching, and a detector that raised
# on the fleet's most common busy test would be worse than one that missed it.
_POSIX_CLASS = re.compile(r"\[:(alpha|digit|alnum|space|blank|upper|lower|punct|xdigit):\]")
_POSIX_EXPANSION = {
    "alpha": "a-zA-Z",
    "digit": "0-9",
    "alnum": "a-zA-Z0-9",
    "space": r" \t\n\r\f\v",
    "blank": r" \t",
    "upper": "A-Z",
    "lower": "a-z",
    "punct": r"!-/:-@\[-`{-~",
    "xdigit": "0-9A-Fa-f",
}
# BRE spells the operators backwards from ERE: `\|` is alternation and a bare
# `|` is a literal pipe. Charters measured so far all use `-E`, but a `-E`-less
# grep read AS ERE would silently over-match, so the two are translated apart.
_BRE_ESCAPED_OP = re.compile(r"\\([|+?(){}])")
_BRE_BARE_OP = re.compile(r"(?<!\\)([|+?(){}])")


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


def unguarded_path_resolution(*, text: str) -> list[str]:
    """Path resolution with no non-empty guard in the preceding three lines.

    THE ATTRIBUTION HERE WAS BACKWARDS UNTIL 2026-07-30 and the correction is the
    reason this docstring is long. Measured on the developer host, whose
    `readlink` and `realpath` are BOTH uutils coreutils 0.2.2:

        readlink -f ""       rc=0, prints $PWD   -> FALSE PASS
        readlink -f -- ""    rc=0, prints $PWD   -> `--` does NOT save it
        realpath ""          rc=1                -> fails safe

    So the false pass is **uutils**, not GNU — GNU exits 1 and fails safe by
    accident. This module previously credited the false pass to GNU, which would
    have sent a reader to the wrong platform to reproduce it. The sibling
    `test_repo_containment_discriminates.py` had the mapping right all along;
    this file disagreed with it, and two files in one directory disagreeing about
    an environmental fact is how a wrong belief survives review.

    What saves the emitted charter form is therefore the NON-EMPTY GUARD, not the
    `--`. The `--` protects a leading-dash path, a different hazard.

    `realpath` is matched as well as `readlink -f`. Keying only on `readlink`
    would let an alternative spelling of the same operation evade the guard
    requirement entirely — the identical self-disarming shape that let defect
    (e)'s detector go blind the moment (f) was remediated. A detector must key on
    the ABSENCE OF THE GUARD, not on one spelling of the thing being guarded.
    """
    found: list[str] = []
    for block in _code_blocks(text=text):
        lines = block.splitlines()
        for index, line in enumerate(lines):
            if not _PATH_RESOLVE.search(line) or _is_comment(line=line):
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


def _empty_seeded_comparison_lines(*, block: str) -> list[str]:
    """Lines seeding EMPTY a var that a stability comparison then reads, any name.

    Returns the offending LINE rather than the variable name, so a finding from
    this rule is deduplicable against the literal-`prev` rule. Both rules describe
    the SAME defect when they both fire, and reporting it twice inflated the fleet
    exposure numbers by 2x on every affected charter — a count used to inform a
    maintainer decision, so the double-report was not merely untidy.
    """
    compared: set[str] = set()
    for match in _STABILITY_CMP.finditer(block):
        compared.update(match.groups())
    # The FULL line, in the same shape the literal rule reports, so the two are
    # dedupable by string. Reporting the bare regex match instead yields
    # `prev="";` where the literal rule yields `prev=""; stable=0`, and the
    # dedupe then silently does nothing.
    found: list[str] = []
    for line in block.splitlines():
        seed = _EMPTY_SEED.search(line)
        if seed is not None and seed.group(1) in compared:
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
        found.extend(_empty_seeded_comparison_lines(block=block))
    # DEDUPED BY LINE, order preserved. The literal rule and the property rule both
    # fire on `prev=""`, and that is ONE defect, not two. Keeping both rules is
    # deliberate — neither may narrow the other — but reporting both is not.
    return list(dict.fromkeys(found))


def bash_pipestatus_in_zsh_fleet(*, text: str) -> list[str]:
    """`PIPESTATUS` used in emitted code, which is silently empty under zsh."""
    found: list[str] = []
    for block in _code_blocks(text=text):
        for line in block.splitlines():
            if _is_comment(line=line):
                continue
            if _BASH_PIPESTATUS.search(line):
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


def wrapper_less_ledger_read(
    *, text: str, wrapper_tokens: frozenset[str] | None = None
) -> list[str]:
    """A `bd` invocation with no credential wrapper anywhere in the charter.

    Document-scoped like `supervisor_trusted_by_name`, not line-scoped, and for
    the same reason: the correct form is a `ledger_show()` helper that DETECTS the
    wrapper once and is called later by name, so a per-line rule would flag the
    correct call site.
    """
    blocks = _code_blocks(text=text)
    invocations = [
        raw.strip()
        for block in blocks
        for raw in block.splitlines()
        if _BD_INVOCATION.search(raw) and not _is_comment(line=raw)
    ]
    if not invocations:
        return []
    # CONTINUATION-JOINED, because a trailing backslash does not stop a wrapper
    # from wrapping. The live `beads-v1-1-2-upgrade` charter writes the correct
    # call as `with-livespec-env.sh -- \` + `  bd show ...`, which is the SAME
    # command as the one-liner and was scored as a defect purely because both
    # halves were required on one physical line.
    joined = "\n".join("\n".join(_logical_lines(block=block)) for block in blocks)
    # The wrapper THIS repo declares, whatever it is named. Resolved first,
    # because it is the only clause that survives a repo renaming its wrapper —
    # which `homelab` did, out of the `-env.sh` convention the pattern below
    # encodes and into a multi-element scoped-injection argv.
    tokens = declared_wrapper_tokens() if wrapper_tokens is None else wrapper_tokens
    if tokens and _declared_wrapper_wraps(joined=joined, tokens=tokens):
        return []
    if _WRAPPER_DETECTED.search(joined) or _WRAPPER_DIRECT.search(joined):
        return []
    # The variable form: the binding PROVED must be the binding CALLED.
    proved = {match.group(1) for match in _WRAPPER_VAR_DETECTED.finditer(joined)}
    invoked = {match.group(1) for match in _WRAPPER_VAR_INVOKED.finditer(joined)}
    if proved & invoked:
        return []
    return invocations


def fixed_cap_marker_read(*, text: str) -> list[str]:
    """A fixed-line-count marker read that never announces its own truncation."""
    blocks = _code_blocks(text=text)
    caps = [
        raw.strip()
        for block in blocks
        for raw in block.splitlines()
        if _FIXED_CAP_READ.search(raw) and not _is_comment(line=raw)
    ]
    if not caps:
        return []
    if _TRUNCATION_NOTICE.search("\n".join(blocks)):
        return []
    return caps


def unguarded_marker_binding(*, text: str) -> list[str]:
    """A `supervisor_marker` file test with no non-empty guard on the binding."""
    blocks = _code_blocks(text=text)
    tests = [
        raw.strip()
        for block in blocks
        for raw in block.splitlines()
        if _MARKER_FILE_TEST.search(raw) and not _is_comment(line=raw)
    ]
    if not tests:
        return []
    if _MARKER_NONEMPTY_GUARD.search("\n".join(blocks)):
        return []
    return tests


def _date_short_flags(*, token: str) -> str:
    """The leading short-flag letters of one `date` argument, `''` if it has none.

    Bundling and attached values are both in scope on purpose: `-ur`, `-ru` and
    `-r<file>` are all the same `-r`, and matching the exact token `-r` would be
    keying on a spelling — the failure mode that made (e) disarm itself when (f)
    was remediated. Long options return `''` here and are matched separately.
    """
    match = _DATE_SHORT_BUNDLE.match(token)
    return match.group(1) if match is not None else ""


def _claims_utc(*, token: str) -> bool:
    """Whether one `date` argument asserts that the printed time is UTC.

    A format argument counts, not just the flag: `date -r "$f" '+%FT%TZ'` labels
    local time `Z` without ever writing `-u`. `%Z` does NOT count — it prints the
    real zone name, which is the honest spelling this detector must leave alone.
    """
    if "u" in _date_short_flags(token=token) or _DATE_UTC_LONG.match(token):
        return True
    bare = token.strip("'\"")
    return bare.startswith("+") and _DATE_UTC_LABEL.search(bare) is not None


def local_time_labelled_utc(*, text: str) -> list[str]:
    """A `date` invocation that reads a FILE and still claims UTC (C19).

    Argument runs are cut at `;`, `|`, `&` and `)` so a later command's own `-r`
    cannot be read as this one's: `date -u '+%FT%TZ' && test -r "$f"` is clean.
    """
    found: list[str] = []
    for block in _code_blocks(text=text):
        for raw in block.splitlines():
            if _is_comment(line=raw):
                continue
            for args in _DATE_ARGS.findall(_strip_trailing_comment(line=raw)):
                tokens = _DATE_TOKEN.findall(args)
                reads_file = any(
                    "r" in _date_short_flags(token=token) or _DATE_FILE_LONG.match(token)
                    for token in tokens
                )
                if reads_file and any(_claims_utc(token=token) for token in tokens):
                    found.append(raw.strip())
                    break
    return found


def _logical_lines(*, block: str) -> list[str]:
    """Physical lines joined across trailing backslash continuations.

    A busy test routinely spans two physical lines — the fleet's corrected one
    does — so a per-physical-line reader would see a `grep -v` with no `grep`
    after it and draw the opposite conclusion.
    """
    joined: list[str] = []
    pending = ""
    for line in block.splitlines():
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        joined.append(pending + stripped)
        pending = ""
    if pending:
        joined.append(pending)
    return joined


def _pipeline_segments(*, line: str) -> list[str]:
    """Split a logical line on shell pipes, IGNORING pipes inside quotes.

    A naive `line.split("|")` tears every ERE alternation apart — and the busy
    patterns this detector exists to read are nothing BUT alternations, so the
    naive version silently found no grep at all and reported every charter clean.
    `||` is a control operator, not a pipe, and also ends a segment.
    """
    segments: list[str] = []
    current = ""
    quote: str | None = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote is not None:
            current += char
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
            current += char
        elif char == "|":
            segments.append(current)
            current = ""
            # `||` — skip the second pipe so it does not open an empty segment.
            if line[index + 1 : index + 2] == "|":
                index += 1
        else:
            current += char
        index += 1
    segments.append(current)
    return segments


def _posix_to_python(*, pattern: str, extended: bool) -> str:
    """Translate a POSIX grep pattern into Python regex source."""
    translated = _POSIX_CLASS.sub(lambda m: _POSIX_EXPANSION[m.group(1)], pattern)
    if extended:
        return translated
    # BRE: `\(` is a group and `(` is a literal, so both spellings flip.
    translated = _BRE_BARE_OP.sub(r"\\\1", translated)
    return _BRE_ESCAPED_OP.sub(r"\1", translated)


def _compiled_pattern(*, flags: str, quoted: str) -> re.Pattern[str] | None:
    """The Python equivalent of one grep pattern, or None if it cannot be read."""
    body = quoted[1:-1]
    fixed = "F" in flags or "--fixed-strings" in flags
    extended = "E" in flags or "--extended-regexp" in flags
    source = re.escape(body) if fixed else _posix_to_python(pattern=body, extended=extended)
    try:
        return re.compile(source)
    except re.error:
        # A pattern this module cannot parse is reported as no finding rather
        # than as a defect. Stated so the silence is a KNOWN floor: this
        # detector under-reports on exotic patterns, and never invents one.
        return None


def _segment_effect(*, segment: str, lines: list[str]) -> tuple[list[str], re.Pattern[str] | None]:
    """Apply one pipeline stage to the working line set.

    Returns the narrowed lines plus the pattern that DECIDES busy, if this stage
    is the deciding one. `grep -v` and `tail`/`head` only narrow.
    """
    narrowed = lines
    for verb, count in _TAIL_HEAD.findall(segment):
        n = int(count)
        narrowed = narrowed[-n:] if verb == "tail" else narrowed[:n]
    for flags, quoted in _GREP_CALL.findall(segment):
        compiled = _compiled_pattern(flags=flags, quoted=quoted)
        if compiled is None:
            continue
        if "v" in flags.replace("--", "") or "--invert-match" in flags:
            narrowed = [line for line in narrowed if not compiled.search(line)]
            continue
        return narrowed, compiled
    return narrowed, None


def _decides_busy(*, lines: list[str], index: int) -> bool:
    """Whether the grep on `lines[index]` is what sets the busy verdict.

    True when a busy-flag assignment sits on the same logical line, or within the
    two logical lines after it when the grep opens an `if`/`while`. That lookahead
    is the difference between catching the defect and being evaded by reformatting
    `... && busy=1` into a block body.
    """
    line = lines[index]
    if _BUSY_FLAG.search(line) is not None:
        return True
    opens_block = line.lstrip().startswith(("if ", "while ")) or line.rstrip().endswith(
        ("then", "do")
    )
    return opens_block and any(_BUSY_FLAG.search(nxt) for nxt in lines[index + 1 : index + 3])


def _busy_decisions(*, block: str, pane: str) -> list[tuple[str, re.Pattern[str], list[str]]]:
    """Each busy-deciding grep, with the pane lines still reaching it.

    The pipeline is walked left to right against `pane`, so `grep -v` exclusions
    and `tail`/`head` windows narrow the candidate lines exactly as the shell
    would before the deciding grep sees them.
    """
    found: list[tuple[str, re.Pattern[str], list[str]]] = []
    lines = _logical_lines(block=block)
    for index, line in enumerate(lines):
        if (
            _is_comment(line=line)
            or "grep" not in line
            or not _decides_busy(lines=lines, index=index)
        ):
            continue
        working = pane.splitlines()
        for segment in _pipeline_segments(line=line):
            working, decider = _segment_effect(segment=segment, lines=working)
            if decider is not None:
                found.append((line.strip(), decider, working))
                break
    return found


def _busy_match_patterns(*, block: str) -> list[tuple[str, re.Pattern[str]]]:
    """Every busy-deciding pattern in a block, with the line it came from."""
    return [
        (line, compiled)
        for line, compiled, _ in _busy_decisions(block=block, pane=_IDLE_PANE_RENDER)
    ]


def busy_test_matches_idle_pane(*, text: str) -> list[str]:
    """A watcher busy test that fires on an IDLE pane, so it can only say busy."""
    return [
        line
        for block in _code_blocks(text=text)
        for line, decider, reaching in _busy_decisions(block=block, pane=_IDLE_PANE_RENDER)
        if any(decider.search(candidate) for candidate in reaching)
    ]


_DETECTORS = (
    ("a-bare-tmux-target", bare_targets),
    ("b-unguarded-path-resolution", unguarded_path_resolution),
    ("c-history-fed-capture", history_fed_capture),
    ("d-empty-prev-watcher-init", empty_prev_watcher_init),
    ("e-supervisor-trusted-by-name", supervisor_trusted_by_name),
    ("f-regex-session-existence-test", regex_session_existence_test),
    ("g-bash-pipestatus-under-zsh", bash_pipestatus_in_zsh_fleet),
    ("h-wrapper-less-ledger-read", wrapper_less_ledger_read),
    ("i-fixed-cap-marker-read", fixed_cap_marker_read),
    ("j-unguarded-marker-binding", unguarded_marker_binding),
    ("k-local-time-labelled-utc", local_time_labelled_utc),
    ("l-busy-test-matches-idle-pane", busy_test_matches_idle_pane),
    ("m-adoptable-runtime-contract", adoptable_runtime_contract),
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
    the shared layer, which is deliberately WIDER than `_CHARTER_GLOBS`' two
    fixed depths -- a charter added at `plan/archive/<topic>/research/` would be
    unscanned today and this is what would say so. It does NOT look outside
    `plan/`, which correctly ignores the gitignored working copy at
    `tmp/<topic>-supervisor/supervisor-handoff.md` (measured: that is the only
    charter-shaped file outside the globs, and it is untracked scratch).

    Sabotage that reddens this: drop `plan/archive/*/supervisor-handoff.md` from
    `_CHARTER_GLOBS`, which removes four charters while leaving the set non-empty.
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
        "Widen _CHARTER_GLOBS rather than deleting this assertion -- an "
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
