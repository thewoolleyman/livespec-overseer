"""The `llm-provider-manager` console bootstrap: scrub, then re-exec into the isolated companion.

SPECIFICATION/contracts.md states this module's whole job, and its constraints are unusually
tight: "Before process replacement, the installed console wrapper MAY import only the `overseer`
package initializer and its standard-library-only bootstrap module; that bootstrap MUST import no
other product module. As its first manager-owned action after those two imports and before reading
any environment value or performing substantive work, the bootstrap MUST remove every inherited
entry in the complete closed credential-override set by ASCII-uppercased name without reading its
value. It MUST then re-execute the invoking Python interpreter with `-I -S`, an absolute path to
its packaged companion and the original manager arguments, preserving standard input, output,
error and exit status. ... Inability to establish that isolated companion MUST emit the common
`internal-bug` result and exit `70` without substantive mutation."

THE SCRUB COMES FIRST, AND BY NAME ONLY. Nothing below reads an environment VALUE: the closed set
is matched on the ASCII-uppercased NAME, because a bootstrap that read values to decide what to
delete would have those values in its own process memory — which is the thing being prevented.
An inherited `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` or `OP_SERVICE_ACCOUNT_TOKEN` must not
reach any manager code, let alone a role child.

THE CLOSED SET IS DUPLICATED HERE, DELIBERATELY AND UNCOMFORTABLY. `_lpm_env` owns it, and
importing `_lpm_env` is exactly what the sentence above forbids — the bootstrap may import the
package initializer and nothing else, because every product import happens BEFORE the scrub and
so runs with the credentials still in the environment. A copy that silently drifted would be
worse than the duplication, so `tests/test_lpm_console_bootstrap.py` asserts the two sets are
EQUAL rather than trusting this one.

`-I -S` IS WHAT MAKES THE COMPANION ISOLATED. `-I` ignores `PYTHONPATH` and the user site
directory and keeps the script's own directory off `sys.path`; `-S` disables site-package
discovery entirely. So no environment variable a consumer controls can repoint the manager at
another plugin's code, and the companion must locate its product package explicitly — which is
why `_lpm_companion` loads it by absolute path rather than by `import`.

THE EXEC IS AN INJECTABLE MODULE ATTRIBUTE, NOT A FLAG. `execv` is substituted by this module's
tests and by nothing else; the invocation surface stays knob-free, exactly as the daemon's own
re-exec seam does.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Final

__all__: list[str] = [
    "COMPANION_MODULE_NAME",
    "CREDENTIAL_OVERRIDE_PREFIXES",
    "EXACT_CREDENTIAL_OVERRIDES",
    "INTERNAL_BUG_LINE",
    "INTERNAL_BUG_STATUS",
    "companion_path",
    "is_credential_override",
    "main",
    "scrub_credential_overrides",
]

COMPANION_MODULE_NAME: Final = "_lpm_companion.py"
INTERNAL_BUG_STATUS: Final = 70

# The common single-line `internal-bug` object, as a LITERAL. `_lpm_results.error_object` builds
# the same bytes, and importing it here is forbidden: it is a product module, and every import in
# this file happens before the scrub below. One of the two copies has to be the literal, and it
# is cheaper to pin this one with a test than to move the scrub after a product import.
INTERNAL_BUG_LINE: Final = (
    '{"version":1,"status":"error","error_type":"internal-bug",'
    '"message":"the isolated manager companion could not be established"}'
)

CREDENTIAL_OVERRIDE_PREFIXES: Final = ("ANTHROPIC_", "CLAUDE_", "OP_")

EXACT_CREDENTIAL_OVERRIDES: Final = (
    "CLAUDECODE",
    "LPM_ACQUISITION_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_ACQUISITION_READER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_PROVIDER_OBSERVER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN",
)

execv: Callable[[str, list[str]], None] = os.execv


def is_credential_override(*, name: str) -> bool:
    """True when this environment NAME is in the closed credential-override set."""
    upper = name.upper()
    return upper in EXACT_CREDENTIAL_OVERRIDES or upper.startswith(CREDENTIAL_OVERRIDE_PREFIXES)


def scrub_credential_overrides(*, environ: MutableMapping[str, str]) -> tuple[str, ...]:
    """Delete every credential-override entry by name; answer which names were removed."""
    removed = tuple(sorted(name for name in environ if is_credential_override(name=name)))
    for name in removed:
        del environ[name]
    return removed


def companion_path() -> Path:
    """The absolute path to the packaged companion beside this bootstrap."""
    return Path(__file__).resolve().parent / COMPANION_MODULE_NAME


def main() -> int:
    """Scrub, then replace this process with the isolated companion; `70` if that cannot happen."""
    _ = scrub_credential_overrides(environ=os.environ)
    companion = companion_path()
    if companion.is_file():
        # A successful exec never returns, so anything past this block means the isolated companion
        # could not be established -- the contract's one `internal-bug` for this layer. The OSError
        # is suppressed rather than handled for exactly that reason: there is nothing to decide.
        with contextlib.suppress(OSError):
            execv(sys.executable, [sys.executable, "-I", "-S", str(companion), *sys.argv[1:]])
    _ = sys.stdout.write(f"{INTERNAL_BUG_LINE}\n")
    return INTERNAL_BUG_STATUS


if __name__ == "__main__":
    raise SystemExit(main())
