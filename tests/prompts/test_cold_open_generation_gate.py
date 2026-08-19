"""Cold-open generated-prompt gate for overseer-lf7ieb.

The contract here is narrower than the older known-defect sweep: a fresh reader
with only the generated handoff layers must be able to run the boot commands
without guessing. The validator therefore reads the binder's declared bindings,
resolves composed bindings to a fixed point, leaves declared runtime slots alone,
scans fenced shell blocks only, and executes the substituted shell under stubs.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SHARED_LAYER = _REPO_ROOT / ".ai" / "supervisor-protocol.md"
_BINDER = _REPO_ROOT / "tests" / "prompts" / "fixtures" / "exemplar-supervisor-handoff.md"
_GENERATOR_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"

_FENCE = re.compile(
    r"^[ \t]*(`{3,}|~{3,})([^\n]*)\n(.*?)^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL
)
_BINDING_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]*)`\s*\|", re.MULTILINE)
_PLACEHOLDER = re.compile(r"<[A-Za-z0-9_| -]+>")
_BOOT_LINE = re.compile(r"^[^#\n]*\bBOOT:", re.MULTILINE)
_SLEEP_WAIT = re.compile(r"\b(?:while|until)\b[\s\S]*\bsleep\b")
_DECLARATION_MARKER = "Placeholder classes declared by this binder:"

_RUNTIME_SLOTS = frozenset(("<condition-command>", "<short-slug>", "<branch>"))


def _shell_blocks(*, text: str) -> list[str]:
    blocks: list[str] = []
    for match in _FENCE.finditer(text):
        language = match.group(2).strip().split(maxsplit=1)[0]
        if language in {"sh", "bash"}:
            blocks.append(match.group(3))
    return blocks


def _bindings(*, text: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _BINDING_ROW.finditer(text)}


def _aliases_for(*, bindings: dict[str, str]) -> dict[str, str]:
    aliases = dict(bindings)
    aliases.update({name.replace("_", "-"): value for name, value in bindings.items()})
    return aliases


def _resolve_to_fixed_point(*, value: str, bindings: dict[str, str]) -> str:
    aliases = _aliases_for(bindings=bindings)
    resolved = value
    for _ in range(len(aliases) + 1):
        previous = resolved
        for name, replacement in aliases.items():
            resolved = resolved.replace(f"<{name}>", replacement)
        if resolved == previous:
            return resolved
    # Defensive ceiling for future resolver changes; current cycles stabilize within a pass.
    return resolved  # pragma: no cover


def _resolved_bindings(*, text: str, repo_primary: Path) -> dict[str, str]:
    declared = _bindings(text=text)
    declared["repo_primary"] = str(repo_primary)
    return {
        name: _resolve_to_fixed_point(value=value, bindings=declared)
        for name, value in declared.items()
    }


def _substitute(*, block: str, bindings: dict[str, str]) -> str:
    substituted = block
    for name, value in _aliases_for(bindings=bindings).items():
        substituted = substituted.replace(f"<{name}>", value)
    return substituted


def _remaining_generation_placeholders(*, block: str) -> list[str]:
    return sorted({token for token in _PLACEHOLDER.findall(block) if token not in _RUNTIME_SLOTS})


def _placeholder_declaration_findings(*, text: str) -> list[str]:
    declaration_at = text.find(_DECLARATION_MARKER)
    if declaration_at == -1:
        return ["placeholder-declaration-missing"]
    declaration = text[declaration_at:]
    missing = [slot for slot in sorted(_RUNTIME_SLOTS) if slot not in declaration]
    if missing:
        return ["placeholder-runtime-slots-incomplete: " + ", ".join(missing)]
    required_words = ("Concretely bound", "Composed bindings", "Runtime slots", "Illustrative")
    absent = [word for word in required_words if word.lower() not in declaration.lower()]
    if absent:
        return ["placeholder-classes-incomplete: " + ", ".join(absent)]
    return []


def _boot_findings(*, text: str) -> list[str]:
    shell = "\n".join(_shell_blocks(text=text))
    if _BOOT_LINE.search(shell) is None:
        return ["boot-brief-is-not-command"]
    return []


def _wait_channel_findings(*, text: str) -> list[str]:
    shell = "\n".join(_shell_blocks(text=text))
    if "wait_channel" not in text:
        return []
    has_bootstrap = "mkdir -p" in shell and ': > "$wait_channel"' in shell
    has_feed_instruction = 'append one line to "$wait_channel" at every milestone' in shell
    if has_bootstrap and has_feed_instruction:
        return []
    return ["wait-channel-not-created-and-fed"]


def _unbounded_wait_findings(*, text: str) -> list[str]:
    findings: list[str] = []
    for block in _shell_blocks(text=text):
        if _SLEEP_WAIT.search(block) and "$(seq" not in block and "timeout" not in block:
            findings.append("unbounded-agent-ui-wait")
    return findings


def _halt_remedy_findings(*, text: str) -> list[str]:
    findings: list[str] = []
    for block in _shell_blocks(text=text):
        if "HALT:" in block and "REMEDY:" not in block:
            findings.append("halt-precondition-has-no-remedy")
    return findings


def _false_placeholder_claim_findings(*, text: str) -> list[str]:
    lowered = text.lower()
    if "only placeholder" not in lowered:
        return []
    declaration = text[text.find(_DECLARATION_MARKER) :] if _DECLARATION_MARKER in text else ""
    runtime_count = sum(1 for slot in _RUNTIME_SLOTS if slot in declaration)
    if runtime_count > 1:
        return ["false-only-placeholder-claim"]
    return []


def _env_safe_bindings(*, bindings: dict[str, str]) -> dict[str, str]:
    """Bindings whose names are usable as SHELL VARIABLE names.

    The binder's table is free-form markdown, so a binding name is whatever sits
    in backticks in the first column. Exporting one that is not an identifier
    would put a name into the environment that no `$name` expansion can ever read
    — silently, and looking exactly like a binding that did get through.
    """
    return {name: value for name, value in bindings.items() if name.replace("_", "").isalnum()}


def _write_executable(*, path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _stub_path(*, tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    _write_executable(
        path=bin_dir / "tmux",
        body="""#!/bin/sh
case "$*" in
  *supervisor-prompt-quality-supervisor*pane_pid*) printf '%s\n' 101 ;;
  *pane_pid*) printf '%s\n' 100 ;;
  *pane_current_path*) printf '%s\n' "$COLD_OPEN_REPO" ;;
  *capture-pane*) printf '%s\n' PANE ;;
  *list-sessions*) printf '%s\n' supervisor-prompt-quality-supervisor ;;
esac
exit 0
""",
    )
    # `bd` reaches the LEDGER. It is STUBBED rather than classified out of the
    # execution leg, for exactly the reason `tmux` is: this gate's design is that
    # every emitted block must EXECUTE, and the way it holds that for a block
    # touching live external state is to stand in for the tool. Classifying
    # ledger blocks out instead would stop the gate checking the one instruction
    # the "a filed item is a claim with a timestamp" rule requires the charter to
    # carry.
    #
    # DISCRIMINATING ON PURPOSE — a blanket `exit 0` would remove the teeth. The
    # shipped form is `bd show <anchor> --json`; a missing subcommand, a missing
    # or option-shaped anchor, or a missing `--json` all exit 1, so a malformed
    # ledger re-measure is still reported as not executing.
    _write_executable(
        path=bin_dir / "bd",
        body="""#!/bin/sh
[ "$1" = "show" ] || exit 1
case "$2" in "" | -*) exit 1 ;; esac
case "$*" in *--json*) ;; *) exit 1 ;; esac
printf '%s\n' '{"id":"stub","status":"open"}'
""",
    )
    # The charter now reaches the ledger THROUGH the fleet credential wrapper,
    # detected with `command -v`. That detection searches the WHOLE PATH, and the
    # stub dir is only PREPENDED — so without a stub here it finds the REAL
    # `/usr/local/bin/with-livespec-env.sh`, which attempts a real credential
    # fetch and BLOCKS until this gate's 2-second execution deadline kills it.
    # Observed exactly that on 2026-07-30 while deploying the wrapper fix.
    #
    # The stub models the wrapper HONESTLY: strip a leading `--` and exec the rest,
    # which is what the real wrapper does once it has injected credentials. So the
    # wrapped `bd` still resolves to the discriminating stub below and keeps its
    # teeth. A stub that merely exited 0 would retire the ledger execution leg —
    # the same blanket-pass mistake the `bd` stub's own comment warns against.
    _write_executable(
        path=bin_dir / "with-livespec-env.sh",
        body="""#!/bin/sh
[ "$1" = "--" ] && shift
exec "$@"
""",
    )
    _write_executable(path=bin_dir / "ps", body="#!/bin/sh\nprintf '%s\n' '100 claude claude'\n")
    _write_executable(path=bin_dir / "sleep", body="#!/bin/sh\nexit 0\n")
    _write_executable(path=bin_dir / "seq", body="#!/bin/sh\nprintf '1\n'\n")
    return bin_dir


def _unresolved_placeholder_findings(*, text: str, repo_primary: Path) -> list[str]:
    bindings = _resolved_bindings(text=text, repo_primary=repo_primary)
    findings: list[str] = []
    declared_repo = _bindings(text=text).get("repo_primary")
    for index, block in enumerate(_shell_blocks(text=text), start=1):
        substituted = _substitute(block=block, bindings=bindings)
        if declared_repo is not None:
            substituted = substituted.replace(declared_repo, str(repo_primary))
        remaining = _remaining_generation_placeholders(block=substituted)
        if remaining:
            findings.append(f"unsubstituted-generation-placeholder:block-{index}: {remaining[0]}")
    return findings


def _execution_findings(*, text: str, repo_primary: Path, tmp_path: Path) -> list[str]:
    bindings = _resolved_bindings(text=text, repo_primary=repo_primary)
    env = os.environ.copy()
    env["COLD_OPEN_REPO"] = str(repo_primary)
    env["PATH"] = str(_stub_path(tmp_path=tmp_path)) + os.pathsep + env["PATH"]
    # FABRICATE HOME, for the same reason the repo and the tool stubs are
    # fabricated: this gate asserts that emitted blocks EXECUTE, and that verdict
    # must not depend on what the machine running it happens to have installed.
    # The provenance block reads `$HOME/.claude/plugins/cache/...`, so with the
    # real HOME the gate said "executes" on a developer box holding a plugin
    # cache and "does not execute" on a CI runner without one — the same answer
    # differing by environment, which is exactly what a static gate must not do.
    # An empty HOME is the honest fixture: no cache, so the block takes its
    # cannot-verify branch deterministically everywhere. What that branch SKIPS
    # is covered by `test_provenance_check_discriminates.py`, which fabricates
    # each cache state and runs the block against all four.
    fabricated_home = tmp_path / "home"
    fabricated_home.mkdir(exist_ok=True)
    env["HOME"] = str(fabricated_home)
    # EXPORT THE RESOLVED BINDINGS as shell variables. The charter's own Bindings
    # section says to "resolve and REPORT these before driving anything", so a
    # cold-open supervisor has them bound by the time it runs any block; a harness
    # that leaves them unset is not modelling a cold open, it is modelling a
    # supervisor who skipped the first instruction.
    #
    # THIS WAS LATENT UNTIL THE BOOT BLOCK LEARNED TO FAIL. The previous block read
    # `test ! -f "$supervisor_marker" || sed ...`, and `test ! -f ""` is TRUE, so
    # with the binding unset the block SHORT-CIRCUITED, printed nothing and exited
    # 0 — and this gate recorded that as executing. The gate was green because the
    # block did nothing. Now that an unset binding HALTs, the omission surfaces.
    # A gate that asserts "exits 0" is satisfied by a command that does nothing,
    # which is the same blind spot as a stub standing in for a working tool.
    env.update(_env_safe_bindings(bindings=bindings))
    (tmp_path / ".ai").mkdir(exist_ok=True)
    (tmp_path / ".ai" / "supervisor-protocol.md").write_text("shared\n", encoding="utf-8")
    (repo_primary / "plan" / "supervisor-prompt-quality").mkdir(parents=True, exist_ok=True)
    findings: list[str] = []
    for index, block in enumerate(_shell_blocks(text=text), start=1):
        substituted = _substitute(block=block, bindings=bindings)
        declared_repo = _bindings(text=text).get("repo_primary")
        if declared_repo is not None:
            substituted = substituted.replace(declared_repo, str(repo_primary))
        result = subprocess.run(  # noqa: S603
            ["bash", "-c", substituted],  # noqa: S607
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode != 0:
            findings.append(f"command-does-not-execute:block-{index}: rc={result.returncode}")
    return findings


def cold_open_findings(*, text: str, repo_primary: Path, tmp_path: Path) -> list[str]:
    findings: list[str] = []
    findings.extend(_placeholder_declaration_findings(text=text))
    findings.extend(_boot_findings(text=text))
    findings.extend(_wait_channel_findings(text=text))
    findings.extend(_unbounded_wait_findings(text=text))
    findings.extend(_halt_remedy_findings(text=text))
    findings.extend(_false_placeholder_claim_findings(text=text))
    findings.extend(_unresolved_placeholder_findings(text=text, repo_primary=repo_primary))
    if findings:
        return findings
    findings.extend(_execution_findings(text=text, repo_primary=repo_primary, tmp_path=tmp_path))
    return findings


def _clean_charter() -> str:
    return "\n\n".join(
        (_SHARED_LAYER.read_text(encoding="utf-8"), _BINDER.read_text(encoding="utf-8"))
    )


def _fixture() -> str:
    return """
# Supervisor Handoff - supervisor-prompt-quality

## Shared Protocol

```sh
test -f ".ai/supervisor-protocol.md" \
  || { echo "HALT: missing shared supervisor protocol"; echo "REMEDY: regenerate handoff"; exit 1; }
printf '%s\n' "BOOT: read shared protocol, binder, and marker"
```

## Bindings

| Binding | Value |
|---|---|
| `repo_primary` | `/repo` |
| `thread_dir` | `plan/supervisor-prompt-quality/` |
| `topic` | `supervisor-prompt-quality` |
| `worker_session` | `supervisor-prompt-quality` |
| `supervisor_session` | `supervisor-prompt-quality-supervisor` |
| `WORKER_TARGET` | `'=supervisor-prompt-quality:'` |
| `SUPERVISOR_TARGET` | `'=supervisor-prompt-quality-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/<topic>/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-lf7ieb` |

Placeholder classes declared by this binder:

- Concretely bound: `repo_primary`, `thread_dir`, `topic`, `worker_session`,
  `supervisor_session`, `WORKER_TARGET`, `SUPERVISOR_TARGET`, `ledger_anchor`.
- Composed bindings resolved to a fixed point: `runtime_dir`,
  `supervisor_marker`, `wait_channel`.
- Runtime slots intentionally left for later commands: `<condition-command>`,
  `<short-slug>`, `<branch>`.
- Illustrative placeholders appear only in prose that discusses a form, not in
  fenced commands.

`-t <name>` is illustrative prose and must not be scanned as code.

## HALT-first preconditions

```sh
WORKER_TARGET='=<worker-session>:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session"; echo "REMEDY: ask whether to start it"; exit 1; }
```

## Never end a turn without an armed re-entry

```sh
WORKER_TARGET='=<worker-session>:'
wait_channel=<runtime_dir>/worker-status.log
mkdir -p "$(dirname "$wait_channel")"
: > "$wait_channel"
# Tell the worker: append one line to "$wait_channel" at every milestone.
prev="__OVERSEER_NO_CAPTURE_YET__"; stable=0
for i in $(seq 1 180); do
  sleep 20
  pane=$(tmux capture-pane -p -t "$WORKER_TARGET")
  [ -z "$pane" ] && { echo "WAKE: pane unreadable - session may be gone"; exit 0; }
  if [ "$pane" = "$prev" ]; then stable=$((stable+1)); else stable=0; prev="$pane"; fi
done
echo "WAKE: watcher ceiling reached - worker still busy, RE-ARM NOW"
```

```sh
tmux send-keys -t "$WORKER_TARGET" -- '<condition-command>'
```
"""


def _fixture_for_topic(*, topic: str) -> str:
    return _fixture().replace("supervisor-prompt-quality", topic)


def _with_distinct_pane_precondition(
    *, text: str, worker_target: str, supervisor_target: str
) -> str:
    return text.replace(
        "```sh\n" "tmux send-keys -t \"$WORKER_TARGET\" -- '<condition-command>'\n" "```",
        "```sh\n"
        f"WORKER_TARGET='{worker_target}'\n"
        f"SUPERVISOR_TARGET='{supervisor_target}'\n"
        "pane_pid=$(tmux display-message -p -t \"$WORKER_TARGET\" '#{pane_pid}')\n"
        'supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '
        "'#{pane_pid}')\n"
        '[ "$supervisor_pane_pid" != "$pane_pid" ] \\\n'
        '  || { echo "HALT: supervisor and worker resolve to the SAME pane"; '
        'echo "REMEDY: re-check both exact targets"; exit 1; }\n'
        "```\n"
        "\n"
        "```sh\n"
        "tmux send-keys -t \"$WORKER_TARGET\" -- '<condition-command>'\n"
        "```",
    )


def _repo(*, tmp_path: Path) -> Path:
    return tmp_path / "repo"


def test_current_generated_layers_are_cold_open_clean(*, tmp_path: Path) -> None:
    assert (
        cold_open_findings(
            text=_clean_charter(), repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path
        )
        == []
    )


def test_generator_prose_declares_the_four_placeholder_classes() -> None:
    prose = _GENERATOR_PROSE.read_text(encoding="utf-8")
    assert "concretely bound placeholders" in prose
    assert "composed bindings" in prose
    assert "runtime slots" in prose
    assert "illustrative placeholders" in prose
    assert all(slot in prose for slot in _RUNTIME_SLOTS)
    assert "cold-open boot command" in prose
    assert "BOOT: read .ai/supervisor-protocol.md" in prose


def test_fixed_point_substitution_accepts_composed_bindings_and_runtime_slots(
    *, tmp_path: Path
) -> None:
    text = _fixture()
    findings = cold_open_findings(
        text=text, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path
    )
    assert findings == []


def test_non_exemplar_charter_distinct_pane_guard_is_cold_open_clean(*, tmp_path: Path) -> None:
    text = _with_distinct_pane_precondition(
        text=_fixture_for_topic(topic="daemon-liveness-truth"),
        worker_target="=daemon-liveness-truth:",
        supervisor_target="=daemon-liveness-truth-supervisor:",
    )
    findings = cold_open_findings(
        text=text, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path
    )

    assert findings == []


def test_same_pane_distinct_pane_guard_still_halts(*, tmp_path: Path) -> None:
    text = _with_distinct_pane_precondition(
        text=_fixture_for_topic(topic="single-pane-topic"),
        worker_target="=single-pane-topic:",
        supervisor_target="=single-pane-topic:",
    )
    findings = cold_open_findings(
        text=text, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path
    )

    assert findings == ["command-does-not-execute:block-4: rc=1"]


def test_illustrative_placeholders_in_prose_are_out_of_scope(*, tmp_path: Path) -> None:
    text = _fixture() + "\nThe banned one-shot form is `... -- '<line>' Enter`.\n"
    findings = cold_open_findings(
        text=text, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path
    )
    assert findings == []


def test_cold_open_defect_classes_do_not_cross_fire(*, tmp_path: Path) -> None:
    base = _fixture()
    cases = {
        "unsubstituted-generation-placeholder": base.replace(
            "tmux send-keys -t \"$WORKER_TARGET\" -- '<condition-command>'",
            "tmux send-keys -t \"$WORKER_TARGET\" -- '<workdir>'",
        ),
        "wait-channel-not-created-and-fed": base.replace(': > "$wait_channel"', "# missing seed"),
        "boot-brief-is-not-command": base.replace(
            "BOOT: read shared protocol, binder, and marker",
            "cold open guidance is present only as prose",
        ),
        "unbounded-agent-ui-wait": base.replace(
            "for i in $(seq 1 180); do",
            "while true; do",
        ).replace(
            'done\necho "WAKE: watcher ceiling reached - worker still busy, RE-ARM NOW"',
            "done",
        ),
        "halt-precondition-has-no-remedy": base.replace(
            '; echo "REMEDY: ask whether to start it"',
            "",
        ),
        "false-only-placeholder-claim": base.replace(
            "Placeholder classes declared by this binder:",
            (
                "The only placeholder is `<condition-command>`.\n\n"
                "Placeholder classes declared by this binder:"
            ),
        ),
    }
    assert (
        cold_open_findings(text=base, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path)
        == []
    )
    for expected, text in cases.items():
        found = cold_open_findings(
            text=text, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path
        )
        assert found == [expected] or (
            len(found) == 1 and found[0].startswith(expected + ":")
        ), f"{expected} cross-fired: {found}"


def test_shell_command_execution_failure_is_reported_after_placeholder_substitution(
    *, tmp_path: Path
) -> None:
    text = _fixture().replace("tmux has-session", "missing-cold-open-command")
    found = cold_open_findings(text=text, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path)
    assert any(finding.startswith("command-does-not-execute:") for finding in found)


def test_placeholder_declaration_edge_findings_are_named() -> None:
    assert _resolve_to_fixed_point(value="<a>", bindings={"a": "<b>", "b": "<a>"}) == "<a>"
    assert _placeholder_declaration_findings(text="no declaration") == [
        "placeholder-declaration-missing"
    ]
    incomplete_runtime = _DECLARATION_MARKER + "\nRuntime slots: <condition-command>"
    assert _placeholder_declaration_findings(text=incomplete_runtime) == [
        "placeholder-runtime-slots-incomplete: <branch>, <short-slug>"
    ]
    incomplete_classes = _DECLARATION_MARKER + "\n" + " ".join(sorted(_RUNTIME_SLOTS))
    assert _placeholder_declaration_findings(text=incomplete_classes) == [
        "placeholder-classes-incomplete: Concretely bound, Composed bindings, "
        "Runtime slots, Illustrative"
    ]


def test_optional_wait_channel_and_placeholder_claim_controls() -> None:
    assert _wait_channel_findings(text="```sh\nprintf '%s\n' BOOT\n```") == []
    assert (
        _false_placeholder_claim_findings(text="the only placeholder is <condition-command>") == []
    )


def test_substitution_and_execution_do_not_require_a_repo_binding(*, tmp_path: Path) -> None:
    text = """
# Supervisor Handoff - demo

## Bindings

Placeholder classes declared by this binder:

- Concretely bound: none.
- Composed bindings: none.
- Runtime slots: <condition-command>, <short-slug>, <branch>.
- Illustrative placeholders: none.

```sh
printf '%s\n' "BOOT: no repo binding needed"
printf '%s\n' '<condition-command>'
```
"""
    repo = _repo(tmp_path=tmp_path)
    assert _unresolved_placeholder_findings(text=text, repo_primary=repo) == []
    assert _execution_findings(text=text, repo_primary=repo, tmp_path=tmp_path) == []


def test_bash_is_available_for_the_execution_leg() -> None:
    assert shutil.which("bash") is not None


def test_the_ledger_stub_discriminates_a_malformed_re_measure(*, tmp_path: Path) -> None:
    """The `bd` stub must NOT be a blanket pass.

    Standing in for a tool the harness cannot reach is how this gate keeps
    executing external-state blocks. The risk is that the stand-in accepts
    anything, which would silently retire the execution leg for every ledger
    block. Each mutation below is a real way to get the re-measure wrong, and each
    must still be reported as not executing.

    Sabotage that reddens this: replace the stub body with `exit 0`.

    THE MUTATION TARGET MOVED, and the way it moved is the point. The charter used
    to invoke `bd show "$ledger_anchor" --json` inline; it now calls a
    `ledger_show()` helper that detects the credential wrapper, so the literal is
    `bd show "$1" --json` and appears TWICE — once behind the wrapper and once in
    the bare fallback. `str.replace` mutates both, which is what we want: a
    discriminating stub must reject a malformed re-measure on EITHER path.

    The `assert text != _clean_charter()` guard below is why this was caught
    rather than silently retired. When the charter changed shape the old literal
    stopped matching, every mutation became a no-op, and all three cases would
    have "passed" against an UNMUTATED charter — a test that proves nothing while
    reporting green. That guard is doing the same job here that
    `test_this_repo_has_charters_to_scan` does for the sibling gate.
    """
    for broken in (
        "bd show --json",  # anchor missing, option consumed as the anchor
        'bd show "$1"',  # no --json, so nothing is machine-readable
        'bd shwo "$1" --json',  # subcommand typo
    ):
        text = _clean_charter().replace('bd show "$1" --json', broken)
        assert text != _clean_charter(), f"mutation did not apply: {broken}"
        found = cold_open_findings(
            text=text, repo_primary=_repo(tmp_path=tmp_path), tmp_path=tmp_path
        )
        assert any(
            f.startswith("command-does-not-execute:") for f in found
        ), f"the stub accepted a malformed ledger re-measure: {broken}"


def test_a_boot_block_whose_binding_is_unset_is_reported_as_not_executing(
    *, tmp_path: Path
) -> None:
    """The binding export is LOAD-BEARING and must not be quietly removed.

    A cold-open supervisor resolves the Bindings table first, so the harness binds
    them too. Strip that and the boot block HALTs on an unset `supervisor_marker`
    — which is the correct behaviour of the charter and must be reported here as a
    finding, not absorbed silently.

    WHY THIS TEST EXISTS AT ALL. Before the boot block learned to fail, an unset
    binding made it short-circuit on `test ! -f ""` and exit 0, and this gate
    called that executing. The gate asserts a block EXITS 0; a block that does
    nothing also exits 0. This pins the one case where that difference was
    actually observed, so a future change cannot restore the no-op and still read
    as green.
    """
    text = _clean_charter()
    bindings = _resolved_bindings(text=text, repo_primary=_repo(tmp_path=tmp_path))
    assert "supervisor_marker" in bindings, "the binder must declare supervisor_marker"

    boot_blocks = [b for b in _shell_blocks(text=text) if "$supervisor_marker" in b]
    assert boot_blocks != [], "no block reads the supervisor marker — mutation is vacuous"

    # Satisfy the block's FIRST precondition so the run reaches the marker guard.
    # Without this the shared-layer check HALTs earlier and the test would pass for
    # the wrong reason — a green that proves a different guard fired.
    (tmp_path / ".ai").mkdir(exist_ok=True)
    (tmp_path / ".ai" / "supervisor-protocol.md").write_text("shared\n", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(_stub_path(tmp_path=tmp_path)) + os.pathsep + env["PATH"]
    env.pop("supervisor_marker", None)
    completed = subprocess.run(  # noqa: S603
        ["bash", "-c", boot_blocks[0]],  # noqa: S607
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert completed.returncode != 0, "an unset marker binding must HALT, not no-op at rc 0"
    assert "HALT: supervisor_marker is unset" in completed.stdout


def test_a_binding_name_that_is_not_a_shell_identifier_is_not_exported() -> None:
    """A name `$name` could never expand must not reach the environment.

    Exporting it would look identical to a binding that got through, so the block
    would fail on an unset variable while the harness believed it was bound.
    """
    assert _env_safe_bindings(bindings={"supervisor_marker": "/m", "not-an-ident": "x"}) == {
        "supervisor_marker": "/m"
    }
