"""Every per-harness binding must READ its prose contract, never restate it.

`overseer-mr2f2k`. Each operation ships one harness-neutral prose contract plus
three thin bindings (Claude, Codex, pi). The bindings are supposed to resolve a
plugin root and read the prose; ALL behavior lives in the prose. A binding that
stops referencing its prose file has silently become a second, divergent copy of
the contract -- and nothing else in the suite would notice, because the file
would still exist and still parse.

This gate therefore checks the REFERENCE, not the file's existence. The
discriminating control below drives the same helper with a binding body that has
dropped its prose reference and asserts that case is reported; without that leg
the gate would pass just as happily against a check that always returned "fine".
"""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = ROOT / ".claude-plugin"

OPERATIONS = (
    "overseer",
    "supervise-plan",
    "foreman",
    "grooming",
    "caam-anthropic-loop",
)


def _binding_paths(*, operation: str) -> dict[str, Path]:
    return {
        "claude": PLUGIN_ROOT / "skills" / operation / "SKILL.md",
        "codex": PLUGIN_ROOT / ".codex-plugin" / "skills" / operation / "SKILL.md",
        "pi": (
            PLUGIN_ROOT / ".pi-plugin" / "skills" / f"livespec-overseer-{operation}" / "SKILL.md"
        ),
    }


def _missing_prose_reference(*, body: str, operation: str) -> bool:
    """True when a binding body fails to reference its own prose contract."""
    return f"prose/{operation}.md" not in body


def test_every_binding_references_its_prose_contract() -> None:
    offenders: list[str] = []
    for operation in OPERATIONS:
        for harness, path in _binding_paths(operation=operation).items():
            assert path.is_file(), f"{harness} binding missing for {operation}: {path}"
            if _missing_prose_reference(body=path.read_text(encoding="utf-8"), operation=operation):
                offenders.append(f"{operation}/{harness}")

    assert offenders == [], (
        "these bindings do not reference their prose contract and may be carrying "
        f"behavior of their own: {offenders}"
    )


def test_gate_reports_a_binding_that_dropped_its_prose_reference() -> None:
    """DISCRIMINATING CONTROL: the check must FAIL on a self-contained binding.

    Drives the same helper the gate above uses. The first body references its
    prose and must pass; the second restates behavior inline with no reference
    and must be reported. A gate that cannot separate these two is not measuring
    anything.
    """
    referencing = 'Read the contract:\n\n```bash\ncat "$PLUGIN_ROOT/prose/grooming.md"\n```\n'
    self_contained = "# grooming\n\nStage 1: measure the tenant. Stage 2: drain the spec lane.\n"

    assert not _missing_prose_reference(body=referencing, operation="grooming")
    assert _missing_prose_reference(body=self_contained, operation="grooming")


def test_bindings_carry_their_harness_specific_shape() -> None:
    """The three bindings are not interchangeable copies.

    Codex does not substitute a plugin-root token into SKILL prose, so its
    binding resolves the root explicitly. pi's skill namespace is flat, so its
    directory carries the unabbreviated `livespec-overseer-` name prefix. Both
    properties are load-bearing and both are easy to lose when a binding is
    created by copying its sibling.
    """
    for operation in OPERATIONS:
        paths = _binding_paths(operation=operation)

        codex_body = paths["codex"].read_text(encoding="utf-8")
        assert (
            "PLUGIN_ROOT" in codex_body
        ), f"the Codex binding must resolve the plugin root explicitly: {paths['codex']}"

        assert paths["pi"].parent.name == f"livespec-overseer-{operation}", (
            "the pi binding directory must carry the unabbreviated name prefix: " f"{paths['pi']}"
        )
