"""The emitted provenance check, RUN, against a fabricated plugin cache.

`test_generated_supervisor_handoff_contract.py` proves the charter CARRIES a
provenance record and a comparison. That is a statement about the text. This
module runs the block the charter actually emits and pins what it DOES in each
of the four states it can meet — the same relationship the `*_discriminates`
modules have to the rest of this directory.

WHY IT IS NEEDED RATHER THAN TIDY. The cold-open gate executes every emitted
block, but in CI there is no plugin cache, so the block takes its
cannot-verify branch and the COMPARISON — the whole point of the record — is
never executed anywhere. A rule whose load-bearing path no runner reaches is
the verifier-that-cannot-fail shape this epic exists to remove. The fix is not
to weaken the gate but to fabricate the cache here, where the test controls both
the file and its digest.

THE FOUR STATES, and the reason the first two are not the same thing. Conflating
them was a real bug: the first version of this block HALTed whenever the recorded
generator prose was absent, which is right on an adopter host and wrong
everywhere else. `test_current_generated_layers_are_cold_open_clean` caught it in
CI, having passed locally only because this host happens to hold the cache. A
charter that HALTs on every machine except the one that produced it is unusable,
and committed charters are read from many.

    cache root absent      -> rc 0, UNVERIFIED   not a charter-generating host
    recorded ref absent    -> rc 1, HALT         the generator was REPLACED
    digest differs         -> rc 1, HALT         the charter is STALE
    digest matches         -> rc 0, PASS         current

UNVERIFIED IS NOT A SILENT PASS, and that distinction is the one to hold onto: it
names the path it could not read and the generator it was looking for, so the
output says which of "checked and fine" and "could not check" happened. A bare
exit 0 would not.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CHARTER = _REPO_ROOT / "tests" / "prompts" / "fixtures" / "exemplar-supervisor-handoff.md"
_GENERATOR_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"

# The emitted block, taken from the REAL charter rather than restated here. A
# copy would let the shipped block rot while this module stayed green — the
# reasoning already landed in `tests/test_prose_release_hygiene.py`.
_PROVENANCE_BLOCK = re.compile(r"## Generator provenance.*?```sh\n(.*?)\n```", re.DOTALL)
_RECORDED_DIGEST = re.compile(r"generator_prose_md5='([0-9a-f]{32})'")
_RECORDED_REF = re.compile(r"generator_ref='([^']+)'")
_RECORDED_PLUGIN = re.compile(r"generator_plugin='([^']+)'")


def _emitted_block() -> str:
    charter = _CHARTER.read_text(encoding="utf-8")
    match = _PROVENANCE_BLOCK.search(charter)
    if match is None:
        raise AssertionError(
            f"no fenced provenance block under '## Generator provenance' in {_CHARTER}. "
            "This module runs the SHIPPED block; restore it rather than deleting this leg."
        )
    return match.group(1)


def _generator_template_block() -> str:
    prose = _GENERATOR_PROSE.read_text(encoding="utf-8")
    match = _PROVENANCE_BLOCK.search(prose)
    if match is None:
        raise AssertionError(
            "no fenced provenance template block under '## Generator provenance' in "
            f"{_GENERATOR_PROSE}"
        )
    return match.group(1)


def _concrete_template_block(*, digest: str, ref: str = "older-ref") -> str:
    block = _generator_template_block()
    replacements = {
        "generator_plugin": "livespec-overseer",
        "generator_ref": ref,
        "generator_version": "0.0-test",
        "generator_prose_md5": digest,
    }
    for name, value in replacements.items():
        block = re.sub(rf"^{name}='[^']+'$", f"{name}='{value}'", block, flags=re.MULTILINE)
    return block


def _recorded(*, pattern: re.Pattern[str], name: str) -> str:
    match = pattern.search(_emitted_block())
    if match is None:
        raise AssertionError(f"the emitted provenance block records no {name}")
    return match.group(1)


def _run(*, home: Path, block: str | None = None) -> subprocess.CompletedProcess[str]:
    """Execute the emitted block with HOME pointed at a fabricated cache.

    S603/S607 suppressed on the narrow reasoning used by every sibling fixture:
    the argv is a list with no untrusted input, and `sh` must resolve the way an
    operator pasting the block resolves it.
    """
    return subprocess.run(  # noqa: S603
        ["sh", "-c", _emitted_block() if block is None else block],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(home)},
        timeout=30,
    )


def _cache_root(*, home: Path) -> Path:
    plugin = _recorded(pattern=_RECORDED_PLUGIN, name="plugin")
    return home / ".claude" / "plugins" / "cache" / plugin / plugin


def _install(*, home: Path, ref: str, content: bytes) -> None:
    prose = _cache_root(home=home) / ref / "prose" / "supervise-plan.md"
    prose.parent.mkdir(parents=True)
    prose.write_bytes(content)


def _install_ref_with_mtime(*, home: Path, ref: str, content: bytes, mtime: int) -> None:
    _install(home=home, ref=ref, content=content)
    ref_dir = _cache_root(home=home) / ref
    os.utime(ref_dir, (mtime, mtime))


@pytest.fixture(name="home")
def _home(*, tmp_path: Path) -> Path:
    """A HOME with no plugin cache, which each test then populates."""
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_no_cache_root_reports_unverified_and_continues(*, home: Path):
    """The CI condition, and the one that must NOT halt.

    This is what turned the first attempt red: a runner with no plugin cache
    cannot check provenance, and refusing to continue there makes every
    committed charter unreadable off the host that produced it.
    """
    result = _run(home=home)
    assert result.returncode == 0, result.stderr
    assert "UNVERIFIED" in result.stdout
    # It must say WHAT it could not read and WHICH generator it wanted, or
    # "could not check" is indistinguishable from "checked and fine".
    assert str(_cache_root(home=home)) in result.stdout
    assert _recorded(pattern=_RECORDED_DIGEST, name="digest") in result.stdout


def test_generator_template_no_cache_root_reports_unverified_and_continues(*, home: Path):
    """The generator-owned block must preserve the CI/read-only host branch."""
    digest = hashlib.md5(b"recorded generator\n", usedforsecurity=False).hexdigest()
    result = _run(home=home, block=_concrete_template_block(digest=digest))
    assert result.returncode == 0, result.stderr
    assert "UNVERIFIED" in result.stdout
    assert str(_cache_root(home=home)) in result.stdout
    assert digest in result.stdout


def test_a_cache_that_no_longer_holds_the_recorded_ref_halts(*, home: Path):
    """A refresh lands under a NEW ref directory, so this is how staleness shows.

    The cache root EXISTS here — this is an adopter host — and the recorded ref
    is gone. That is a replaced generator, not an unknown environment.
    """
    _install(home=home, ref="some-newer-ref", content=b"whatever the new generator is\n")
    result = _run(home=home)
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "HALT" in combined
    assert "REMEDY" in combined


def test_a_digest_mismatch_halts_and_names_both_generators(*, home: Path):
    """The comparison itself — the path no other runner reaches.

    Naming both digests is what makes the HALT actionable: a reader can tell
    which generation the charter came from and which one is installed.
    """
    recorded_digest = _recorded(pattern=_RECORDED_DIGEST, name="digest")
    _install(
        home=home,
        ref=_recorded(pattern=_RECORDED_REF, name="ref"),
        content=b"a different generator entirely\n",
    )
    result = _run(home=home)
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert recorded_digest in combined
    assert hashlib.md5(b"a different generator entirely\n", usedforsecurity=False).hexdigest() in (
        combined
    )
    assert "REMEDY" in combined


def test_the_recorded_generator_passes(*, home: Path):
    """THE POSITIVE CONTROL. Without it, three failures prove only that it fails.

    The installed prose is a REAL in-tree artifact whose digest is the recorded
    one — the live generator prose, or one of the two vendored cache
    generations. The pass is earned by an artifact this repo can actually
    produce, never by relaxing the check.
    """
    recorded_digest = _recorded(pattern=_RECORDED_DIGEST, name="digest")
    content = _generation_with_digest(digest=recorded_digest)
    _install(home=home, ref=_recorded(pattern=_RECORDED_REF, name="ref"), content=content)
    result = _run(home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
    assert recorded_digest in result.stdout


def test_generator_template_checks_newest_installed_ref_not_recorded_ref(*, home: Path):
    """RED LEG: a stale recorded ref must not compare against itself.

    The recorded ref stays present, because real plugin caches retain old refs.
    The current generator is the newest ref by mtime, and a different digest
    there must HALT while naming both refs and both digests.
    """
    recorded = b"old generator prose\n"
    current = b"current generator prose\n"
    recorded_digest = hashlib.md5(recorded, usedforsecurity=False).hexdigest()
    current_digest = hashlib.md5(current, usedforsecurity=False).hexdigest()
    _install_ref_with_mtime(home=home, ref="0.12.2", content=recorded, mtime=1_000)
    _install_ref_with_mtime(home=home, ref="0.17.0", content=current, mtime=2_000)

    result = _run(
        home=home,
        block=_concrete_template_block(digest=recorded_digest, ref="0.12.2"),
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "HALT" in combined
    assert "0.12.2" in combined
    assert "0.17.0" in combined
    assert recorded_digest in combined
    assert current_digest in combined
    assert "REMEDY" in combined


def test_generator_template_passes_when_the_newest_ref_matches(*, home: Path):
    """A charter stamped from the current ref passes."""
    content = b"current generator prose\n"
    digest = hashlib.md5(content, usedforsecurity=False).hexdigest()
    _install_ref_with_mtime(home=home, ref="0.17.0", content=content, mtime=2_000)

    result = _run(home=home, block=_concrete_template_block(digest=digest, ref="0.17.0"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
    assert digest in result.stdout


def test_generator_template_passes_when_newest_ref_has_the_same_digest(*, home: Path):
    """Ref identity is not generator identity; byte-identical prose stays green."""
    content = b"same generator prose across releases\n"
    digest = hashlib.md5(content, usedforsecurity=False).hexdigest()
    _install_ref_with_mtime(home=home, ref="0.16.0", content=content, mtime=1_000)
    _install_ref_with_mtime(home=home, ref="0.17.0", content=content, mtime=2_000)

    result = _run(home=home, block=_concrete_template_block(digest=digest, ref="0.16.0"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
    assert digest in result.stdout


def test_a_charter_with_no_provenance_block_fails_loudly(*, tmp_path: Path, monkeypatch):
    """The fixture's own integrity guards are TESTED, not pragma'd away.

    Each of the three below refuses to skip when its input is malformed. They are
    reachable, so they are exercised rather than exempted — a guard nobody runs
    is indistinguishable from one that does not work.
    """
    charter = tmp_path / "no-provenance.md"
    charter.write_text("# Supervisor Handoff - demo\n\n## Bindings\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "_CHARTER", charter)
    with pytest.raises(AssertionError, match="no fenced provenance block"):
        _emitted_block()


def test_a_provenance_block_recording_no_digest_fails_loudly(*, tmp_path: Path, monkeypatch):
    """A block present but recording nothing must not read as a clean pass."""
    charter = tmp_path / "no-digest.md"
    charter.write_text(
        "## Generator provenance\n\n```sh\ngenerator_ref='013d35d48cde'\n```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "_CHARTER", charter)
    with pytest.raises(AssertionError, match="records no digest"):
        _recorded(pattern=_RECORDED_DIGEST, name="digest")


def test_a_recorded_generation_this_repo_cannot_produce_fails_loudly():
    """THE GUARD THAT ALREADY EARNED ITS KEEP.

    It fired for real while this was being written: the charter still recorded
    the digest of the prose from BEFORE this change, which no file in the tree
    could produce any more. That is a finding — a charter claiming a generator
    that does not exist here — not a reason to relax the positive control.
    """
    with pytest.raises(AssertionError, match="matches none of"):
        _generation_with_digest(digest="0" * 32)


def _generation_with_digest(*, digest: str) -> bytes:
    """The vendored or live prose whose md5 is `digest`.

    Four candidates exist in-tree: three frozen cache artifacts and the prose
    this repo currently ships. `cached-prose-e793c257.md` is the generation the
    exemplar charter records; it was frozen when the ledger-entry rewrite landed,
    because the exemplar is a historical fixture that must not be re-stamped. Failing
    loudly when none matches is deliberate — it means the charter records a
    generation this repo cannot produce, which is a finding rather than a reason
    to skip.
    """
    candidates = (
        _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md",
        _REPO_ROOT / "tests" / "prompts" / "fixtures" / "cached-prose-2283862c.md",
        _REPO_ROOT / "tests" / "prompts" / "fixtures" / "cached-prose-30b59fcf.md",
        _REPO_ROOT / "tests" / "prompts" / "fixtures" / "cached-prose-e793c257.md",
    )
    for candidate in candidates:
        content = candidate.read_bytes()
        if hashlib.md5(content, usedforsecurity=False).hexdigest() == digest:
            return content
    raise AssertionError(
        f"the charter records generator {digest}, which matches none of "
        + ", ".join(str(path.relative_to(_REPO_ROOT)) for path in candidates)
        + ". Re-stamp the charter from a generation this repo can produce, or "
        "vendor the one it names."
    )
