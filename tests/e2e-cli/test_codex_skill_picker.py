"""Live Codex TUI `/skills` picker acceptance for the livespec-overseer plugin.

WHY THIS EXISTS. `.livespec.jsonc` declares `harnesses.codex.status = "supported"`.
The fleet Verifier (`livespec_dev_tooling.checks.plugin_resolution`) installs a
`DelegatedResolutionRunner` for codex that returns `available=False` -> SKIP, and
`_parse_supported` requires only that `canonical_command` be a NON-EMPTY STRING.
So without a repo-local check, that declaration is green-by-skip in both modes and
ANY string passes -- the "registration is not installation" failure rebuilt at the
gate layer. This test is the delegated live proof.

WHAT IT ASSERTS, AND WHY IT IS NOT THE TEMPLATE'S ASSERTION. It is ported from
`livespec-orchestrator-beads-fabro/tests/e2e-cli/test_codex_skill_picker.py`, whose
assertions are three independent substring tests against the rendered picker. That
shape is SOUND THERE and VACUOUS HERE: their skill is `drive` and their plugin is
`livespec-orchestrator-beads-fabro`, so the two strings are independent -- but our
skill name `overseer` is a SUBSTRING of our plugin name `livespec-overseer`, so
`_EXPECTED_SKILL in plain` would be satisfied by the plugin row alone, with no skill
row rendered at all. A copied-verbatim port would therefore have been green while
proving strictly less than it claims. We assert the composed ROW instead.

AND IT MAKES THE DECLARATION LOAD-BEARING. The plugin and skill names are not
hard-coded here: they are DERIVED from `harnesses.codex.canonical_command` in
`.livespec.jsonc`, parsed with the same vendored `jsoncomment` that
`plugin_resolution.py:326` uses on the same file. So the declaration and this check
cannot drift apart and both stay green -- editing `canonical_command` to any other
non-empty string (which the Verifier accepts) makes THIS check go red, because the
picker will not render a row for a skill that does not exist. That is the specific
hazard `overseer-kju6wh` was filed against.

WHAT IT DOES NOT PROVE, stated because this plan punishes unqualified live
claims: it proves the picker RENDERS the declared plugin/skill pair. It does not
invoke the skill, so it is not evidence that codex RESOLVES the bare
`livespec-overseer:overseer` at runtime the way `_command_surface_prompt`'s docstring
assumes ("codex name-selects the command verbatim") -- the picker's own insertion
form carries a `$` prefix. Invoking would run `overseer-start`, split panes and start
a daemon, which is not something a check may do. Note also that the SLASH-prefixed
`/livespec-overseer:overseer` is measured-invalid in a live Codex TUI ("Unrecognized
command"); that is a hand-verification hazard, not a declaration hazard, and it is
why the declared value is the bare form.
"""

from __future__ import annotations

import fcntl
import json
import os
import pty
import re
import select
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import termios
import time
import tty
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import livespec_dev_tooling
import pytest

_VENDOR_DIR = Path(livespec_dev_tooling.__file__).resolve().parent / "_vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

import jsoncomment  # noqa: E402  — vendor-path-aware import after sys.path insert.

__all__: list[str] = []

# A PER-TEST MARK, NOT A MODULE-LEVEL `pytestmark`, AND THE DIFFERENCE IS THE POINT.
# Only the LIVE picker exercise needs a codex binary and an authenticated host; the
# terminal-contract regression below is pure logic. A module-level mark would have
# skipped that regression everywhere except the one host that can run the live TUI —
# i.e. it would be absent from exactly the ordinary `just check` runs that are supposed
# to notice the contract breaking again.
_LIVE_CODEX_PICKER_ONLY = pytest.mark.skipif(
    os.environ.get("LIVESPEC_CODEX_SKILL_PICKER") != "1",
    reason="live Codex TUI picker acceptance runs only via just check-codex-skill-picker",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FOREGROUND_QUERY = "\x1b]10;?\x1b\\"
_BACKGROUND_QUERY = "\x1b]11;?\x1b\\"
_FOREGROUND_RESPONSE = "\x1b]10;rgb:ffff/ffff/ffff\x1b\\"
_BACKGROUND_RESPONSE = "\x1b]11;rgb:0000/0000/0000\x1b\\"
_TERMINAL_RESPONSES = _FOREGROUND_RESPONSE + _BACKGROUND_RESPONSE
# PROGRESS-ORDERED WAITS, NOT WALL-CLOCK BUDGETS (overseer-zgik5v / overseer-i6yp).
# Every wait below lasts for as long as the Codex TUI keeps writing to its pty, and
# gives up only when the TUI has written NOTHING for the phase's stall window, or when
# the whole exercise passes `_CODEX_EXERCISE_CEILING_SECONDS`. A loaded host makes
# Codex start slowly but it keeps rendering while it does, so slowness extends the wait
# instead of failing it. The stall windows are the only budgets that can fail an
# unloaded host, and they fail it quickly when the picker never renders the row.
#
# The stall windows are measured against the longest silent gap observed on this host
# unloaded (about 6.5 s between Codex's first frame and its model line, 2026-11-03),
# not against how long a phase takes. The ceiling is the single liveness bound.
_CODEX_STARTUP_STALL_SECONDS = 120.0
_CODEX_PICKER_STALL_SECONDS = 60.0
_CODEX_SETTLE_QUIET_SECONDS = 6.0
_CODEX_EXERCISE_CEILING_SECONDS = 600.0
_CODEX_PROMPT_MARKER = chr(0x203A)
# The mentions list `@` opens draws this header before it filters rows.
_PICKER_OPEN_MARKER = "Mentions"
_GIT_HOOK_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)
_HOST_CODEX_HOME = Path.home() / ".codex"
_FALLBACK_TERM = "xterm-256color"
_CODEX_TEST_MODEL = "gpt-5.6-sol"
# TERMINAL TYPES THAT CANNOT DRIVE A TUI, distinguished from a MISSING one because
# conflating the two is the bug this set was added to close. See `_tui_capable_term`.
_TUI_INCAPABLE_TERMS = frozenset({"", "dumb"})

# The materialized plugin tree this run reads. Defaults to the host's, which is what
# the check asserts in normal operation.
#
# THE OVERRIDE EXISTS SO THE RED DEMONSTRATION CAN RUN AGAINST THIS EXACT CHECK.
# This slice's acceptance is "demonstrated RED by REMOVING THE SURFACE and showing
# the check FAILS", and a green that cannot go red is not evidence. Removing the
# surface from the HOST tree would prune a cache that live Codex sessions on this
# host are using, which this plan forbids. So the demo points this at a
# scratch copy with `.codex-plugin/skills/<skill>/` deleted, and the check fails
# there while the host tree is never touched. Without the seam the RED demo would
# have to be run against a hand-built REPLICA of the assertion path, which proves
# something about the replica rather than about the shipped check.
_PLUGINS_ROOT = Path(
    os.environ.get("LIVESPEC_CODEX_PLUGINS_ROOT", str(_HOST_CODEX_HOME / "plugins"))
)

# THE PLUGIN THIS ACCEPTANCE IS ABOUT, AND NOTHING ELSE. The host plugin root is a
# SHARED, MULTI-TENANT tree: whatever the operator has installed lives beside ours
# under `cache/<marketplace>/<plugin>/<version>`. `_CODEX_PLUGIN_KEY` is the
# `<plugin>@<marketplace>` form Codex's own `[plugins.*]` config table uses, and
# `_DECLARED_PLUGIN_NAMES` is the pair of directory names that belong to us.
_CODEX_PLUGIN_CACHE_DIR = "cache"
_CODEX_MARKETPLACE = "livespec-overseer"
_CODEX_PLUGIN = "livespec-overseer"
_CODEX_PLUGIN_KEY = f"{_CODEX_PLUGIN}@{_CODEX_MARKETPLACE}"
_DECLARED_PLUGIN_NAMES = frozenset({_CODEX_MARKETPLACE, _CODEX_PLUGIN})
# How deep the pruning mirror walks before it symlinks a subtree wholesale: enough
# to reach `cache/<marketplace>/<plugin>` and link THAT, so the declared plugin's
# own materialized versions are never copied or re-walked.
_PLUGIN_MIRROR_DEPTH = 2
_HOST_CODEX_HOME_FILES = ("auth.json", ".credentials.json", "installation_id")

# DELIBERATELY NO `[marketplaces.*]` BLOCK — this omission is load-bearing and was
# arrived at by measurement, not by taste.
#
# The template this is ported from declares its marketplaces here. Doing the same
# was tried and REBUILT THE SHARED PLUGIN CACHE: the real
# `~/.codex/plugins/cache/livespec-overseer/livespec-overseer` is SYMLINKED into the
# scratch home (see `_mirror_declared_plugin_only`), so a declared marketplace makes
# codex re-fetch and re-materialize it — observed as fresh inodes on two consecutive
# runs. That is precisely the prune this plan warns breaks live Codex sessions on
# this host, and a check that fires on every `just check` must not do it.
#
# Mirroring the host's `last_updated`/`last_revision` state keys did NOT prevent it:
# the host pin is `ref = "master"`, a MOVING ref, so codex re-syncs whenever master
# has advanced past the recorded revision. Omitting the block entirely leaves the
# already-materialized cache untouched — verified by comparing cache inodes before
# and after a run, where `livespec-overseer` was byte-stable while only unrelated
# `openai-curated-remote` state churned (that churns on any codex start).
#
# What this means for what the test proves: it reads the surface the HOST has
# already materialized, at whatever ref the host registered — currently the declared
# `--ref master` deviation (this thread's, retiring when release PR #360 merges).
# The test therefore asserts the INSTALLED surface renders, which is the claim
# `harnesses.codex.status = "supported"` actually makes. It is not a test that a
# fresh clone can register the marketplace from scratch.
_CODEX_TEST_CONFIG = f"""
model = "{_CODEX_TEST_MODEL}"

[tui.model_availability_nux]
"{_CODEX_TEST_MODEL}" = 4

[notice.model_migrations]
"gpt-5.5" = "{_CODEX_TEST_MODEL}"

[projects."{_REPO_ROOT}"]
trust_level = "trusted"

[plugins."{_CODEX_PLUGIN_KEY}"]
enabled = true
"""


def _declared_codex_command(*, repo_root: Path) -> tuple[str, str]:
    """Return `(plugin, skill)` parsed from the declared codex `canonical_command`.

    Parsed with the SAME vendored `jsoncomment` the fleet Verifier uses on this
    file (`plugin_resolution.py:326`), so this check reads exactly what the gate
    reads. Deriving rather than hard-coding is what stops the declaration and this
    check drifting apart while both stay green.
    """
    config_path = repo_root / ".livespec.jsonc"
    parsed = jsoncomment.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        pytest.fail(f"{config_path} did not parse to an object")
    harnesses = parsed.get("harnesses")
    if not isinstance(harnesses, dict):
        pytest.fail(f"{config_path} carries no `harnesses` object")
    codex = harnesses.get("codex")
    if not isinstance(codex, dict):
        pytest.fail(f"{config_path} carries no `harnesses.codex` object")
    if codex.get("status") != "supported":
        pytest.fail(
            "harnesses.codex.status is not 'supported'; this live picker acceptance "
            "exists to back that specific claim and must not pass while it is absent"
        )
    command = codex.get("canonical_command")
    if not isinstance(command, str) or command.count(":") != 1:
        pytest.fail(
            "harnesses.codex.canonical_command must be a bare `<plugin>:<skill>` string "
            f"(the checker supplies the harness sigil); got {command!r}"
        )
    plugin, _, skill = command.partition(":")
    if not plugin or not skill:
        pytest.fail(f"harnesses.codex.canonical_command has an empty half: {command!r}")
    return plugin, skill


@dataclass(kw_only=True)
class _Screen:
    """The small ANSI terminal model needed to render Codex's 40x120 pty."""

    rows: list[list[str]] = field(default_factory=lambda: [[" "] * 120 for _ in range(40)])
    row: int = 0
    column: int = 0
    saved_row: int = 0
    saved_column: int = 0

    def render(self) -> str:
        return "\n".join("".join(line).rstrip() for line in self.rows).strip()

    def write(self, *, text: str) -> None:
        index = 0
        while index < len(text):
            character = text[index]
            if character == "\x1b" and index + 1 < len(text):
                index = self._consume_escape(text=text, index=index)
                continue
            if character == "\r":
                self.column = 0
            elif character == "\n":
                self.row = min(39, self.row + 1)
            elif character == "\b":
                self.column = max(0, self.column - 1)
            elif character >= " ":
                self.rows[self.row][self.column] = character
                self.column = min(119, self.column + 1)
            index += 1

    def _consume_escape(self, *, text: str, index: int) -> int:
        introducer = text[index + 1]
        if introducer == "[":
            return self._consume_csi(text=text, index=index)
        if introducer == "]":
            return self._consume_osc(text=text, index=index)
        if introducer == "7":
            self.saved_row, self.saved_column = self.row, self.column
        elif introducer == "8":
            self.row, self.column = self.saved_row, self.saved_column
        return index + 2

    def _consume_osc(self, *, text: str, index: int) -> int:
        bell = text.find("\x07", index + 2)
        string_terminator = text.find("\x1b\\", index + 2)
        endings = [ending for ending in (bell, string_terminator) if ending >= 0]
        if not endings:
            return len(text)
        ending = min(endings)
        return ending + (2 if ending == string_terminator else 1)

    def _consume_csi(self, *, text: str, index: int) -> int:
        end = index + 2
        while end < len(text) and not ("@" <= text[end] <= "~"):
            end += 1
        if end == len(text):
            return end
        parameters = text[index + 2 : end].lstrip("?>")
        values = [int(value) if value else 0 for value in parameters.split(";")]
        handler = {
            "H": self._position,
            "f": self._position,
            "A": self._up,
            "B": self._down,
            "C": self._right,
            "D": self._left,
            "G": self._column,
            "d": self._row,
            "J": self._erase_display,
            "K": self._erase_line,
            "s": self._save_cursor,
            "u": self._restore_cursor,
        }.get(text[end])
        if handler is not None:
            handler(values=values)
        return end + 1

    def _position(self, *, values: list[int]) -> None:
        self._row(values=values)
        self._column(values=values[1:])

    def _up(self, *, values: list[int]) -> None:
        self.row = max(0, self.row - (values[0] or 1))

    def _down(self, *, values: list[int]) -> None:
        self.row = min(39, self.row + (values[0] or 1))

    def _right(self, *, values: list[int]) -> None:
        self.column = min(119, self.column + (values[0] or 1))

    def _left(self, *, values: list[int]) -> None:
        self.column = max(0, self.column - (values[0] or 1))

    def _column(self, *, values: list[int]) -> None:
        self.column = min(119, max(0, (values[0] if values else 1) - 1))

    def _row(self, *, values: list[int]) -> None:
        self.row = min(39, max(0, (values[0] if values else 1) - 1))

    def _erase_display(self, *, values: list[int]) -> None:
        if not values or values[0] in {2, 3}:
            self.rows = [[" "] * 120 for _ in range(40)]

    def _erase_line(self, *, values: list[int]) -> None:
        mode = values[0] if values else 0
        start, stop = (
            (0, 120) if mode == 2 else (0, self.column + 1) if mode == 1 else (self.column, 120)
        )
        self.rows[self.row][start:stop] = [" "] * (stop - start)

    def _save_cursor(self, *, values: list[int]) -> None:
        self.saved_row, self.saved_column = self.row, self.column

    def _restore_cursor(self, *, values: list[int]) -> None:
        self.row, self.column = self.saved_row, self.saved_column


def _plain(*, text: str) -> str:
    """Render Codex's cursor-addressed pty stream into the screen it displays."""
    screen = _Screen()
    screen.write(text=text)
    return screen.render()


def _escaped(*, text: str) -> str:
    """The RAW pty bytes with escape sequences rendered visibly.

    WHY A STALL NEEDS THIS BESIDE THE RENDERED TAIL. `_plain` strips escape
    sequences, which is right for asserting on content and wrong for diagnosing a
    stall: the release-host failure of `overseer-twtw55` reported an EMPTY
    `Last output:` because everything codex had emitted was escape sequences, and an
    UNANSWERED terminal query — a cursor-position report, a device-attributes
    request, a keyboard-protocol probe — is by construction invisible once stripped.
    `_answer_terminal_queries` answers only the two OSC colour queries, so any other
    query codex learns to send would stall startup with nothing on screen to say so.
    Rendering the raw stream makes the next such stall readable instead of blank.
    """
    return text.encode("unicode_escape").decode("ascii")


def _squashed(*, text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _has_main_prompt(*, plain: str) -> bool:
    return not _has_trust_prompt(plain=plain) and any(
        line.lstrip().startswith(_CODEX_PROMPT_MARKER) for line in plain.splitlines()
    )


def _has_trust_prompt(*, plain: str) -> bool:
    return "doyoutrust" in _squashed(text=plain)


def _tui_capable_term(*, inherited: str | None) -> str:
    """Return the `TERM` the spawned Codex gets, given whatever the caller exported.

    THE PTY IS OURS, SO THE TERMINAL CONTRACT IS OURS TO STATE. This test builds its
    own 40x120 pseudoterminal and answers codex's OSC colour queries itself, so the
    terminal codex talks to is a known, fully capable one regardless of what the
    INVOKER happened to be attached to. Passing the invoker's `TERM` through therefore
    describes the wrong terminal.

    THE BUG THIS FIXES (`overseer-m7jty7`). The previous expression was
    `env.get("TERM", "xterm-256color")` — a fallback for ABSENCE only. lefthook runs
    its commands with `TERM=dumb`, which is PRESENT, so the fallback never fired;
    codex saw a terminal it cannot render into, stopped at its terminal warning, and
    `_open_skills_list` timed out waiting for a `/skills` row that was never going to
    appear. Every other target in the same pre-push aggregate passed. The gate thus
    MEANT DIFFERENT THINGS depending on who invoked it: red under lefthook, green from
    an interactive shell running the identical command. A gate whose verdict tracks its
    caller's environment is not evidence about the surface it claims to check.

    `dumb` is the value POSIX reserves for "no capabilities", and an empty `TERM` is
    the same statement spelled differently; both are replaced. A caller-supplied
    CAPABLE value is passed through untouched, so a `screen-256color` or `tmux-256color`
    invoker still exercises its own terminal type rather than a substituted one.

    NOTE WHAT THIS DOES NOT DO: it does not weaken, skip or soften the live picker
    assertion. The assertion is unchanged — only the environment it runs against stops
    varying by caller.
    """
    if inherited is None or inherited in _TUI_INCAPABLE_TERMS:
        return _FALLBACK_TERM
    return inherited


def _prepare_pty(*, master_fd: int, slave_fd: int) -> None:
    tty.setraw(slave_fd)
    winsize = struct.pack("HHHH", 40, 120, 0, 0)
    termios.tcflush(slave_fd, termios.TCIOFLUSH)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)


def _answer_terminal_queries(*, fd: int, current: str, answered: dict[str, int]) -> None:
    """Answer codex's foreground/background colour queries.

    SCANS THE ACCUMULATED STREAM, NOT THE LATEST CHUNK, AND THIS IS THE WHOLE BUG
    THIS FUNCTION EXISTS TO FIX. The template tests `if _FOREGROUND_QUERY in chunk`.
    An OSC query is ~8 bytes and nothing guarantees it lands inside one `os.read`;
    when it straddles a chunk boundary the substring test never matches, codex never
    receives its colour response, and it falls back to a degraded renderer that
    emits ONE GLYPH PER LINE. The assertion then fails against a transcript that
    contains every expected word spelled down the screen a character at a time.

    That is LOAD-DEPENDENT, because load is what changes where chunk boundaries
    fall: measured here passing standalone and failing inside the full ~66-target
    `just check` aggregate, with the pty verifiably 40x120 and `TERM`/`COLUMNS`
    identical in both. Diagnosing it cost three wrong hypotheses — terminal width,
    `TERM`, and a quiet-window race — each of which had a plausible story and none
    of which survived measurement.

    Counting rather than flagging keeps it correct when codex asks more than once.
    """
    for query, response in (
        (_FOREGROUND_QUERY, _FOREGROUND_RESPONSE),
        (_BACKGROUND_QUERY, _BACKGROUND_RESPONSE),
    ):
        while answered.get(query, 0) < current.count(query):
            _send(fd=fd, text=response)
            answered[query] = answered.get(query, 0) + 1


@dataclass(kw_only=True)
class _Exercise:
    """One picker exercise's shared state: the pty, its answered queries, its ceiling.

    `started` is when the exercise began, so every phase is held to ONE overall
    ceiling rather than each phase getting a fresh budget of its own.
    """

    fd: int
    ceiling_seconds: float = _CODEX_EXERCISE_CEILING_SECONDS
    started: float = field(default_factory=time.monotonic)
    answered: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class _Read:
    """One read window's outcome: the rendered transcript, and whether it grew."""

    plain: str
    produced: bool


def _host_load() -> str:
    one, five, fifteen = os.getloadavg()
    return f"{one:.2f} {five:.2f} {fifteen:.2f} (1/5/15 min) on {os.cpu_count()} CPUs"


def _wait_expired(
    *, exercise: _Exercise, phase: str, why: str, phase_started: float, current: str
) -> AssertionError:
    """The failure for an expired wait: which wait, how long, against what, under what load."""
    now = time.monotonic()
    tail = _plain(text=current)[-3000:]
    return AssertionError(
        f"Timed out waiting for Codex picker state: the {phase} wait expired because {why}. "
        f"Phase elapsed {now - phase_started:.1f}s; exercise elapsed "
        f"{now - exercise.started:.1f}s of {exercise.ceiling_seconds:g}s allowed. "
        f"Host load average at expiry: {_host_load()}.\n"
        f"Last rendered screen:\n{tail}\n\n"
        f"Raw pty tail, escapes visible:\n{_escaped(text=current[-_RAW_TAIL_CHARS:])}"
    )


def _pump(
    *,
    exercise: _Exercise,
    phase: str,
    seen: str,
    done: Callable[[_Read], bool],
    stall_seconds: float,
) -> str:
    """Read the pty until `done` holds for a read window; raise a named expiry otherwise.

    `_Read.produced` is whether that window brought new output. The wait is extended
    by every byte Codex writes: it expires only after `stall_seconds` of silence, or
    when the exercise's overall ceiling passes.
    """
    phase_started = time.monotonic()
    ceiling = exercise.started + exercise.ceiling_seconds
    stall_deadline = phase_started + stall_seconds
    current = seen
    while True:
        now = time.monotonic()
        if now >= ceiling:
            why = f"the whole exercise reached its {exercise.ceiling_seconds:g}s ceiling"
            raise _wait_expired(
                exercise=exercise,
                phase=phase,
                why=why,
                phase_started=phase_started,
                current=current,
            )
        if now >= stall_deadline:
            why = f"the Codex TUI wrote nothing for {stall_seconds:g}s"
            raise _wait_expired(
                exercise=exercise,
                phase=phase,
                why=why,
                phase_started=phase_started,
                current=current,
            )
        window = max(0.05, min(0.25, ceiling - now, stall_deadline - now))
        readable, _, _ = select.select([exercise.fd], [], [], window)
        produced = bool(readable)
        if produced:
            try:
                chunk = os.read(exercise.fd, 8192).decode("utf-8", errors="replace")
            except OSError as exc:
                tail = _plain(text=current)[-3000:]
                raise AssertionError(
                    f"Codex TUI exited during the {phase} wait. Last output:\n{tail}"
                ) from exc
            current += chunk
            stall_deadline = time.monotonic() + stall_seconds
            _answer_terminal_queries(fd=exercise.fd, current=current, answered=exercise.answered)
        if done(_Read(plain=_plain(text=current), produced=produced)):
            return current


def _read_until(
    *,
    exercise: _Exercise,
    phase: str,
    seen: str,
    predicate: Callable[[str], bool],
    stall_seconds: float,
) -> str:
    return _pump(
        exercise=exercise,
        phase=phase,
        seen=seen,
        done=lambda read: predicate(read.plain),
        stall_seconds=stall_seconds,
    )


def _read_until_quiet(*, exercise: _Exercise, seen: str, quiet_seconds: float) -> str:
    """Return once Codex has been silent for `quiet_seconds`; silence here is SUCCESS.

    So there is no stall window to expire: only the exercise ceiling bounds a TUI that
    never stops redrawing.
    """
    quiet_since = [time.monotonic()]

    def settled(read: _Read) -> bool:
        if read.produced:
            quiet_since[0] = time.monotonic()
            return False
        return time.monotonic() - quiet_since[0] >= quiet_seconds

    return _pump(
        exercise=exercise,
        phase="startup",
        seen=seen,
        done=settled,
        stall_seconds=exercise.ceiling_seconds,
    )


def _send(*, fd: int, text: str) -> None:
    os.write(fd, text.encode("utf-8"))


def _foreign_plugin_names(*, plugins_root: Path) -> frozenset[str]:
    """Every marketplace and plugin name the host has materialized EXCEPT ours.

    Read off the cache tree rather than off a registry, because the cache is the
    thing that actually exists: a plugin materialized under
    `cache/<marketplace>/<plugin>` is a plugin Codex can start whether or not any
    registry still records it, and the inverse (a registry entry with no cache) is
    inert. Enumerating from the tree therefore cannot miss a tenant.
    """
    cache = plugins_root / _CODEX_PLUGIN_CACHE_DIR
    if not cache.is_dir():
        return frozenset()
    names = {entry.name for entry in cache.iterdir() if entry.is_dir()}
    for marketplace in cache.iterdir():
        if marketplace.is_dir():
            names.update(entry.name for entry in marketplace.iterdir() if entry.is_dir())
    return frozenset(names - _DECLARED_PLUGIN_NAMES)


def _names_a_foreign_plugin(*, name: str, foreign: frozenset[str]) -> bool:
    """Whether one directory, file, or registry-key name belongs to another tenant.

    Split on `@` so BOTH spellings are caught: a bare cache directory name and the
    `<plugin>@<marketplace>` key Codex's registries and config table use.
    """
    return any(part in foreign for part in name.split("@"))


def _without_foreign_entries(*, value: object, foreign: frozenset[str]) -> object:
    """One parsed registry value with every foreign-named mapping entry removed."""
    if isinstance(value, dict):
        return {
            key: _without_foreign_entries(value=entry, foreign=foreign)
            for key, entry in value.items()
            if not (isinstance(key, str) and _names_a_foreign_plugin(name=key, foreign=foreign))
        }
    if isinstance(value, list):
        return [_without_foreign_entries(value=entry, foreign=foreign) for entry in value]
    return value


def _pruned_registry(*, path: Path, foreign: frozenset[str]) -> str | None:
    """`path`'s JSON with foreign entries dropped, or `None` when it cannot be read.

    `None` is the FAIL-CLOSED answer, and it is deliberately not an empty object: a
    registry this function cannot parse is a registry whose contents it cannot vouch
    for, so the home is built WITHOUT it rather than with something unfiltered.
    Carrying the parseable ones pruned — rather than dropping every registry — is
    what keeps OUR plugin's own registration intact, which is the surface the live
    picker assertion needs.
    """
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return json.dumps(_without_foreign_entries(value=parsed, foreign=foreign), indent=2)


def _mirror_declared_plugin_only(
    *, source: Path, destination: Path, foreign: frozenset[str], depth: int
) -> None:
    """Mirror `source` into `destination`, admitting only the declared plugin.

    A PRUNING MIRROR RATHER THAN A SYMLINK OF THE WHOLE ROOT, which is the fix for
    `overseer-kq7tkw`. Each level becomes a REAL directory holding only the entries
    that are not another tenant's, so the shared host tree is read without being
    re-materialized (the hazard the `[marketplaces.*]` omission above was measured
    against) and without being exposed.

    `depth` bounds the walk: at zero a kept directory is symlinked WHOLESALE, so
    `cache/<marketplace>/<plugin>` — every version of our own plugin — is linked in
    one step rather than walked. Walking into it would be pointless work and would
    put this function in the business of mirroring plugin internals.
    """
    destination.mkdir(parents=True, exist_ok=True)
    if not source.is_dir():
        # An absent host plugin root used to leave a DANGLING symlink here, which let
        # the run reach the picker assertion and fail with its own diagnostic about a
        # surface that does not exist. Returning an empty mirror preserves exactly
        # that failure, rather than replacing it with an opaque FileNotFoundError
        # from inside the mirror.
        return
    for entry in sorted(source.iterdir()):
        if _names_a_foreign_plugin(name=entry.name, foreign=foreign):
            continue
        target = destination / entry.name
        if entry.is_file() and entry.suffix == ".json":
            pruned = _pruned_registry(path=entry, foreign=foreign)
            if pruned is not None:
                target.write_text(pruned, encoding="utf-8")
        elif entry.is_dir() and depth > 0:
            _mirror_declared_plugin_only(
                source=entry, destination=target, foreign=foreign, depth=depth - 1
            )
        else:
            os.symlink(entry, target)


def _prepare_codex_home(
    *,
    codex_home: Path,
    plugins_root: Path = _PLUGINS_ROOT,
    host_home: Path = _HOST_CODEX_HOME,
) -> None:
    """Build the scratch Codex home the live exercise runs against.

    `plugins_root` and `host_home` default to the real host's, which is what the
    live acceptance reads; they are parameters so the exposure contract above can be
    proved HERMETICALLY against a stand-in host tree. Without the seam the only way
    to measure what this home exposes would be to measure the operator's own
    `~/.codex`, which makes the answer depend on what they happen to have installed
    — the very coupling this function exists to remove.
    """
    (codex_home / "config.toml").write_text(_CODEX_TEST_CONFIG, encoding="utf-8")
    _mirror_declared_plugin_only(
        source=plugins_root,
        destination=codex_home / "plugins",
        foreign=_foreign_plugin_names(plugins_root=plugins_root),
        depth=_PLUGIN_MIRROR_DEPTH,
    )
    for filename in _HOST_CODEX_HOME_FILES:
        source = host_home / filename
        if source.exists():
            os.symlink(source, codex_home / filename)


# WHY A STALL CARRIES CODEX'S OWN LOG. On the release host this acceptance stalls
# intermittently at startup (overseer-twtw55: 2 of 10 runs on 2026-10-22), and the
# rendered tail held only "⚠ 2 warnings" -- the TUI's collapsed count, never the
# warnings themselves. Codex writes them to `logs_2.sqlite` in its OWN home, which is
# this test's temporary directory and is deleted on exit, so the cause was destroyed
# with the evidence. The digest is read before that cleanup: every WARN/ERROR row in
# full, plus the last rows of any level, which name what startup was waiting on.
def _codex_tui_env(*, inherited: Mapping[str, str]) -> dict[str, str]:
    """The spawned Codex's environment: a capable 40x120 terminal, no git-hook state."""
    env = dict(inherited)
    env["TERM"] = _tui_capable_term(inherited=env.get("TERM"))
    env["COLUMNS"] = "120"
    env["LINES"] = "40"
    env["NO_COLOR"] = "1"
    for name in _GIT_HOOK_ENV_VARS:
        env.pop(name, None)
    return env


_CODEX_LOG_DB = "logs_2.sqlite"
_CODEX_LOG_TAIL_ROWS = 25
# How much of the raw pty stream a picker-state stall reports. Escaped rendering is
# several times longer than the bytes it describes, so this is deliberately well
# under the 3000 characters of rendered tail it sits beside.
_RAW_TAIL_CHARS = 1200


def _codex_log_digest(*, codex_home: Path) -> str:
    """Codex's own startup log from `codex_home`, or a line saying why it is absent."""
    database = codex_home / _CODEX_LOG_DB
    if not database.exists():
        return f"(no Codex log: {database} does not exist)"
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            problems = connection.execute(
                "SELECT ts, level, target, feedback_log_body FROM logs"
                " WHERE level IN ('WARN', 'ERROR') ORDER BY id"
            ).fetchall()
            last = connection.execute(
                "SELECT ts, level, target, feedback_log_body FROM logs ORDER BY id DESC LIMIT ?",
                (_CODEX_LOG_TAIL_ROWS,),
            ).fetchall()
    except sqlite3.Error as exc:
        return f"(Codex log unreadable: {database}: {exc})"
    lines = [f"Codex WARN/ERROR log rows ({len(problems)}):"]
    lines.extend(f"  {ts} {level} {target}: {body}" for ts, level, target, body in problems)
    lines.append(f"Codex last {len(last)} log rows, oldest first:")
    lines.extend(f"  {ts} {level} {target}: {body}" for ts, level, target, body in reversed(last))
    return "\n".join(lines)


def _await_codex_prompt(*, exercise: _Exercise, transcript: str) -> str:
    current = _read_until(
        exercise=exercise,
        phase="startup",
        seen=transcript,
        predicate=lambda plain: _has_main_prompt(plain=plain) or _has_trust_prompt(plain=plain),
        stall_seconds=_CODEX_STARTUP_STALL_SECONDS,
    )
    if _has_trust_prompt(plain=_plain(text=current)):
        _send(fd=exercise.fd, text="\r")
        current = _read_until(
            exercise=exercise,
            phase="startup",
            seen=current,
            predicate=lambda plain: _has_main_prompt(plain=plain),
            stall_seconds=_CODEX_STARTUP_STALL_SECONDS,
        )
    return _read_until_quiet(
        exercise=exercise, seen=current, quiet_seconds=_CODEX_SETTLE_QUIET_SECONDS
    )


def _open_skills_list(
    *, exercise: _Exercise, transcript: str, query: str, expected_row: str
) -> str:
    """Open the skills list directly with `@` and filter it by `query`.

    THE TEMPLATE'S TWO-STEP NAVIGATION WAS PORTED FIRST AND IT RACED. It sends
    `/skills`, waits for the action menu, sends Enter to choose "List skills", then
    waits on `"Skills" in plain or "Search" in plain` before typing. That predicate
    tests the WHOLE ACCUMULATED transcript, and the action menu it just waited for
    already contains the word "Skills" — so the wait returns instantly, the query is
    typed before the list view exists, and the keystrokes land in the composer. The
    observed failure was a composer reading `lls@...overseer` with no rows rendered
    at all: a stale-substring match, the same "correct about its own inputs, wrong
    about the world" shape this plan keeps hitting.

    `@` reaches the SAME list in one step — the action menu's own tip says so
    ("Tip: press @ to open this list directly") — which removes the intermediate
    state that could be matched stale. `\\x15` (Ctrl-U) clears the composer first so
    a leftover keystroke cannot corrupt the filter.

    WAITS ON CONTENT, NOT ON QUIET, AND THAT DISTINCTION IS LOAD-BEARING. An earlier
    revision settled for "2s with no output" and PASSED standalone while FAILING
    inside the full `just check` aggregate: under the load of ~66 targets a 2s gap
    opens before the picker has filtered, so the transcript gets asserted mid-render.
    A quiet window measures the HOST, not the UI. Waiting for the expected row
    instead returns as soon as it renders, and gives up only when Codex has stopped
    writing for a whole stall window or the exercise ceiling passes, so a slow host
    costs seconds rather than a false red. This repo carries a P1 about a
    check aggregate that is flaky under concurrency (`overseer-jdo`); adding another
    load-sensitive gate to it would have been the same defect, self-inflicted.
    """
    _send(fd=exercise.fd, text="\x15@" + query)
    before = _plain(text=transcript)
    # Picker OPEN: the rendered mentions list has changed after the keystrokes.
    # `plain` is a terminal-screen redraw, not an append-only stream, so neither an
    # offset into `before` nor whether a marker was already present identifies what
    # Codex drew after input.
    opened = _read_until(
        exercise=exercise,
        phase="picker open",
        seen=transcript,
        predicate=lambda plain: plain != before
        and any(marker in plain for marker in (_PICKER_OPEN_MARKER, expected_row)),
        stall_seconds=_CODEX_PICKER_STALL_SECONDS,
    )
    return _read_until(
        exercise=exercise,
        phase="picker render",
        seen=opened,
        predicate=lambda plain: expected_row in plain and "Skill" in plain,
        stall_seconds=_CODEX_PICKER_STALL_SECONDS,
    )


def _stop_codex(*, proc: subprocess.Popen[bytes], fd: int) -> None:
    if proc.poll() is None:
        try:
            _send(fd=fd, text="\x03")
            _send(fd=fd, text="/quit\r")
            proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    os.close(fd)


def _skill_row(*, plugin: str, skill: str) -> str:
    """The picker's rendered skill row, e.g. `overseer (livespec-overseer)`.

    Asserting the COMPOSED row rather than the two names separately is what keeps
    this check non-vacuous when the skill name is a substring of the plugin name,
    which is exactly our case.
    """
    return f"{skill} ({plugin})"


def _exercise_skills_picker(*, master_fd: int, plugin: str, skill: str) -> str:
    # One tally for the whole exercise: the colour queries are counted against the
    # accumulated stream, so the count of answers-already-sent has to persist across
    # every pump call rather than reset per call.
    exercise = _Exercise(fd=master_fd)
    _send(fd=master_fd, text=_TERMINAL_RESPONSES)
    transcript = _await_codex_prompt(exercise=exercise, transcript="")
    return _open_skills_list(
        exercise=exercise,
        transcript=transcript,
        query=f"{plugin}:{skill}",
        expected_row=_skill_row(plugin=plugin, skill=skill),
    )


@pytest.mark.parametrize("inherited", [None, "", "dumb"])
def test_a_tui_incapable_caller_terminal_is_replaced_for_the_spawned_codex(inherited) -> None:
    assert _tui_capable_term(inherited=inherited) == _FALLBACK_TERM


@pytest.mark.parametrize("inherited", ["xterm-256color", "screen-256color", "tmux-256color"])
def test_a_capable_caller_terminal_reaches_the_spawned_codex_unchanged(inherited) -> None:
    assert _tui_capable_term(inherited=inherited) == inherited


def test_a_stall_digest_carries_codex_warnings_and_its_last_log_rows(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / _CODEX_LOG_DB) as connection:
        _ = connection.execute(
            "CREATE TABLE logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,"
            " level TEXT NOT NULL, target TEXT NOT NULL, feedback_log_body TEXT)"
        )
        _ = connection.executemany(
            "INSERT INTO logs (ts, level, target, feedback_log_body) VALUES (?, ?, ?, ?)",
            [
                (1, "INFO", "codex_core::boot", "starting"),
                (2, "WARN", "codex_mcp::rmcp_client", "mcp server needs auth"),
                (3, "DEBUG", "codex_core::models", "fetching models"),
            ],
        )
    digest = _codex_log_digest(codex_home=tmp_path)
    assert "Codex WARN/ERROR log rows (1):" in digest
    assert "2 WARN codex_mcp::rmcp_client: mcp server needs auth" in digest
    assert digest.rstrip().endswith("3 DEBUG codex_core::models: fetching models")


def test_an_unanswered_terminal_query_is_visible_in_the_raw_pty_rendering() -> None:
    """A stream `_plain` renders as empty is still readable escape-by-escape."""
    unanswered = "\x1b[6n\x1b[?u"
    assert _plain(text=unanswered) == ""
    assert _escaped(text=unanswered) == "\\x1b[6n\\x1b[?u"


def test_plain_renders_a_cursor_addressed_idle_prompt_on_its_screen_line() -> None:
    """The timeout's screen is the terminal state, not its write history."""
    raw = "\x1b[2J\x1b[1;1Hmodel: gpt-5.6-sol\x1b[39;1H› Ask Codex to do anything"

    assert _plain(text=raw).endswith("\n› Ask Codex to do anything")


def test_main_prompt_recognises_the_composer_without_a_placeholder_or_tip() -> None:
    plain = _plain(text="\x1b[2J\x1b[39;1H› Ask Codex to do anything")

    assert _has_main_prompt(plain=plain)


@pytest.mark.parametrize(
    "plain",
    [
        _plain(text="\x1b[2J\x1b[18;1HDo you trust this folder?\x1b[20;1H› Yes, I trust it"),
        f"model: {_CODEX_TEST_MODEL}\n/model to change\nTip: press @ to open this list directly",
        "",
    ],
)
def test_main_prompt_refuses_dialogs_and_screens_without_a_composer(plain: str) -> None:
    assert not _has_main_prompt(plain=plain)


def test_a_wait_returns_once_its_state_renders() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"booting... overseer (livespec-overseer)  Skill")
        exercise = _Exercise(fd=read_fd)
        current = _read_until(
            exercise=exercise,
            phase="picker render",
            seen="",
            predicate=lambda plain: "overseer (livespec-overseer)" in plain,
            stall_seconds=_CODEX_PICKER_STALL_SECONDS,
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)
    assert current.endswith("Skill")


def test_a_silent_codex_fails_naming_the_wait_its_times_and_the_host_load() -> None:
    """Silence, not a phase budget, is what expires a wait, and the failure says which."""
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"Mentions  Files, directories, plugins")
        exercise = _Exercise(fd=read_fd)
        with pytest.raises(AssertionError) as raised:
            _ = _read_until(
                exercise=exercise,
                phase="picker render",
                seen="",
                predicate=lambda plain: "overseer (livespec-overseer)" in plain,
                stall_seconds=0.2,
            )
    finally:
        os.close(read_fd)
        os.close(write_fd)
    message = str(raised.value)
    assert "the picker render wait expired because the Codex TUI wrote nothing for 0.2s" in message
    assert re.search(r"Phase elapsed \d+\.\ds; exercise elapsed \d+\.\ds of 600s allowed", message)
    assert "Host load average at expiry: " in message
    assert "(1/5/15 min)" in message
    assert "Last rendered screen:\nMentions  Files, directories, plugins" in message


def test_a_codex_that_never_stops_writing_is_bounded_by_the_exercise_ceiling() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"loading")
        exercise = _Exercise(fd=read_fd, started=time.monotonic() - 601.0)
        with pytest.raises(AssertionError) as raised:
            _ = _read_until(
                exercise=exercise,
                phase="startup",
                seen="",
                predicate=lambda plain: "never" in plain,
                stall_seconds=_CODEX_STARTUP_STALL_SECONDS,
            )
    finally:
        os.close(read_fd)
        os.close(write_fd)
    assert "the startup wait expired because the whole exercise reached its 600s ceiling" in str(
        raised.value
    )


def test_a_stall_digest_names_a_missing_codex_log(tmp_path: Path) -> None:
    assert _codex_log_digest(codex_home=tmp_path) == (
        f"(no Codex log: {tmp_path / _CODEX_LOG_DB} does not exist)"
    )


_FOREIGN_MARKETPLACE = "openai-curated-remote"
_FOREIGN_PLUGIN = "someoneelses-remote-plugin"


def _fake_host_codex_home(*, home: Path) -> Path:
    """A stand-in `~/.codex` carrying OUR plugin and one foreign remote plugin.

    Shaped like the real host tree the live exercise reads: a
    `cache/<marketplace>/<plugin>/<version>` materialization per installed plugin,
    plus the two root registries that record which plugins and marketplaces the
    host knows about. The foreign plugin declares an MCP server, because that
    declaration is what Codex acts on at startup and therefore what must not be
    reachable from the home this test builds.
    """
    plugins = home / "plugins"
    for marketplace, plugin, version in (
        (_CODEX_MARKETPLACE, _CODEX_PLUGIN, "5.34.2"),
        (_FOREIGN_MARKETPLACE, _FOREIGN_PLUGIN, "1.0.0"),
    ):
        materialized = plugins / _CODEX_PLUGIN_CACHE_DIR / marketplace / plugin / version
        materialized.mkdir(parents=True)
        (materialized / "plugin.json").write_text(
            json.dumps({"name": plugin, "mcpServers": {plugin: {"url": f"https://{plugin}"}}}),
            encoding="utf-8",
        )
    (plugins / "installed_plugins.json").write_text(
        json.dumps(
            {
                "plugins": {
                    _CODEX_PLUGIN_KEY: [{"version": "5.34.2"}],
                    f"{_FOREIGN_PLUGIN}@{_FOREIGN_MARKETPLACE}": [{"version": "1.0.0"}],
                }
            }
        ),
        encoding="utf-8",
    )
    (plugins / "known_marketplaces.json").write_text(
        json.dumps(
            {
                _CODEX_MARKETPLACE: {"source": {"ref": "master"}},
                _FOREIGN_MARKETPLACE: {"source": {"ref": "main"}},
            }
        ),
        encoding="utf-8",
    )
    for filename in _HOST_CODEX_HOME_FILES:
        (home / filename).write_text("{}", encoding="utf-8")
    return plugins


def _exposed_surface(*, codex_home: Path) -> str:
    """Every path name AND file body reachable from the built home, as one string.

    Reading the BODIES as well as the names is the point: a registry entry naming a
    foreign plugin is exposure just as surely as a cache directory is, and it is the
    form a names-only assertion would miss.
    """
    parts: list[str] = []
    for path in sorted(codex_home.rglob("*")):
        parts.append(str(path.relative_to(codex_home)))
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def test_the_built_codex_home_exposes_only_the_declared_plugin(tmp_path: Path) -> None:
    """The scratch home exposes our plugin alone, so no foreign MCP server starts.

    THE DEFECT THIS PINS (`overseer-kq7tkw`). `_prepare_codex_home` used to symlink
    the host's WHOLE `~/.codex/plugins` root into the scratch home, so every remote
    plugin the operator happens to have installed was visible to the spawned Codex
    and each one's MCP server started and performed a network handshake at startup.
    Measured on the release host 2026-10-23: the only ERROR in Codex's own log was a
    foreign `box` MCP server failing auth against `mcp.box.com`, and the acceptance
    stalled waiting for a picker state that startup had not reached. That makes this
    gate's verdict depend on the host's unrelated plugin inventory and on the
    reachability of third-party servers — neither of which it claims to check.
    """
    host_home = tmp_path / "host"
    plugins_root = _fake_host_codex_home(home=host_home)
    codex_home = tmp_path / "scratch"
    codex_home.mkdir()

    _prepare_codex_home(codex_home=codex_home, plugins_root=plugins_root, host_home=host_home)

    exposed = codex_home / "plugins"
    assert not exposed.is_symlink(), (
        "the scratch plugins root is a symlink to the host's whole multi-tenant "
        "plugin tree, so every host-installed plugin is exposed to the spawned Codex"
    )
    surface = _exposed_surface(codex_home=codex_home)
    assert _FOREIGN_PLUGIN not in surface, (
        f"the built Codex home exposes the foreign plugin {_FOREIGN_PLUGIN!r}, so "
        f"Codex will start its MCP server at startup. Exposed surface:\n{surface}"
    )
    assert (
        _FOREIGN_MARKETPLACE not in surface
    ), f"the built Codex home exposes the foreign marketplace {_FOREIGN_MARKETPLACE!r}"

    cache = exposed / _CODEX_PLUGIN_CACHE_DIR
    assert [entry.name for entry in sorted(cache.iterdir())] == [_CODEX_MARKETPLACE]
    assert [entry.name for entry in sorted((cache / _CODEX_MARKETPLACE).iterdir())] == [
        _CODEX_PLUGIN
    ]
    assert (
        cache / _CODEX_MARKETPLACE / _CODEX_PLUGIN / "5.34.2" / "plugin.json"
    ).is_file(), "the declared plugin's own materialized tree is no longer reachable"
    assert _CODEX_PLUGIN_KEY in (exposed / "installed_plugins.json").read_text(encoding="utf-8")
    assert _CODEX_MARKETPLACE in (exposed / "known_marketplaces.json").read_text(encoding="utf-8")
    for filename in _HOST_CODEX_HOME_FILES:
        assert (codex_home / filename).is_file(), f"{filename} is no longer linked"


@_LIVE_CODEX_PICKER_ONLY
def test_skills_picker_renders_the_declared_codex_canonical_command() -> None:
    plugin, skill = _declared_codex_command(repo_root=_REPO_ROOT)
    codex = shutil.which("codex")
    if codex is None:
        pytest.fail("codex CLI is required for the live /skills picker acceptance")

    master_fd, slave_fd = pty.openpty()
    _prepare_pty(master_fd=master_fd, slave_fd=slave_fd)
    env = _codex_tui_env(inherited=os.environ)
    tmp_root = _HOST_CODEX_HOME / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="livespec-codex-home-", dir=tmp_root) as codex_home_raw:
        codex_home = Path(codex_home_raw)
        _prepare_codex_home(codex_home=codex_home)
        env["CODEX_HOME"] = str(codex_home)
        proc = subprocess.Popen(  # noqa: S603  — argv is a resolved codex binary, not a shell.
            [
                codex,
                "--no-daemon",
                "--no-alt-screen",
                "--dangerously-bypass-hook-trust",
                "-C",
                str(_REPO_ROOT),
            ],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            close_fds=True,
            # Own session, so the pty we just built becomes codex's CONTROLLING
            # terminal instead of whatever the invoker had. Measured necessary:
            # driven through lefthook's runner the TUI otherwise degrades to a
            # one-glyph-per-line renderer even though the pty is verifiably
            # 40x120 -- reproduced 3/3 under lefthook against 2/2 clean runs of
            # the identical standalone aggregate.
            start_new_session=True,
        )
        os.close(slave_fd)
        try:
            transcript = _exercise_skills_picker(master_fd=master_fd, plugin=plugin, skill=skill)
        except AssertionError as exc:
            raise AssertionError(f"{exc}\n\n{_codex_log_digest(codex_home=codex_home)}") from exc
        finally:
            _stop_codex(proc=proc, fd=master_fd)

    plain = _plain(text=transcript)
    expected_row = _skill_row(plugin=plugin, skill=skill)
    assert expected_row in plain, (
        f"the Codex /skills picker did not render {expected_row!r}, so the surface backing "
        f"harnesses.codex.canonical_command = '{plugin}:{skill}' does not exist. "
        f"Last rendered output:\n{plain[-3000:]}"
    )
    assert "Skill" in plain, (
        "the picker rendered no Skill-typed row; the plugin may be registered without its "
        f"skills resolving. Last rendered output:\n{plain[-3000:]}"
    )
