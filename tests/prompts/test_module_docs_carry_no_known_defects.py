"""The `overseer/` MODULE DOCS must carry none of the known defect classes.

THE THIRD PROSE SURFACE, and the last one nothing scanned. The charter gate
reads charters that were already EMITTED; `test_generator_prose_is_defect_free`
reads the template they are emitted FROM. Neither reads the documents a
MAINTAINER follows by hand -- and this repo's own `.claude/CLAUDE.md` names all
three of them authoritative: "Read these beside the code before changing
anything in `overseer/`."

MEASURED 2026-08-01, and unlike the generator prose this corpus was NOT clean.
`overseer/AGENTS.md` carried TWO class-(a) instances, both inside the
reboot-recovery runbook's "Canary ONE pane first" block -- a
`respawn-pane -k -c <repo> -t <tmux-name>` and the `capture-pane -p -t
<tmux-name>` that confirms it. Both were corrected in the change that added this
module; this gate is what stops them coming back.

WHY THIS SURFACE IS WORSE THAN A CHARTER, not merely another one. A charter's
bare target is executed by an agent against a session the daemon believes is
live. The runbook's is typed by a HUMAN during a fleet-wide tmux recovery --
the one moment when the session they are naming is GONE, which is exactly when a
bare `-t` stops being harmless. tmux prefers an exact match when one exists, so
the defect is invisible in steady state and fires only in the recovery this
runbook exists for. And the offending command is `respawn-pane -k`, the single
destructive operation in the whole system.

DEMONSTRATED rather than argued, on a private socket (2026-08-01): with only
`canary-two` alive, `respawn-pane -k -t canary` returned rc=0 and ran its
command inside `canary-two`. The exact form `-t '=canary:'` refuses the same
call with rc=1, `can't find session: canary`. This host was carrying 14
session-name pairs where one name extends another at the time of measurement,
including `supervisor-prompt-quality` / `supervisor-prompt-quality-supervisor`.

THE CORRECTION THAT MADE THE FIX POSSIBLE, recorded because the doc argued
against it. That same file's gotcha list asserted that `respawn-pane` wants the
BARE name and rejects the exact-match form. Half true: `=name` (no colon) really
does fail, but `=name:` WITH the trailing colon -- the form the charter gate
mandates -- works on every subcommand this repo uses (`respawn-pane`,
`capture-pane`, `list-panes`, `send-keys`, `paste-buffer`, `has-session`). So
the doc had ruled out the safe form on the strength of a near-miss spelling, and
a gate alone would have looked wrong until that bullet was corrected too.

SCOPE, stated rather than hidden.

  - `.claude-plugin/prose/overseer.md` stays OUT, for the reasons already
    recorded in `test_generator_prose_is_defect_free`: its single (a) hit is the
    operator console's copy-pasteable `switch-client` jump command, emitted bare
    on purpose and under test. Do not re-litigate it here.
  - `plan/*/handoff.md` stays OUT. Handoffs do carry fenced commands, and one
    live class-(a) instance sits in another track's handoff today. Scanning them
    from here would redden this repo's master over a file this gate's owner may
    not edit, which is a routing problem wearing a gate's clothes.
"""

from __future__ import annotations

from pathlib import Path

from test_charters_carry_no_known_defects import _code_blocks, defects_in

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DOC_GLOB = "overseer/*.md"

# One defective line per class, in the shape the class was written for. Injected
# into a REAL module doc rather than a synthetic stub, so the control proves the
# detectors reach THESE FILES and not merely a string that resembles them.
_INJECTIONS: dict[str, str] = {
    "a": "command tmux respawn-pane -k -t overseer-worker 'claude'",
    "d": 'prev=""; stable=0',
    "g": 'just check | tail -5; echo "EXIT=${PIPESTATUS[0]}"',
    "k": "stamped=$(date -u -r \"$marker\" '+%Y-%m-%dT%H:%M:%SZ')",
}


def _module_docs() -> list[Path]:
    return sorted(_REPO_ROOT.glob(_MODULE_DOC_GLOB))


def _agents_doc() -> str:
    return (_REPO_ROOT / "overseer" / "AGENTS.md").read_text(encoding="utf-8")


def test_the_module_docs_are_present_and_carry_fenced_blocks() -> None:
    """A gate over a missing or block-free file set passes vacuously.

    The blocks are the point: the detectors read fenced code only, so a doc set
    with none of it would satisfy the gate below while proving nothing. Both
    halves are asserted because they fail differently -- a moved directory
    empties the glob, while a doc rewritten into pure prose keeps the glob full
    and silently removes everything there is to scan.

    Sabotage that reddens this: point `_MODULE_DOC_GLOB` at a path that matches
    nothing, or at a directory whose markdown carries no fenced blocks.
    """
    docs = _module_docs()
    assert docs != []
    assert [path for path in docs if _code_blocks(text=path.read_text(encoding="utf-8"))] != []


def test_every_module_doc_is_free_of_the_known_defects() -> None:
    """THE GATE. A defect reintroduced into a maintenance doc fails here.

    Nothing else looks at these files. The contract validator checks what a
    charter must CONTAIN, the cold-open gate checks that emitted blocks EXECUTE
    -- and a prefix-matching `respawn-pane` executes perfectly, in the wrong
    session.

    Sabotage that reddens this: restore a bare `-t <session>` target to any
    fenced block under `overseer/`.
    """
    offences = {
        str(path.relative_to(_REPO_ROOT)): defects_in(text=path.read_text(encoding="utf-8"))
        for path in _module_docs()
    }
    assert {path: found for path, found in offences.items() if found} == {}


def test_the_detectors_reach_these_files() -> None:
    """POSITIVE CONTROL. A clean result is worthless without one.

    Each defect is appended to the REAL `AGENTS.md` inside a fenced block and
    must be found. A control built on a synthetic stub would prove only that
    `defects_in` still works -- not that it sees THIS file, which is the claim
    the gate above actually makes. This repo has already published a zero from a
    probe that was simply pointed at the wrong text.
    """
    unreached = [
        cls
        for cls, defect in sorted(_INJECTIONS.items())
        if not [
            found
            for found in defects_in(text=_agents_doc() + "\n\n```sh\n" + defect + "\n```\n")
            if found.startswith(cls + "-")
        ]
    ]
    assert unreached == []


def test_the_recovery_runbook_targets_tmux_exactly() -> None:
    """The specific instance this module was written for, pinned by name.

    The gate above is keyed on the PROPERTY and would survive the runbook being
    rewritten or removed, which is correct but leaves nothing asserting that the
    recovery procedure itself still names sessions exactly. This is that
    assertion, and it is deliberately narrow: the destructive `respawn-pane -k`
    is the command whose mis-targeting cannot be undone.

    Sabotage that reddens this: drop the `=`/`:` from the canary block's
    `respawn-pane` target in `overseer/AGENTS.md`.
    """
    respawns = [
        line
        for block in _code_blocks(text=_agents_doc())
        for line in block.splitlines()
        if "respawn-pane" in line
    ]
    assert respawns != []
    assert [line for line in respawns if "-t '=" not in line] == []
