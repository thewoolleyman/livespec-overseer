"""Three harnesses resolve the plugin root three different ways, and must converge.

SPECIFICATION/contracts.md closes the supported-harness set to the Claude binding, the
Codex binding and the namespaced Pi binding, and requires each to resolve this plugin's
root through its OWN harness-defined installed-plugin discovery before invoking anything.
The three mechanisms are genuinely different, and the differences are load-bearing rather
than stylistic: Claude substitutes a plugin-root token into SKILL prose, Codex does not
and must resolve the root explicitly, and Pi's skill namespace is flat so its binding
carries the unabbreviated name prefix and delegates to one shared resolver script.

THE FAILURE THIS GUARDS IS COPYING A SIBLING. All three bindings look alike, and the
quickest way to add a fourth harness -- or to "fix" one -- is to paste another one's
body. That produces a file that is structurally plausible, passes every existing
existence and prose-reference check, and silently cannot resolve a root in the harness it
claims to serve. So the legs below assert each binding's OWN mechanism positively AND
assert the mechanisms it must not have borrowed.

Like `test_lpm_no_inference_proxy`, this is a REGRESSION GUARD over structure that
already holds rather than a test that drove behavior, and saying so is part of the
record: the bindings shipped with the surface, and what was missing was anything that
would notice one of them drifting into a copy of its neighbour.

The last leg ties the contract to the code. Every other gate in the suite reads the
bindings as TEXT; this one hands the repository's real plugin root to the validator the
shared entrypoint actually calls and requires it to be accepted. Without it, the
validator's idea of where the three bindings live could drift from where they really are
and every text-level gate would stay green -- a shipped surface no binding could ever
validate.
"""

from __future__ import annotations

import importlib
import pathlib
from typing import Any

__all__: list[str] = []

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".claude-plugin"

OPERATION = "llm-provider-manager"

CLAUDE_BINDING = PLUGIN / "skills" / OPERATION / "SKILL.md"
CODEX_BINDING = PLUGIN / ".codex-plugin" / "skills" / OPERATION / "SKILL.md"
PI_BINDING = PLUGIN / ".pi-plugin" / "skills" / f"livespec-overseer-{OPERATION}" / "SKILL.md"
PI_RESOLVER = PLUGIN / ".pi-plugin" / "lib" / "resolve-plugin-root.sh"


def _body(*, path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_claude_binding_resolves_through_the_substituted_plugin_root_token() -> None:
    body = _body(path=CLAUDE_BINDING)

    assert "${CLAUDE_PLUGIN_ROOT}" in body
    assert f"prose/{OPERATION}.md" in body


def test_the_codex_binding_resolves_the_root_explicitly_and_borrows_no_claude_token() -> None:
    """Codex does not substitute a plugin-root token, so a borrowed one resolves nothing."""
    body = _body(path=CODEX_BINDING)

    assert "CLAUDE_PLUGIN_ROOT" not in body, (
        "the Codex binding must not rely on Claude's substituted token: it is never "
        "substituted, so the path would be read literally"
    )
    assert "PLUGIN_ROOT=" in body
    for step in (
        "LIVESPEC_OVERSEER_PLUGIN_ROOT",
        "./.claude-plugin",
        "$HOME/.codex/plugins/cache/livespec-overseer/livespec-overseer",
        "codex plugin list --json -m livespec-overseer",
    ):
        assert step in body, f"the Codex resolution chain is missing its {step!r} step"


def test_the_pi_binding_delegates_to_the_one_shared_resolver_it_must_not_restate() -> None:
    body = _body(path=PI_BINDING)

    assert (
        PI_RESOLVER.is_file()
    ), f"the pi resolver the binding delegates to must exist: {PI_RESOLVER}"
    assert "lib/resolve-plugin-root.sh" in body
    assert PI_BINDING.parent.name == f"livespec-overseer-{OPERATION}"
    assert "CLAUDE_PLUGIN_ROOT" not in body
    assert "codex plugin list" not in body, (
        "the pi binding must not carry Codex's resolution chain; pi resolves through "
        "its own package clone layout"
    )


def test_all_three_bindings_converge_on_the_same_contract_and_add_no_behavior() -> None:
    """Different resolution, one destination. That convergence IS the thin-binding rule."""
    bodies = {
        "claude": _body(path=CLAUDE_BINDING),
        "codex": _body(path=CODEX_BINDING),
        "pi": _body(path=PI_BINDING),
    }

    for harness, body in bodies.items():
        assert f"prose/{OPERATION}.md" in body, harness
        assert (
            "no operation behavior" in body.lower() or "owns the behavior" in body.lower()
        ), f"the {harness} binding does not say it carries no operation behavior"


def test_the_shared_prose_delegates_to_the_importable_entrypoint() -> None:
    """The bindings resolve a root; the ONE contract they all read names what to run."""
    prose = _body(path=PLUGIN / "prose" / f"{OPERATION}.md")

    assert "python3 -m overseer.llm_provider_manager" in prose
    assert 'PYTHONPATH="$PLUGIN_ROOT"' in prose


def test_the_repositorys_own_plugin_root_is_accepted_by_the_validator_bindings_use() -> None:
    """The end-to-end tie: the shipped root must pass the code that actually gates it.

    Every other gate here reads the surface as text. This one hands the real root to the
    validator the shared entrypoint calls, so the validator's idea of where the three
    bindings live cannot drift from where they are while the text gates stay green.
    """
    binding_root: Any = importlib.import_module("_lpm_binding_root")

    accepted = binding_root.validated_plugin_root(plugin_root=PLUGIN)

    assert accepted.value_or(None) == PLUGIN.resolve(), accepted
    missing = [
        relative
        for relative in binding_root.REQUIRED_SURFACE_FILES
        if not (PLUGIN / relative).is_file()
    ]
    assert missing == [], f"the validator requires files the surface does not ship: {missing}"
