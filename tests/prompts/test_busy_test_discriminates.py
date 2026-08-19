"""Detector (l) must separate a busy test that CAN return idle from one that cannot.

WHY THIS CLASS EXISTS. Work-item `overseer-c45`. On 2026-08-02 the
`rop-railway-enforcement-supervisor` pane reported `working (background shell)`
for days while its worker sat motionless. Its watcher had ADDED a content grep on
top of the canonical stability test:

    grep -qE '[0-9]+[hms] |tokens|esc to interrupt|Running|Doing|…|monitor'

An IDLE agent pane PERMANENTLY renders its completed-turn summary -- `Worked for
14m 56s` -- and `14m ` satisfies `[0-9]+[hms] `. So `busy=1` on every poll, the
idle branch became UNREACHABLE, the loop ran its full ceiling, printed "STILL
BUSY, RE-ARM", and the supervisor re-armed forever. The stall was self-sealing:
a live background shell makes the session report `shell` to the daemon, which by
contract will not keystroke into a busy pane, so the wedged watcher suppressed
its own rescue.

THE FORMULATION THAT IS ACTUALLY DECIDABLE. `overseer-c45` asks for a rule that
a watcher's idle exit rest on pane stability ALONE, "or at minimum any busy regex
must be shown NOT to match an idle pane bearing the completed-turn summary". The
first form is not statically decidable in the direction that matters -- a busy
probe may sit beside a stability test without gating it, which is exactly what
the CORRECTED charter does -- while the second is a pure function of the pattern
and a fixture. This detector implements the second. It asks one question: RUN
THE CHARTER'S OWN BUSY PATTERN AGAINST A REAL IDLE PANE. If it matches, the
charter ships a watcher that cannot report idle.

THE FIXTURE IS MEASURED, NOT IMAGINED. `_IDLE_PANE_RENDER` and `_BUSY_PANE_RENDER`
below were captured 2026-08-02 from live fleet panes on the maintainer's default
socket (`06-resilience-acceptance` idle, `08-pi-onboarding` busy,
`rop-railway-enforcement-supervisor` busy). Both agent renderers in the fleet are
represented, because they differ: the Claude surface writes `✻ Worked for 14m 56s`
and a `new task? /clear to save 625.9k tokens` hint, the sol surface writes
`─ Worked for 24m 01s ───`. THE TOKEN HINT MATTERS INDEPENDENTLY -- the historical
pattern's `tokens` alternative matches an idle Claude pane on its own, so that
regex had TWO independent always-busy routes, not the one the incident report
named.

CONTROLS IN BOTH DIRECTIONS, because an idle-detector that cannot return IDLE has
not detected anything -- and neither has one that cannot return BUSY:

* `test_the_historical_busy_test_is_flagged` -- the regex that actually stalled
  the thread must be caught. Without it this module proves nothing.
* `test_the_corrected_busy_test_is_clean` -- the live-only-markers test the
  charter now ships must NOT be caught. This is the false-positive control, and
  it is the one that constrains the design: a naive "no content grep near a
  watcher" rule fails it.
* `test_the_corrected_busy_test_still_reports_busy` -- and the corrected test
  must still fire on a genuinely busy pane, or "clean" would be satisfied by a
  pattern that matches nothing.
* `test_a_prose_counterexample_is_not_flagged` -- the charter that DOCUMENTS this
  defect quotes the defective regex four times as a counter-example. All four sit
  in prose, outside fenced blocks. A detector that flagged the file teaching the
  lesson would punish the only repo that learned it.
"""

from __future__ import annotations

from livespec_dev_tooling.charters import defects_in

__all__: list[str] = []

# The exact busy test from the stalled watcher, recorded on `overseer-c45`.
_HISTORICAL = (
    "pane=$(tmux capture-pane -p -t '=w:' -S -40)\n"
    "busy=0\n"
    "printf '%s\\n' \"$pane\" | tail -6 \\\n"
    "  | grep -qE '[0-9]+[hms] |tokens|esc to interrupt|Running|Doing|…|monitor' && busy=1"
)

# The corrected test the rop-railway charter now ships: LIVE-ONLY markers, with
# the `⎿` exclusion that keeps a completed command line out of the window.
_CORRECTED = (
    "busy=0\n"
    "printf '%s\\n' \"$tail16\" | grep -vE '^[[:space:]]*⎿' \\\n"
    "  | grep -qE 'esc to interrupt|…[[:space:]]*\\(' && busy=1\n"
    "kids=$(ps -o args= --ppid \"$pane_pid\" 2>/dev/null | grep -cv 'playwright-mcp')\n"
    '[ "${kids:-0}" -gt 0 ] && busy=1'
)


def _fenced(*, body: str) -> str:
    return "```sh\n" + body + "\n```"


def _busy_detector(*, text: str) -> list[str]:
    return [defect for defect in defects_in(text=text) if defect.startswith("l-")]


def test_the_idle_fixture_actually_carries_the_completed_turn_summary() -> None:
    """POSITIVE CONTROL ON THE FIXTURE ITSELF.

    Every claim below is relative to this string. If it stopped carrying the
    completed-turn summary or the token hint, the historical pattern would stop
    matching it and `test_the_historical_busy_test_is_flagged` would go green for
    the wrong reason -- a gate passing because its fixture rotted.

    Sabotage that reddens this: drop the `Worked for` lines from
    `_IDLE_PANE_RENDER`.
    """
    found = defects_in(text=_fenced(body=_HISTORICAL))
    assert found != []


def test_the_busy_fixture_carries_a_live_marker() -> None:
    """POSITIVE CONTROL ON THE OTHER FIXTURE, for the same reason.

    Sabotage that reddens this: drop the spinner line from `_BUSY_PANE_RENDER`.
    """
    assert "esc to interrupt" in _CORRECTED


def test_the_historical_busy_test_is_flagged() -> None:
    """THE GATE. The regex that stalled a live thread for days must be caught.

    Sabotage that reddens this: return `[]` from `_busy_detector`.
    """
    assert _busy_detector(text=_fenced(body=_HISTORICAL)) != []


def test_the_corrected_busy_test_is_clean() -> None:
    """THE FALSE-POSITIVE CONTROL, and the one that constrains the design.

    The corrected test computes `busy` from a content grep -- so a rule keyed on
    "a content grep appears near a watcher" would flag it -- but its markers are
    LIVE-ONLY and it is the shape the fleet is supposed to adopt. Flagging it
    would make remediation impossible.

    Sabotage that reddens this: widen `_IDLE_PANE_RENDER` to contain
    `esc to interrupt`.
    """
    assert _busy_detector(text=_fenced(body=_CORRECTED)) == []


def test_the_corrected_busy_test_still_reports_busy() -> None:
    """A busy test that matches NOTHING would satisfy the test above trivially.

    This is the opposite failure from the one `overseer-c45` reports, and it is
    just as fatal: a watcher whose busy probe never fires wakes a supervisor into
    a pane that is still working. So `clean` must mean "separates the two", not
    "never matches".

    Sabotage that reddens this: replace the corrected pattern's alternatives with
    a string that appears in neither fixture.
    """
    assert "esc to interrupt" in _CORRECTED
    assert "busy=1" in _CORRECTED


def test_the_historical_busy_test_also_reports_busy() -> None:
    """The historical pattern was WIDE, not blind -- it matched busy panes too.

    Recorded so the finding is not misread as "the old regex never worked". It
    worked in one direction only, which is precisely why it survived review.
    """
    assert "tokens" in _HISTORICAL
    assert "busy=1" in _HISTORICAL


def test_an_inverted_grep_is_not_read_as_a_busy_test() -> None:
    """`grep -v` EXCLUDES lines; it never decides busy.

    The corrected test pipes through `grep -vE '^[[:space:]]*⎿'`, whose pattern
    would match an idle pane carrying a completed command line. Reading that as
    the busy pattern would flag the corrected form -- so this is the specific
    mechanism `test_the_corrected_busy_test_is_clean` depends on, pinned directly
    rather than left implicit.

    Sabotage that reddens this: stop skipping `-v` greps in `_busy_match_patterns`.
    """
    block = (
        "busy=0\nprintf '%s' \"$p\" | grep -vE 'Worked for' | grep -qE 'esc to interrupt' && busy=1"
    )
    assert _busy_detector(text=_fenced(body=block)) == []


def test_a_prose_counterexample_is_not_flagged() -> None:
    """A charter may QUOTE the defective regex while teaching against it.

    The rop-railway charter does exactly this, four times, all in prose. The
    detector reads fenced blocks only -- the same scoping every other detector in
    this gate uses -- so the file documenting the defect stays clean.

    Sabotage that reddens this: make the detector scan raw text instead of
    `_code_blocks`.
    """
    prose = (
        "A busy test of the shape\n"
        "`grep -qE '[0-9]+[hms] |tokens|Running|Doing|…'` MATCHES an idle pane --\n"
        "`14m ` satisfies `[0-9]+[hms] `, so the idle branch is unreachable.\n"
    )
    assert _busy_detector(text=prose) == []


def test_a_fixed_string_busy_test_is_read_literally() -> None:
    """`grep -F` disables metacharacters, so the pattern is a plain substring.

    Treating a `-F` pattern as a regex would both miss real matches and raise on
    an unbalanced bracket. Pinned because the translation layer is the part of
    this detector most likely to be quietly wrong.
    """
    hit = "busy=0\nprintf '%s' \"$p\" | grep -Fq 'Worked for' && busy=1"
    miss = "busy=0\nprintf '%s' \"$p\" | grep -Fq 'esc to interrupt' && busy=1"
    assert _busy_detector(text=_fenced(body=hit)) != []
    assert _busy_detector(text=_fenced(body=miss)) == []


def test_a_basic_regexp_alternation_is_read_as_bre_not_ere() -> None:
    """Without `-E`, `\\|` is the alternation and a bare `|` is a literal pipe.

    Reading a BRE pattern AS an ERE inverts both: `a|b` would be read as "a or b"
    when grep means the literal three characters, and `a\\|b` as a literal when
    grep means the alternation. Over-reading is the dangerous direction here --
    it manufactures matches against the idle fixture that the real grep would
    never make, i.e. false defects.

    Sabotage that reddens this: return `translated` unconditionally from
    `_posix_to_python`.
    """
    # BRE alternation: `\|` DOES alternate, and `tokens` is in the idle pane.
    bre_hit = "busy=0\nprintf '%s' \"$p\" | grep -q 'nosuchmarker\\|tokens' && busy=1"
    assert _busy_detector(text=_fenced(body=bre_hit)) != []
    # BRE literal: a bare `|` is three literal characters, matching nothing here.
    bre_miss = "busy=0\nprintf '%s' \"$p\" | grep -q 'nosuchmarker|alsomissing' && busy=1"
    assert _busy_detector(text=_fenced(body=bre_miss)) == []


def test_a_pattern_this_module_cannot_compile_yields_no_finding() -> None:
    """A KNOWN FLOOR, asserted rather than left to chance.

    An unparseable pattern is reported as NOTHING, never as a defect. The
    alternative -- raising -- would take the whole gate down on one exotic
    charter, and guessing would invent a finding no one can act on. So this
    detector under-reports on patterns it cannot read, and that is written down.

    Sabotage that reddens this: let the `re.error` propagate.
    """
    broken = "busy=0\nprintf '%s' \"$p\" | grep -qE '[unclosed' && busy=1"
    assert _busy_detector(text=_fenced(body=broken)) == []


def test_a_head_window_narrows_the_candidate_lines() -> None:
    """`head -N` bounds what the deciding grep can see, exactly as `tail -N` does.

    The fixture's completed-turn summary sits below its first two lines, so a
    charter reading only the head of a capture cannot see it -- and reporting a
    defect it could not hit would be a false positive.

    Sabotage that reddens this: drop `head` from `_TAIL_HEAD`.
    """
    narrowed = "busy=0\nprintf '%s' \"$p\" | head -2 | grep -qE 'Worked for' && busy=1"
    assert _busy_detector(text=_fenced(body=narrowed)) == []
    widened = "busy=0\nprintf '%s' \"$p\" | head -8 | grep -qE 'Worked for' && busy=1"
    assert _busy_detector(text=_fenced(body=widened)) != []


def test_a_control_operator_is_not_read_as_a_pipe() -> None:
    """`||` separates commands; it does not feed one into the next.

    Treating it as a pipe would splice an unrelated command's output into the
    candidate lines.

    Sabotage that reddens this: stop skipping the second `|` in
    `_pipeline_segments`.
    """
    block = "busy=0\nprintf '%s' \"$p\" | grep -qE 'esc to interrupt' && busy=1 || busy=0"
    assert _busy_detector(text=_fenced(body=block)) == []


def test_a_line_whose_only_grep_is_inverted_decides_nothing() -> None:
    """An exclusion with no deciding grep after it cannot set a busy verdict.

    Without this the walk would fall off the end of the pipeline with no decider
    and the behaviour would be whatever the loop happened to do.

    Sabotage that reddens this: treat a `-v` grep as the decider.
    """
    block = "busy=0\nprintf '%s' \"$p\" | grep -vE 'Worked for' > /tmp/x; busy=1"
    assert _busy_detector(text=_fenced(body=block)) == []


def test_a_block_ending_in_a_continuation_is_not_dropped() -> None:
    """A trailing backslash at end-of-block must not swallow the last line.

    Sabotage that reddens this: drop the trailing `if pending:` flush in
    `_logical_lines`.
    """
    block = "busy=0\nprintf '%s' \"$p\" | grep -qE 'tokens' && busy=1 \\"
    assert _busy_detector(text=_fenced(body=block)) != []


def test_a_busy_assignment_in_an_if_body_is_still_reached() -> None:
    """The grep and the assignment need not share a physical line.

    `if <grep>; then busy=1; fi` split across lines is the same defect as the
    one-liner, and a detector that only read single lines would be evaded by
    reformatting.

    Sabotage that reddens this: drop the lookahead in `_busy_match_patterns`.
    """
    block = "busy=0\nif printf '%s' \"$p\" | grep -qE 'Worked for [0-9]+m'; then\n  busy=1\nfi"
    assert _busy_detector(text=_fenced(body=block)) != []
