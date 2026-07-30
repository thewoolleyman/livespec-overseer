"""The emitted boot and ledger commands must be able to SUCCEED, not merely parse.

This module exists because the cold-open gate proves an emitted block is
WELL-FORMED, never that it can succeed. That gate stubs `bd` to validate argv
shape — `show`, a non-option anchor, `--json` — and by construction its stub
stands in for a WORKING tool, so the credential dimension is invisible to it. A
charter could therefore emit `bd show "$anchor" --json`, pass every gate, and
fail on every real cold open with "Access denied". Measured 2026-07-30.

THE CREDENTIAL FIXTURES BELOW DO NOT REPEAT THAT MISTAKE. Their `bd` stub FAILS
by default and succeeds ONLY when a credential variable is present, so the
credential is the deciding variable rather than an invisible one. A stub that
succeeded unconditionally would re-create the exact hole this module is here to
close.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"

_LEDGER_ANCHOR = "ledger_anchor='<ledger-anchor>'"
_BOOT_ANCHOR = 'test -f ".ai/supervisor-protocol.md"'

# The pre-fix form, kept verbatim so its failure is demonstrated rather than
# asserted from memory. This is what shipped, and what every deployed charter
# still carries.
_BARE_FORM = 'bd show "$ledger_anchor" --json'


def _sh_block(*, anchor: str) -> str:
    """The fenced sh block whose body starts with ``anchor``."""
    text = _PROSE.read_text(encoding="utf-8")
    match = re.search(
        r"```sh\n(" + re.escape(anchor) + r".*?)```",
        text,
        re.DOTALL,
    )
    assert match is not None, f"no fenced sh block starting with {anchor!r}"
    return match.group(1)


def _write_exec(*, path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _credential_bin(
    tmp_path: Path,
    *,
    with_wrapper: bool,
    bd_needs_credential: bool,
    bd_returns_nothing: bool = False,
) -> Path:
    """A PATH dir modelling the CREDENTIAL dependency, not a working tool.

    `bd` refuses exactly the way the real one does when the tenant credential is
    absent; the wrapper is the only thing that supplies it.
    """
    bin_dir = tmp_path / f"bin-{with_wrapper}-{bd_needs_credential}-{bd_returns_nothing}"
    bin_dir.mkdir()
    if bd_returns_nothing:
        # Succeeds while reporting nothing — an exit status that certifies a
        # reading which never happened.
        bd_body = "#!/bin/sh\nexit 0\n"
    elif bd_needs_credential:
        bd_body = (
            "#!/bin/sh\n"
            'if [ -z "${FLEET_LEDGER_CREDENTIAL:-}" ]; then\n'
            '  echo "failed to open database: Access denied for user" >&2\n'
            "  exit 1\n"
            "fi\n"
            'printf \'[{"id":"%s","status":"open"}]\\n\' "$2"\n'
        )
    else:
        bd_body = '#!/bin/sh\nprintf \'[{"id":"%s","status":"open"}]\\n\' "$2"\n'
    _write_exec(path=bin_dir / "bd", body=bd_body)
    if with_wrapper:
        _write_exec(
            path=bin_dir / "with-livespec-env.sh",
            body=(
                "#!/bin/sh\n"
                '[ "$1" = "--" ] && shift\n'
                "FLEET_LEDGER_CREDENTIAL=present\n"
                "export FLEET_LEDGER_CREDENTIAL\n"
                'exec "$@"\n'
            ),
        )
    return bin_dir


def _run(script: str, *, bin_dir: Path, cwd: Path, env_extra: dict[str, str] | None = None):
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(cwd)}
    env.update(env_extra or {})
    return subprocess.run(  # noqa: S603
        ["/bin/sh", "-c", script],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


# --------------------------------------------------------------------------
# The credential axis — the leg the cold-open gate structurally cannot cover.
# --------------------------------------------------------------------------


def test_the_emitted_ledger_block_succeeds_when_only_a_wrapper_supplies_credentials(tmp_path):
    block = _sh_block(anchor=_LEDGER_ANCHOR).replace("<ledger-anchor>", "demo-1")
    bin_dir = _credential_bin(tmp_path, with_wrapper=True, bd_needs_credential=True)
    result = _run(block, bin_dir=bin_dir, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert '"id":"demo-1"' in result.stdout
    assert "MEASURED_AT:" in result.stdout


def test_the_pre_fix_bare_invocation_fails_against_the_same_credentials(tmp_path):
    """The defect, demonstrated rather than remembered.

    Same stubs, same anchor; only the command form differs. If this ever passes,
    the stub has drifted into standing in for a working tool and every
    credential assertion in this module is worthless.
    """
    bin_dir = _credential_bin(tmp_path, with_wrapper=True, bd_needs_credential=True)
    result = _run(f'ledger_anchor="demo-1"\n{_BARE_FORM}', bin_dir=bin_dir, cwd=tmp_path)
    assert result.returncode == 1
    assert "Access denied" in result.stderr


def test_without_a_wrapper_the_remedy_names_the_wrapper_not_ledger_access(tmp_path):
    """A remedy naming the wrong cause is worse than no remedy.

    The shipped form advised "fix ledger access" while the ledger was healthy
    and the wrapper was the actual fix.
    """
    block = _sh_block(anchor=_LEDGER_ANCHOR).replace("<ledger-anchor>", "demo-1")
    bin_dir = _credential_bin(tmp_path, with_wrapper=False, bd_needs_credential=True)
    result = _run(block, bin_dir=bin_dir, cwd=tmp_path)
    assert result.returncode == 1
    assert "credential wrapper" in result.stdout
    assert "fix ledger access" not in result.stdout


def test_an_adopter_whose_ledger_needs_no_wrapper_still_re_measures(tmp_path):
    """Detection, not a hard-coded path: no wrapper must not mean no re-measure."""
    block = _sh_block(anchor=_LEDGER_ANCHOR).replace("<ledger-anchor>", "demo-1")
    bin_dir = _credential_bin(tmp_path, with_wrapper=False, bd_needs_credential=False)
    result = _run(block, bin_dir=bin_dir, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert '"id":"demo-1"' in result.stdout


def test_a_ledger_tool_that_exits_0_while_reporting_nothing_is_rejected(tmp_path):
    """An empty success must not be stamped MEASURED_AT.

    Exit status alone cannot tell a real reading from a tool that succeeded
    without reporting, and the stamp is what turns the second into a filed
    claim. Note this does NOT guard a wrapper defect: the fleet wrapper
    propagates 127 for a missing binary (measured 2026-07-30). A widely-repeated
    claim that it exits 0 came from reading `$?` after a PIPELINE, which yields
    `head`'s status.
    """
    block = _sh_block(anchor=_LEDGER_ANCHOR).replace("<ledger-anchor>", "demo-1")
    bin_dir = _credential_bin(
        tmp_path, with_wrapper=True, bd_needs_credential=False, bd_returns_nothing=True
    )
    result = _run(block, bin_dir=bin_dir, cwd=tmp_path)
    assert result.returncode == 1
    assert "exited 0 but returned NOTHING" in result.stdout
    assert "MEASURED_AT" not in result.stdout, "an empty success was stamped as a measurement"


def test_the_emitted_ledger_block_is_wrapper_aware():
    """Static backstop: the block must DETECT a wrapper, not assume either way.

    A bare `bd` fallback is deliberate and must stay — an adopter without a
    wrapper has to be able to re-measure. What must never come back is a block
    that invokes `bd` WITHOUT first detecting whether a wrapper is available,
    which is the form that shipped and failed every real cold open.
    """
    body = _sh_block(anchor=_LEDGER_ANCHOR)
    assert "command -v with-livespec-env.sh" in body, "no wrapper DETECTION"
    assert "with-livespec-env.sh -- bd show" in body, "no wrapper-routed invocation"
    detect_at = body.index("command -v with-livespec-env.sh")
    first_bd = body.index("bd show")
    assert detect_at < first_bd, "an unconditional `bd show` precedes the wrapper detection"


# --------------------------------------------------------------------------
# The boot block.
# --------------------------------------------------------------------------


def _boot_repo(tmp_path: Path, *, marker_lines: int, name: str) -> tuple[str, Path]:
    repo = tmp_path / name
    (repo / ".ai").mkdir(parents=True)
    (repo / ".ai" / "supervisor-protocol.md").write_text("shared layer\n")
    marker = repo / "marker.txt"
    marker.write_text("".join(f"line {i}\n" for i in range(1, marker_lines + 1)))
    return str(marker), repo


def test_an_unset_supervisor_marker_halts_loudly(tmp_path):
    """It used to display NOTHING and exit 0 — a boot that cannot fail."""
    _marker, repo = _boot_repo(tmp_path, marker_lines=10, name="unset")
    block = _sh_block(anchor=_BOOT_ANCHOR)
    bin_dir = _credential_bin(tmp_path, with_wrapper=True, bd_needs_credential=False)
    result = _run(block, bin_dir=bin_dir, cwd=repo)
    assert result.returncode == 1
    assert "HALT: supervisor_marker is unset or empty" in result.stdout
    assert "REMEDY:" in result.stdout


def test_a_short_marker_is_shown_whole_with_no_notice(tmp_path):
    marker, repo = _boot_repo(tmp_path, marker_lines=50, name="short")
    block = _sh_block(anchor=_BOOT_ANCHOR)
    bin_dir = _credential_bin(tmp_path, with_wrapper=True, bd_needs_credential=False)
    result = _run(block, bin_dir=bin_dir, cwd=repo, env_extra={"supervisor_marker": marker})
    assert result.returncode == 0, result.stderr
    assert "TRUNCATED" not in result.stdout
    assert "line 1\n" in result.stdout
    assert "line 50\n" in result.stdout


def test_a_long_marker_emits_a_notice_naming_the_hidden_range(tmp_path):
    marker, repo = _boot_repo(tmp_path, marker_lines=697, name="long")
    block = _sh_block(anchor=_BOOT_ANCHOR)
    bin_dir = _credential_bin(tmp_path, with_wrapper=True, bd_needs_credential=False)
    result = _run(block, bin_dir=bin_dir, cwd=repo, env_extra={"supervisor_marker": marker})
    assert result.returncode == 0, result.stderr
    assert "TRUNCATED: lines 161-537 of 697 NOT SHOWN (377 hidden)" in result.stdout
    shown = [ln for ln in result.stdout.splitlines() if ln.startswith("line ")]
    # The notice's arithmetic must match the cut it describes, or it is a
    # different kind of lie from the silence it replaced.
    assert len(shown) == 320
    assert shown[159] == "line 160"
    assert shown[160] == "line 538"


def test_a_retraction_in_the_tail_survives_truncation(tmp_path):
    """The regression test for the harm, not for the mechanism.

    A real marker carried an obligation assigning `holder: worker` at line 200 —
    inside the old visible window — while its retraction sat at line 253, below
    the cut. A cold-open reader was shown discharged work as live. A head-only
    read is the worst possible cut of an append-only file, because corrections
    land at the END.
    """
    repo = tmp_path / "retraction"
    (repo / ".ai").mkdir(parents=True)
    (repo / ".ai" / "supervisor-protocol.md").write_text("shared layer\n")
    marker = repo / "marker.txt"
    lines = [f"filler {i}\n" for i in range(1, 701)]
    lines[199] = "OPEN OBLIGATIONS: holder worker, implement ejja5o\n"
    lines[599] = "NO OPEN OBLIGATIONS: ejja5o closed, nothing is in flight\n"
    marker.write_text("".join(lines))
    block = _sh_block(anchor=_BOOT_ANCHOR)
    bin_dir = _credential_bin(tmp_path, with_wrapper=True, bd_needs_credential=False)
    result = _run(block, bin_dir=bin_dir, cwd=repo, env_extra={"supervisor_marker": str(marker)})
    assert result.returncode == 0, result.stderr
    assert "NO OPEN OBLIGATIONS" in result.stdout, "the retraction was cut away"
    assert "TRUNCATED" in result.stdout
