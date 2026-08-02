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

WHAT IT DOES NOT PROVE, stated because this plan thread punishes unqualified live
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
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import tty
from collections.abc import Callable
from pathlib import Path

import livespec_dev_tooling
import pytest

_VENDOR_DIR = Path(livespec_dev_tooling.__file__).resolve().parent / "_vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

import jsoncomment  # noqa: E402  — vendor-path-aware import after sys.path insert.

__all__: list[str] = []

pytestmark = pytest.mark.skipif(
    os.environ.get("LIVESPEC_CODEX_SKILL_PICKER") != "1",
    reason="live Codex TUI picker acceptance runs only via just check-codex-skill-picker",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANSI_RE = re.compile(r"(?:\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[78])")
_FOREGROUND_QUERY = "\x1b]10;?\x1b\\"
_BACKGROUND_QUERY = "\x1b]11;?\x1b\\"
_FOREGROUND_RESPONSE = "\x1b]10;rgb:ffff/ffff/ffff\x1b\\"
_BACKGROUND_RESPONSE = "\x1b]11;rgb:0000/0000/0000\x1b\\"
_TERMINAL_RESPONSES = _FOREGROUND_RESPONSE + _BACKGROUND_RESPONSE
_CODEX_STARTUP_TIMEOUT_SECONDS = 120
_CODEX_PROMPT_MARKER = chr(0x203A)
_GIT_HOOK_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)
_HOST_CODEX_HOME = Path.home() / ".codex"

# The materialized plugin tree this run reads. Defaults to the host's, which is what
# the check asserts in normal operation.
#
# THE OVERRIDE EXISTS SO THE RED DEMONSTRATION CAN RUN AGAINST THIS EXACT CHECK.
# This slice's acceptance is "demonstrated RED by REMOVING THE SURFACE and showing
# the check FAILS", and a green that cannot go red is not evidence. Removing the
# surface from the HOST tree would prune a cache that live Codex sessions on this
# host are using, which this plan thread forbids. So the demo points this at a
# scratch copy with `.codex-plugin/skills/<skill>/` deleted, and the check fails
# there while the host tree is never touched. Without the seam the RED demo would
# have to be run against a hand-built REPLICA of the assertion path, which proves
# something about the replica rather than about the shipped check.
_PLUGINS_ROOT = Path(
    os.environ.get("LIVESPEC_CODEX_PLUGINS_ROOT", str(_HOST_CODEX_HOME / "plugins"))
)

# DELIBERATELY NO `[marketplaces.*]` BLOCK — this omission is load-bearing and was
# arrived at by measurement, not by taste.
#
# The template this is ported from declares its marketplaces here. Doing the same
# was tried and REBUILT THE SHARED PLUGIN CACHE: the real `~/.codex/plugins` is
# SYMLINKED into the scratch home (below), so a declared marketplace makes codex
# re-fetch and re-materialize `~/.codex/plugins/cache/livespec-overseer/...` —
# observed as fresh inodes on two consecutive runs. That is precisely the prune this
# plan thread warns breaks live Codex sessions on this host, and a check that fires
# on every `just check` must not do it.
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
model = "gpt-5.5"

[tui.model_availability_nux]
"gpt-5.5" = 4

[notice.model_migrations]
"gpt-5.4" = "gpt-5.5"

[projects."{_REPO_ROOT}"]
trust_level = "trusted"

[plugins."livespec-overseer@livespec-overseer"]
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


def _plain(*, text: str) -> str:
    return _ANSI_RE.sub("", text).replace("\r", "\n")


def _squashed(*, text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _has_main_prompt(*, plain: str) -> bool:
    squashed = _squashed(text=plain)
    return (
        ("model:gpt-5.5" in squashed and "/modeltochange" in squashed)
        or (
            f"{_CODEX_PROMPT_MARKER}explainthiscodebase" in squashed
            and "gpt-5.5default" in squashed
        )
        or "tip:" in squashed
    )


def _has_trust_prompt(*, plain: str) -> bool:
    return "doyoutrust" in _squashed(text=plain)


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


def _pump_until(
    *,
    fd: int,
    seen: str,
    predicate: Callable[[str], bool],
    timeout_seconds: float,
    answered: dict[str, int],
) -> tuple[bool, str]:
    """Read until `predicate` holds. Returns `(matched, transcript)`.

    Returning rather than raising on timeout is what lets a caller emit its OWN
    diagnostic against the full transcript instead of a generic timeout message.
    """
    deadline = time.monotonic() + timeout_seconds
    current = seen
    while time.monotonic() < deadline:
        remaining = max(0.05, deadline - time.monotonic())
        readable, _, _ = select.select([fd], [], [], min(0.25, remaining))
        if not readable:
            continue
        try:
            chunk = os.read(fd, 8192).decode("utf-8", errors="replace")
        except OSError as exc:
            tail = _plain(text=current)[-3000:]
            raise AssertionError(f"Codex TUI exited while waiting. Last output:\n{tail}") from exc
        current += chunk
        _answer_terminal_queries(fd=fd, current=current, answered=answered)
        if predicate(_plain(text=current)):
            return True, current
    return False, current


def _read_until(
    *,
    fd: int,
    seen: str,
    predicate: Callable[[str], bool],
    timeout_seconds: float,
    answered: dict[str, int],
) -> str:
    matched, current = _pump_until(
        fd=fd,
        seen=seen,
        predicate=predicate,
        timeout_seconds=timeout_seconds,
        answered=answered,
    )
    if matched:
        return current
    tail = _plain(text=current)[-3000:]
    raise AssertionError(f"Timed out waiting for Codex picker state. Last output:\n{tail}")


def _read_until_quiet(
    *, fd: int, seen: str, quiet_seconds: float, timeout_seconds: float, answered: dict[str, int]
) -> str:
    deadline = time.monotonic() + timeout_seconds
    quiet_deadline = time.monotonic() + quiet_seconds
    current = seen
    while time.monotonic() < deadline:
        remaining = max(0.05, min(deadline, quiet_deadline) - time.monotonic())
        readable, _, _ = select.select([fd], [], [], min(0.25, remaining))
        if not readable:
            if time.monotonic() >= quiet_deadline:
                return current
            continue
        try:
            chunk = os.read(fd, 8192).decode("utf-8", errors="replace")
        except OSError as exc:
            tail = _plain(text=current)[-3000:]
            raise AssertionError(f"Codex TUI exited while waiting. Last output:\n{tail}") from exc
        current += chunk
        _answer_terminal_queries(fd=fd, current=current, answered=answered)
        quiet_deadline = time.monotonic() + quiet_seconds
    tail = _plain(text=current)[-3000:]
    raise AssertionError(f"Timed out waiting for Codex TUI to settle. Last output:\n{tail}")


def _send(*, fd: int, text: str) -> None:
    os.write(fd, text.encode("utf-8"))


def _prepare_codex_home(*, codex_home: Path) -> None:
    (codex_home / "config.toml").write_text(_CODEX_TEST_CONFIG, encoding="utf-8")
    os.symlink(_PLUGINS_ROOT, codex_home / "plugins")
    for filename in ("auth.json", ".credentials.json", "installation_id"):
        source = _HOST_CODEX_HOME / filename
        if source.exists():
            os.symlink(source, codex_home / filename)


def _await_codex_prompt(*, fd: int, transcript: str, answered: dict[str, int]) -> str:
    current = _read_until(
        fd=fd,
        seen=transcript,
        predicate=lambda plain: _has_main_prompt(plain=plain) or _has_trust_prompt(plain=plain),
        timeout_seconds=_CODEX_STARTUP_TIMEOUT_SECONDS,
        answered=answered,
    )
    if not _has_trust_prompt(plain=_plain(text=current)):
        return _read_until_quiet(
            fd=fd,
            seen=current,
            quiet_seconds=6.0,
            timeout_seconds=_CODEX_STARTUP_TIMEOUT_SECONDS,
            answered=answered,
        )
    _send(fd=fd, text="\r")
    current = _read_until(
        fd=fd,
        seen=current,
        predicate=lambda plain: _has_main_prompt(plain=plain),
        timeout_seconds=_CODEX_STARTUP_TIMEOUT_SECONDS,
        answered=answered,
    )
    return _read_until_quiet(
        fd=fd,
        seen=current,
        quiet_seconds=6.0,
        timeout_seconds=_CODEX_STARTUP_TIMEOUT_SECONDS,
        answered=answered,
    )


def _open_skills_list(
    *, fd: int, transcript: str, query: str, expected_row: str, answered: dict[str, int]
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
    about the world" shape this plan thread keeps hitting.

    `@` reaches the SAME list in one step — the action menu's own tip says so
    ("Tip: press @ to open this list directly") — which removes the intermediate
    state that could be matched stale. `\\x15` (Ctrl-U) clears the composer first so
    a leftover keystroke cannot corrupt the filter.

    WAITS ON CONTENT, NOT ON QUIET, AND THAT DISTINCTION IS LOAD-BEARING. An earlier
    revision settled for "2s with no output" and PASSED standalone while FAILING
    inside the full `just check` aggregate: under the load of ~66 targets a 2s gap
    opens before the picker has filtered, so the transcript gets asserted mid-render.
    A quiet window measures the HOST, not the UI. Waiting for the expected row
    instead returns as soon as it renders and only gives up at the timeout, so a
    slow host costs seconds rather than a false red. This repo carries a P1 about a
    check aggregate that is flaky under concurrency (`overseer-jdo`); adding another
    load-sensitive gate to it would have been the same defect, self-inflicted.
    """
    _send(fd=fd, text="\x15@" + query)
    _matched, current = _pump_until(
        fd=fd,
        seen=transcript,
        predicate=lambda plain: expected_row in plain and "Skill" in plain,
        timeout_seconds=45,
        answered=answered,
    )
    return current


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
    answered: dict[str, int] = {}
    _send(fd=master_fd, text=_TERMINAL_RESPONSES)
    transcript = _await_codex_prompt(fd=master_fd, transcript="", answered=answered)
    return _open_skills_list(
        fd=master_fd,
        transcript=transcript,
        query=skill,
        expected_row=_skill_row(plugin=plugin, skill=skill),
        answered=answered,
    )


def test_skills_picker_renders_the_declared_codex_canonical_command() -> None:
    plugin, skill = _declared_codex_command(repo_root=_REPO_ROOT)
    codex = shutil.which("codex")
    if codex is None:
        pytest.fail("codex CLI is required for the live /skills picker acceptance")

    master_fd, slave_fd = pty.openpty()
    _prepare_pty(master_fd=master_fd, slave_fd=slave_fd)
    env = os.environ.copy()
    env["TERM"] = env.get("TERM", "xterm-256color")
    env["COLUMNS"] = "120"
    env["LINES"] = "40"
    env["NO_COLOR"] = "1"
    for name in _GIT_HOOK_ENV_VARS:
        env.pop(name, None)
    tmp_root = _HOST_CODEX_HOME / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="livespec-codex-home-", dir=tmp_root) as codex_home_raw:
        codex_home = Path(codex_home_raw)
        _prepare_codex_home(codex_home=codex_home)
        env["CODEX_HOME"] = str(codex_home)
        proc = subprocess.Popen(  # noqa: S603  — argv is a resolved codex binary, not a shell.
            [codex, "--no-alt-screen", "--dangerously-bypass-hook-trust", "-C", str(_REPO_ROOT)],
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
