"""Detector (h) must recognise a credential wrapper it cannot name in advance.

THE FALSE POSITIVE, MEASURED. `(h)` pinned the literal string
`with-livespec-env.sh`. `homelab` declares a DIFFERENT wrapper --
`with-homelab-env.sh` -- and its charters resolve it from the repo's own
`.livespec.jsonc` rather than hard-coding any name at all:

    ledger_wrapper=$(sed -n 's/.*"credential_wrapper"...' .livespec.jsonc | head -1)
    ledger_show() {
      if [ -n "$ledger_wrapper" ] && command -v "$ledger_wrapper" >/dev/null 2>&1; then
        "$ledger_wrapper" -- bd show "$1" --json
      ...

That is STRICTLY BETTER than the form the detector was pinned to, and the
detector scored it as a defect -- FOUR of them, across two charters. So the gate
penalised the fleet's best wrapper handling, and it failed QUIETLY and in the
wrong direction: a repo that did the right thing looked dirtier than one that
hard-codes a name that happens to match.

WHY IT MATTERS BEYOND TIDINESS. `plan/fleet-charter-remediation/` records this as
a PRECONDITION for ever pointing this gate at `homelab`. Remediating against an
uncorrected `(h)` would mean "fixing" code that is already correct -- rewriting a
config-driven lookup into a hard-coded name, in the one repo that consumes no pin
and therefore cannot be corrected by a release.

THE RULE IS NOW A PROPERTY, NOT A NAME, which is what makes it survive the next
repo. A `bd` call is wrapped when the charter EITHER

  * names a `with-<something>-env.sh` wrapper -- any fleet member's, not just
    this one's -- or
  * binds a wrapper to a VARIABLE, proves it with `command -v`, and invokes `bd`
    THROUGH THAT SAME VARIABLE.

The second clause deliberately requires both halves of the same variable. A
charter cannot clear the detector by running `command -v` on something unrelated,
because the binding it proves must also be the binding it calls.
"""

from __future__ import annotations

from test_charters_carry_no_known_defects import wrapper_less_ledger_read

__all__: list[str] = []

# `homelab`'s real shape, reduced to the load-bearing lines.
_CONFIG_DRIVEN = (
    "ledger_wrapper=$(sed -n 's/.*\"credential_wrapper\".*/\\1/p' .livespec.jsonc | head -1)\n"
    "ledger_show() {\n"
    '  if [ -n "$ledger_wrapper" ] && command -v "$ledger_wrapper" >/dev/null 2>&1; then\n'
    '    "$ledger_wrapper" -- bd show "$1" --json\n'
    "  else\n"
    '    bd show "$1" --json\n'
    "  fi\n"
    "}"
)

# Another fleet member's wrapper, named directly.
_OTHER_REPO_LITERAL = (
    "if command -v with-homelab-env.sh >/dev/null 2>&1; then\n"
    '  with-homelab-env.sh -- bd show "$1" --json\n'
    "else\n"
    '  bd show "$1" --json\n'
    "fi"
)

# This repo's own wrapper. The case that already passed, kept so the widening is
# shown not to have broken it.
_THIS_REPO_LITERAL = (
    "if command -v with-livespec-env.sh >/dev/null 2>&1; then\n"
    '  with-livespec-env.sh -- bd show "$1" --json\n'
    "else\n"
    '  bd show "$1" --json\n'
    "fi"
)

# The genuine defect: a `bd` call with no wrapper anywhere.
_UNWRAPPED = "ledger_anchor='overseer-yho'\nbd show \"$ledger_anchor\" --json || exit 1"


def _fenced(*, body: str) -> str:
    return "```sh\n" + body + "\n```"


def test_a_config_driven_wrapper_is_recognised() -> None:
    """THE FIX. `homelab`'s shape must be clean -- it is the better form.

    Sabotage that reddens this: re-pin `_WRAPPER_DETECTED` to the literal
    `with-livespec-env.sh`.
    """
    assert wrapper_less_ledger_read(text=_fenced(body=_CONFIG_DRIVEN)) == []


def test_another_repos_named_wrapper_is_recognised() -> None:
    """A wrapper this repo will never be named after is still a wrapper.

    Sabotage that reddens this: narrow the wrapper pattern back to `livespec`.
    """
    assert wrapper_less_ledger_read(text=_fenced(body=_OTHER_REPO_LITERAL)) == []


def test_this_repos_wrapper_is_still_recognised() -> None:
    """THE REGRESSION CONTROL. Widening must not drop the case that worked.

    Sabotage that reddens this: require a repo name other than `livespec`.
    """
    assert wrapper_less_ledger_read(text=_fenced(body=_THIS_REPO_LITERAL)) == []


def test_a_bare_bd_with_no_wrapper_is_still_a_defect() -> None:
    """THE POSITIVE CONTROL. The detector must not have been widened into silence.

    Every test above asserts an EMPTY result, so a detector that returned `[]`
    unconditionally would satisfy all of them. This is the one that fails if the
    widening went too far.

    Sabotage that reddens this: return `[]` from `wrapper_less_ledger_read`.
    """
    assert wrapper_less_ledger_read(text=_fenced(body=_UNWRAPPED)) != []


def test_an_unrelated_command_v_does_not_clear_a_bare_bd() -> None:
    """The variable PROVED must be the variable USED.

    Otherwise any charter that happens to probe for some other binary would clear
    the detector for free, and `(h)` would become unfailable. This is the clause
    that keeps the variable form honest.

    Sabotage that reddens this: accept any `command -v "$var"` regardless of
    which variable invokes `bd`.
    """
    decoy = (
        'if command -v "$some_other_tool" >/dev/null 2>&1; then\n'
        '  echo "found"\n'
        "fi\n"
        'bd show "$1" --json'
    )
    assert wrapper_less_ledger_read(text=_fenced(body=decoy)) != []


def test_a_wrapper_variable_proved_but_never_used_does_not_clear() -> None:
    """Detecting a wrapper and then not invoking `bd` through it is the defect.

    The charter that proves a wrapper exists and then calls `bd` bare has done
    the check and ignored the answer -- which is worse than not checking, because
    it reads as diligence.

    Sabotage that reddens this: clear on `command -v "$w"` alone.
    """
    proved_unused = (
        'ledger_wrapper="with-homelab-env.sh"\n'
        'if command -v "$ledger_wrapper" >/dev/null 2>&1; then\n'
        '  echo "wrapper present"\n'
        "fi\n"
        'bd show "$1" --json'
    )
    assert wrapper_less_ledger_read(text=_fenced(body=proved_unused)) != []
