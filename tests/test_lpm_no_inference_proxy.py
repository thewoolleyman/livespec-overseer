"""The manager puts a credential WHERE THE CLIENT ALREADY READS, and is never in the path.

SPECIFICATION/contracts.md registers exactly one ProvisioningTarget adapter,
`isolated-run`, which binds one credential to one consumer run and commits it with a
single atomic write. Nothing in this operation accepts, forwards or answers an inference
request: there is no proxy, no relay, no gateway and no forwarding endpoint, and no
consumer points a base URL at it.

THIS IS A REGRESSION GUARD OVER AN INVARIANT THAT ALREADY HOLDS, not a test that drove
new behavior. Said plainly because it changes how the legs below should be read and how
they should be maintained: the closed adapter registry came with the provisioning
foundation and the closed argument grammar came with the invocation layer, so each
assertion here passed the moment it was written. What was missing was anything that would
NOTICE either one opening up, and "we never meant to add a proxy" is not a property a
reader can verify from a green suite.

A negative like this is easy to write badly, so each leg measures something a regression
would actually change, rather than scanning prose for a forbidden word:

* The word-scan is DELIBERATELY NOT DONE. The operator contract earns its keep by naming
  the boundary explicitly -- it tells a reader looking for something to point a base URL
  at that they are in the wrong place -- so a gate banning "proxy" from the shipped
  surface would fail on the very sentence that states the guarantee. A guard whose
  strictest reading forbids DOCUMENTING the invariant is measuring the wrong thing.
* The ADAPTER REGISTRY is closed, and the default enabled set equals it. A proxy would
  arrive as a second adapter, and this is the cheapest place it would show up.
* The ARGUMENT GRAMMAR cannot express a serve/listen verb. Driven over a corpus of
  proxy-shaped invocations, every one of which must be refused before any launch.
* NO SHIPPED MODULE IMPORTS A LISTENING FACILITY. This is the leg that would catch an
  actual implementation rather than an intention, and it carries its own discriminating
  control below -- without one, a scanner with a typo'd pattern list would report a clean
  tree forever and read exactly like a passing guard.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
from typing import Any

__all__: list[str] = []

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "overseer"
PLUGIN = ROOT / ".claude-plugin"

OPERATION = "llm-provider-manager"

# Module-level facilities that would let a process ACCEPT a request rather than make one.
# `socket` is absent deliberately: a client that dials out uses it too, so banning it
# would forbid the provider probe this operation legitimately performs.
LISTENING_MODULES = frozenset(
    {
        "aiohttp",
        "asyncio.streams",
        "fastapi",
        "flask",
        "http.server",
        "socketserver",
        "uvicorn",
        "wsgiref",
    }
)

PROXY_SHAPED_INVOCATIONS = (
    ["serve"],
    ["proxy"],
    ["relay", "--port", "8080"],
    ["--listen", "127.0.0.1:8080"],
    ["--port", "8080"],
    ["gateway", "--upstream", "https://api.anthropic.com"],
)


def _module(*, name: str) -> Any:
    return importlib.import_module(name)


def _imported_module_names(*, source: str) -> set[str]:
    """Every module name the source imports, by either import form."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def _listening_imports(*, source: str) -> set[str]:
    """The intersection that makes a module able to accept a request."""
    return _imported_module_names(source=source) & LISTENING_MODULES


def _manager_sources() -> dict[str, str]:
    paths = [*PACKAGE.glob("_lpm_*.py"), PACKAGE / "llm_provider_manager.py"]
    return {path.name: path.read_text(encoding="utf-8") for path in paths}


def test_exactly_one_provisioning_target_adapter_is_registered_and_enabled() -> None:
    """A proxy would have to arrive as a second adapter; the registry is closed to one."""
    registry = _module(name="_lpm_registry")
    config = _module(name="_lpm_config")
    target = _module(name="_lpm_target")

    assert registry.REGISTERED_TARGET_ADAPTERS == ("isolated-run",)
    assert target.ISOLATED_RUN_ADAPTER == "isolated-run"
    assert config.default_config().enabled_target_adapters == ("isolated-run",)


def test_the_operator_grammar_refuses_every_proxy_shaped_invocation() -> None:
    """There is no verb for standing something up; the grammar has only two shapes."""
    operator_request = _module(name="_lpm_operator_request").operator_request

    accepted = [
        arguments
        for arguments in PROXY_SHAPED_INVOCATIONS
        if operator_request(arguments=arguments).value_or(None) is not None
    ]

    assert accepted == [], f"these proxy-shaped invocations were accepted: {accepted}"


def test_no_shipped_manager_module_imports_a_listening_facility() -> None:
    sources = _manager_sources()
    # Control: the scan must actually be reading the operation's modules. An empty or
    # near-empty corpus would make the assertion below vacuously true, which is the
    # failure mode that lets a negative guard pass while guarding nothing.
    assert len(sources) >= 30, sorted(sources)
    assert "llm_provider_manager.py" in sources

    offenders = {
        name: sorted(found)
        for name, source in sources.items()
        if (found := _listening_imports(source=source))
    }

    assert offenders == {}, f"these manager modules can accept a request: {offenders}"


def test_the_listening_scan_reports_a_module_that_stands_up_a_server() -> None:
    """DISCRIMINATING CONTROL: the scan must FAIL on a module that IS a relay.

    Drives the same helper the gate above uses. A scanner with a typo'd pattern list
    reports a clean tree forever and is indistinguishable from a correct one until
    something is actually wrong -- by which time it is too late to find out.
    """
    innocent = "import json\nimport subprocess\nfrom pathlib import Path\n"
    relay = "from http.server import ThreadingHTTPServer\n\n\ndef serve() -> None: ...\n"

    assert _listening_imports(source=innocent) == set()
    assert _listening_imports(source=relay) == {"http.server"}


def test_the_operator_contract_states_the_direct_provisioning_boundary() -> None:
    """The guarantee is only useful to an operator if the contract actually makes it."""
    prose = (PLUGIN / "prose" / f"{OPERATION}.md").read_text(encoding="utf-8")

    assert "provisions DIRECTLY into an isolated consumer target" in prose
    assert "no inference-request proxy, no relay" in prose
    assert "isolated-run" in prose
