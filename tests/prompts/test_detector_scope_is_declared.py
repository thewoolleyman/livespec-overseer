"""Every charter detector must DECLARE whether it is line- or document-scoped.

The eleven detectors do not all mean the same thing by "clean". SEVEN are
LINE-SCOPED: each offending line is reported, and a correct form elsewhere in the
charter changes nothing. FOUR are DOCUMENT-SCOPED: `(e)`, `(h)`, `(i)` and `(j)`
return NOTHING as soon as the correct property appears anywhere in the file's
fenced blocks, however many defective lines sit beside it.

That split is deliberate and each of those four docstrings argues for it: the
correct form is a helper DETECTED ONCE and called later by name, so a per-line
rule would flag the correct call site. This module does not second-guess that.
It makes the choice EXPLICIT and EXECUTABLE, because three things follow from it
that were true but written down nowhere:

1. **A charter absorbs new defects of a document-scoped class once it contains
   the correct form once.** Adding a genuinely wrapper-less `bd` call to
   `.ai/supervisor-protocol.md` -- HALF OF EVERY DEPLOYED CHARTER -- produces no
   finding at all, because a wrapper already appears elsewhere in it.

2. **The hardened exemplar masks four of the eleven classes.** Measured
   2026-07-31 by injecting each defect into every real charter in this repo:
   (a)-(d), (f), (g) and (k) fire in 8 of 8; (e) fires in 3 of 8, (h) in 6 of 8,
   (i) and (j) in 7 of 8 -- and `plan/supervisor-prompt-quality/supervisor-handoff.md`
   is the ONLY charter masking (i) and (j), and masks (h) and (e) too. It is the
   most immunised file in the repo precisely BECAUSE it demonstrates every
   correct form. So `test_the_hardened_exemplar_is_clean` cannot fire for those
   four classes no matter how broken they become: that control proves the
   detectors do not FALSE-POSITIVE, and for a document-scoped class it can never
   prove they still fire.

3. **A count of a document-scoped class counts FILES LACKING A PROPERTY, not
   defective lines.** True, and SMALLER THAN IT SOUNDS -- measured against the
   fleet 2026-07-31, the four document-scoped classes contribute **5 of 117
   (4%)**, and only 2, 1, 1 and 6 of 29 fleet charters are immune to (h), (i),
   (j) and (e) respectively. The distinction is architecturally real and
   numerically minor: it does NOT move `overseer-yho.3`'s costing, where class
   (a) alone is 92 of 117. Recorded with its magnitude so it is not mistaken for
   a reason to re-open a settled measurement.

**THE RISK IS LATENT, NOT LIVE, AND THE DIFFERENCE MATTERS.** Measured
2026-07-31 across every scanned charter: each masked class has EXACTLY ONE
instance in the file that masks it, and in every case the correct property
genuinely applies to that instance. The two `bd` invocations in
`.ai/supervisor-protocol.md` and in the exemplar are the documented-correct
`ledger_show()` shape -- a wrapper call plus the bare fallback an adopter without
a wrapper needs -- and the exemplar's single `(i)` read carries its truncation
notice and its single `(j)` test its non-empty guard. **So nothing is hidden
today.** The exposure begins the moment a file already holding the property gains
a SECOND instance that is defective, because that one arrives unreported. Stated
this way round on purpose: a reader who takes this module as evidence of existing
hidden defects would go looking for something that is not there.

THE LINEAGE, and why a registry rather than another pair of cases. Class (e)
once pinned the literal `-qx`; the moment (f) was remediated to `-Fqx` the (e)
detector went blind on charters it had flagged an hour earlier, while its own
synthetic control -- written against the pre-fix spelling -- stayed green.
`test_remediating_f_does_not_disarm_e` pins that ONE pair. The general lesson is
that a detector's REACH is a property nobody was asserting, and a synthetic
control cannot see a reach problem because it supplies the surrounding context
itself. Here the reach is asserted directly, for all eleven, in both directions.

**THE LOAD-BEARING ASSERTION IS THE REGISTRY-COVERAGE ONE.** A twelfth detector
cannot be added without deciding, in writing, which scope it has -- the decision
that was never made explicitly for the first eleven.
"""

from __future__ import annotations

from test_charters_carry_no_known_defects import _DETECTORS, _PROOF, defects_in

__all__: list[str] = []

_LINE_SCOPED = "line"
_DOCUMENT_SCOPED = "document"

# The declared reach of every detector. MEASURED, not assumed: see the module
# docstring for the injection run that produced it.
_SCOPE: dict[str, str] = {
    "a": _LINE_SCOPED,
    "b": _LINE_SCOPED,
    "c": _LINE_SCOPED,
    "d": _LINE_SCOPED,
    "e": _DOCUMENT_SCOPED,
    "f": _LINE_SCOPED,
    "g": _LINE_SCOPED,
    "h": _DOCUMENT_SCOPED,
    "i": _DOCUMENT_SCOPED,
    "j": _DOCUMENT_SCOPED,
    "k": _LINE_SCOPED,
    # (l) is LINE-scoped, and the decision is worth stating rather than
    # inheriting. A charter may legitimately ship SEVERAL busy tests — the fleet's
    # corrected watcher runs a pane probe beside a child-process probe — so one
    # correct test elsewhere in the file says nothing about a defective one. The
    # document-scoped argument that carries (e), (h), (i) and (j) is that the
    # correct form is a helper DETECTED ONCE and called later by name; a busy
    # regex is not detected once, it is evaluated every poll, wherever it sits.
    "l": _LINE_SCOPED,
}

# One defective line per class, in the shape the class was written for.
_DEFECT: dict[str, str] = {
    "a": "tmux send-keys -t my-session -- 'echo hi'",
    "b": (
        "pane_cwd=$(tmux display-message -p -t '=x:' '#{pane_current_path}')\n"
        'case "$(readlink -f -- "$pane_cwd")" in'
    ),
    "c": "pane=$(tmux capture-pane -p -t '=x:' -S -40)",
    "d": 'prev=""; stable=0',
    "e": (
        "SUPERVISOR_TARGET='=demo-supervisor:'\n"
        'tmux has-session -t "$SUPERVISOR_TARGET" '
        '|| { echo "HALT"; echo "REMEDY: bootstrap"; exit 1; }'
    ),
    "f": "tmux list-sessions -F '#{session_name}' | grep -qx 'demo' || exit 1",
    "g": 'just check | tail -5; echo "EXIT=${PIPESTATUS[0]}"',
    "h": "ledger_anchor='overseer-yho'\nbd show \"$ledger_anchor\" --json || exit 1",
    "i": 'test ! -f "$supervisor_marker" || sed -n \'1,220p\' "$supervisor_marker"',
    "j": 'test ! -f "$supervisor_marker" || cat "$supervisor_marker"',
    "k": "worker_state_at=$(date -u -r \"$m\" '+%Y-%m-%dT%H:%M:%SZ')",
    "l": "printf '%s\\n' \"$pane\" | grep -qE '[0-9]+[hms] |tokens' && busy=1",
}

# The CORRECT property for the same class, which a document-scoped detector
# accepts from anywhere in the file and a line-scoped one does not.
_CORRECT: dict[str, str] = {
    "a": "tmux send-keys -t '=my-session:' -- 'echo hi'",
    "b": (
        "pane_cwd=$(tmux display-message -p -t '=x:' '#{pane_current_path}')\n"
        '[ -n "$pane_cwd" ] || { echo "HALT: empty"; exit 1; }\n'
        'case "$(readlink -f -- "$pane_cwd")" in'
    ),
    "c": "tmux capture-pane -p -t '=x:'",
    "d": 'prev="__OVERSEER_NO_CAPTURE_YET__"; stable=0',
    "e": _PROOF,
    "f": "tmux list-sessions -F '#{session_name}' | grep -Fqx 'demo' || exit 1",
    "g": 'just check | tail -5; echo "EXIT=${pipestatus[1]}"',
    "h": (
        "ledger_show() {\n"
        "  if command -v with-livespec-env.sh >/dev/null 2>&1; then\n"
        '    with-livespec-env.sh -- bd show "$1" --json\n'
        "  else\n"
        '    bd show "$1" --json\n'
        "  fi\n"
        "}"
    ),
    "i": (
        'marker_lines=$(wc -l < "$supervisor_marker")\n'
        "sed -n '1,160p' \"$supervisor_marker\"\n"
        "printf 'TRUNCATED: lines 161-%d of %d NOT SHOWN\\n' "
        '"$((marker_lines - 160))" "$marker_lines"'
    ),
    "j": (
        '[ -n "${supervisor_marker:-}" ] || { echo "HALT: unset or empty"; exit 1; }\n'
        'test ! -f "$supervisor_marker" || cat "$supervisor_marker"'
    ),
    "k": "now=$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "l": "printf '%s\\n' \"$pane\" | grep -qE 'esc to interrupt' && busy=1",
}


def _shipped_classes() -> list[str]:
    """The class letter of every detector the gate actually ships."""
    return [name.split("-", 1)[0] for name, _ in _DETECTORS]


def _fenced(*, body: str) -> str:
    return "```sh\n" + body + "\n```"


def _findings(*, cls: str, text: str) -> list[str]:
    return [found for found in defects_in(text=text) if found.startswith(cls + "-")]


def test_the_registry_covers_exactly_the_shipped_detectors() -> None:
    """THE GATE. A twelfth detector must declare its scope before it can land.

    This is the assertion the module exists for. Adding a detector without a
    scope entry fails here, which forces the decision to be made deliberately
    and written down rather than inherited from whichever existing detector was
    copied. Removing one and leaving a stale entry fails here too.

    Sabotage that reddens this: delete the "k" entry from `_SCOPE`.
    """
    assert sorted(_SCOPE) == sorted(_shipped_classes())


def test_every_class_carries_both_fixtures() -> None:
    """A missing fixture would silently skip a class in the reach tests below.

    Without this, dropping a class from `_DEFECT` would shrink the loops rather
    than fail them, and the class would go unchecked while everything stayed
    green -- the vacuous-pass shape this suite guards against everywhere.

    Sabotage that reddens this: delete the "g" entry from `_CORRECT`.
    """
    assert sorted(_DEFECT) == sorted(_SCOPE)
    assert sorted(_CORRECT) == sorted(_SCOPE)


def test_every_detector_fires_on_its_own_defect_in_isolation() -> None:
    """NO DETECTOR IS BLIND. The precondition for either reach claim below.

    A detector that fires on nothing would satisfy the document-scoped test
    trivially, so this must pass before that result means anything.

    Sabotage that reddens this: replace any `_DEFECT` entry with its `_CORRECT`
    counterpart.
    """
    silent = [
        cls for cls in sorted(_SCOPE) if not _findings(cls=cls, text=_fenced(body=_DEFECT[cls]))
    ]
    assert silent == []


def test_a_line_scoped_detector_survives_a_correct_form_elsewhere() -> None:
    """A line-scoped detector reports the defective line regardless of neighbours.

    This is the direct generalisation of `test_remediating_f_does_not_disarm_e`:
    a correct form landing nearby must not disarm a detector, for any of the
    seven, not just the pair that was caught doing it.

    Sabotage that reddens this: move any line-scoped class to `_DOCUMENT_SCOPED`.
    """
    disarmed = [
        cls
        for cls in sorted(_SCOPE)
        if _SCOPE[cls] == _LINE_SCOPED
        and not _findings(
            cls=cls,
            text=_fenced(body=_CORRECT[cls]) + "\n\n" + _fenced(body=_DEFECT[cls]),
        )
    ]
    assert disarmed == []


def test_a_document_scoped_detector_is_cleared_by_a_correct_form_elsewhere() -> None:
    """The declared trade-off, pinned so it cannot change silently.

    This asserts a WEAKNESS on purpose. These four accept the correct property
    from anywhere in the charter, so the defective line beside it is not
    reported. That is the documented cost of not flagging the correct call site
    of a helper detected once -- but it means a charter already holding the
    property cannot fail these classes again, and the hardened exemplar holds
    all four.

    If a future change makes one of these line-scoped, this test fails and the
    right response is to MOVE ITS ENTRY, not to delete the assertion.
    """
    still_flagged = [
        cls
        for cls in sorted(_SCOPE)
        if _SCOPE[cls] == _DOCUMENT_SCOPED
        and _findings(
            cls=cls,
            text=_fenced(body=_CORRECT[cls]) + "\n\n" + _fenced(body=_DEFECT[cls]),
        )
    ]
    assert still_flagged == []
