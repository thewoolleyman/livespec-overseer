"""Detector (h) must recognise a credential wrapper it cannot name in advance.

THE FALSE POSITIVE, MEASURED. `(h)` pinned the literal string
`with-livespec-env.sh`. `homelab` declared a DIFFERENT wrapper --
`with-homelab-env.sh` at the time -- and its charters resolve it from the repo's
own `.livespec.jsonc` rather than hard-coding any name at all:

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

AND THE FIRST FIX WAS STILL A NAME. Widening the literal to the pattern
`with-<something>-env.sh` bought exactly one convention, and `homelab` then left
it: its `credential_wrapper` is now a multi-element scoped-injection argv headed
by `with-homelab-aws.sh` -- an `-aws.sh`, not an `-env.sh`. Measured 2026-08-06
against homelab's live `.livespec.jsonc`, the pattern scored that CORRECT call as
a defect. That is the ORIGINAL false positive, returned under a new spelling, in
the same repo, for the same reason: the rule keyed on what the wrapper is CALLED.
Widening again to `-(env|aws)\\.sh` would buy one more rename and re-arm the trap.

THE RULE IS NOW A PROPERTY, NOT A NAME, which is what makes it survive the next
repo. A `bd` call is wrapped when the charter EITHER

  * invokes `bd` through the wrapper THE REPO ITSELF DECLARES in its own
    `.livespec.jsonc` -- resolved at scan time, whatever it is called and however
    many argv elements it carries -- or
  * names a `with-<something>-env.sh` wrapper -- any fleet member's, not just
    this one's -- or
  * binds a wrapper to a VARIABLE, proves it with `command -v`, and invokes `bd`
    THROUGH THAT SAME VARIABLE.

The last clause deliberately requires both halves of the same variable. A
charter cannot clear the detector by running `command -v` on something unrelated,
because the binding it proves must also be the binding it calls.

The first clause reads only the argv HEAD. The rest of a scoped-injection chain
is that wrapper's own flags -- `--role`, `--bind`, `--` -- and keying on those
would clear almost any line that mentioned one.
"""

from __future__ import annotations

from pathlib import Path

from test_charters_carry_no_known_defects import (
    declared_wrapper_tokens,
    wrapper_less_ledger_read,
)

__all__: list[str] = []

# `homelab`'s post-migration `credential_wrapper`, argv head plus basename --
# the shape `declared_wrapper_tokens` returns. Spelled out rather than read from
# homelab's live config: this repo's CI has no sibling checkout, and a test that
# silently skips when one is absent proves nothing.
_HOMELAB_TOKENS = frozenset({"/usr/local/bin/with-homelab-aws.sh", "with-homelab-aws.sh"})
_LIVESPEC_TOKENS = frozenset({"/usr/local/bin/with-livespec-env.sh", "with-livespec-env.sh"})

# The scoped-injection chain as a charter would write it. Note it matches NO
# `with-<x>-env.sh` pattern and binds no shell variable, so both pre-existing
# clauses miss it.
_SCOPED_INJECTION = (
    "ledger_anchor='hl-ye2ndp'\n"
    "/usr/local/bin/with-homelab-aws.sh --role homelab-workload \\\n"
    "  /home/ubuntu/.nix-profile/bin/hl param run \\\n"
    "  --bind BEADS_DOLT_PASSWORD=/homelab/v1/services/dolt/production/beads-password \\\n"
    '  -- bd show "$ledger_anchor" --json'
)

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


def test_a_wrapper_split_across_a_continuation_is_recognised() -> None:
    """A trailing backslash does not stop a wrapper from wrapping.

    `livespec-orchestrator-beads-fabro`'s live `beads-v1-1-2-upgrade` charter
    writes the correct call across two physical lines:

        with-livespec-env.sh -- \\
          /usr/local/bin/bd show "$ledger_anchor" --json

    which is the SAME COMMAND as the one-liner and was scored as a defect purely
    because the pattern required both halves on one physical line. Measured: the
    one-line spelling returns clean and the continued spelling returns a finding.
    Remediating that would have meant reflowing correct shell to satisfy the
    detector -- the same inversion `(h)`'s hard-coded name already caused once.

    Sabotage that reddens this: match against the raw text instead of the
    continuation-joined text.
    """
    continued = (
        "/data/projects/1password-env-wrapper/with-livespec-env.sh -- \\\n"
        '  /usr/local/bin/bd show "$ledger_anchor" --json'
    )
    assert wrapper_less_ledger_read(text=_fenced(body=continued)) == []


def test_a_declared_wrapper_outside_the_naming_convention_is_recognised() -> None:
    """THE SECOND FIX. `homelab`'s post-migration chain must be clean.

    It is named `-aws.sh`, spans four physical lines, and binds no variable, so
    it clears via the DECLARED clause or not at all.

    Sabotage that reddens this: drop the declared-wrapper clause from
    `wrapper_less_ledger_read`.
    """
    assert (
        wrapper_less_ledger_read(
            text=_fenced(body=_SCOPED_INJECTION), wrapper_tokens=_HOMELAB_TOKENS
        )
        == []
    )


def test_the_same_chain_is_a_defect_under_a_different_declared_wrapper() -> None:
    """THE DISCRIMINATION. Identical text, one token set apart.

    The test above asserts an empty result and would be satisfied by a clause
    that cleared everything. This one holds the charter text FIXED and changes
    only what the repo declares, so what it measures is the declaration -- not
    some incidental property of the chain. A repo declaring the livespec wrapper
    has not wrapped `bd` by running homelab's.

    Sabotage that reddens this: clear whenever `wrapper_tokens` is non-empty,
    without checking the tokens appear beside the `bd` call.
    """
    assert (
        wrapper_less_ledger_read(
            text=_fenced(body=_SCOPED_INJECTION), wrapper_tokens=_LIVESPEC_TOKENS
        )
        != []
    )


def test_a_declared_wrapper_named_far_from_the_bd_call_does_not_clear() -> None:
    """Mentioning the wrapper is not invoking it.

    A charter that names its wrapper in one command and then calls `bd` bare in
    another has done nothing for the call that matters -- the same failure the
    proved-but-unused variable form is rejected for.

    Sabotage that reddens this: search the whole joined block for a token
    instead of the line carrying the `bd` invocation.
    """
    elsewhere = (
        "/usr/local/bin/with-homelab-aws.sh --role homelab-workload -- true\n"
        'bd show "$ledger_anchor" --json'
    )
    assert (
        wrapper_less_ledger_read(text=_fenced(body=elsewhere), wrapper_tokens=_HOMELAB_TOKENS) != []
    )


def test_declared_wrapper_tokens_reads_this_repos_own_config() -> None:
    """The resolution is real: it reads `.livespec.jsonc`, comments and all.

    Without this, every test above could pass against a token set that is only
    ever supplied by a test, and the production path would be unexercised.

    Sabotage that reddens this: return `frozenset()` unconditionally.
    """
    assert "with-livespec-env.sh" in declared_wrapper_tokens()


def test_a_repo_declaring_no_wrapper_yields_no_tokens(tmp_path: Path) -> None:
    """An adopter without a wrapper must not be scored against one.

    Both ways of having none are covered: no config file at all, and a config
    that simply omits the key. Either must be an empty set rather than a crash
    or a stray token, because an empty set falls through to the other clauses.

    Sabotage that reddens this: treat a missing key as an empty-string token.
    """
    assert declared_wrapper_tokens(repo_root=tmp_path) == frozenset()
    (tmp_path / ".livespec.jsonc").write_text(
        '// a comment\n{"template": "livespec"}\n', encoding="utf-8"
    )
    assert declared_wrapper_tokens(repo_root=tmp_path) == frozenset()


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
