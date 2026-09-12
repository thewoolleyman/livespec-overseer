"""The closed inherited credential-override scrub.

SPECIFICATION/contracts.md requires that, before starting either acquisition agent role or
any acquisition terminal, Chrome or browser-control child, the manager or worker REMOVE
every inherited environment entry whose ASCII-uppercased name is `CLAUDECODE`, begins
`ANTHROPIC_` or `CLAUDE_`, is one of the six manager service-account variables, or begins
`OP_`. The same complete set is reapplied at the child-spawn boundary by whichever process
actually spawns each child, inside the credential-role launcher before key lookup, and by
the MCP proxy as its first manager-owned instruction.

THE SCRUB IS BY NAME AND MUST NOT READ A VALUE. The contract says so explicitly for the
launcher, and it is the reason this module builds the surviving environment by COPYING the
entries that pass rather than by deleting the ones that fail: a delete-in-place
implementation reads and rewrites the whole mapping, and a debug print of the intermediate
state would then contain exactly the bytes the scrub exists to keep out of children.

WHY IT IS ALSO THE RECOVERY FROM A CONSUMER'S OWN OVERRIDE: the invoked bootstrap may
inherit a consumer-supplied credential override, and that inheritance is permitted ONLY
until this first-step name-only scrub. A manager child that kept `ANTHROPIC_API_KEY` or a
`CLAUDE_CODE_OAUTH_TOKEN` would authenticate as whoever launched it rather than as the
account the manager selected — which is precisely the confusion this whole operation
exists to remove.

Matching is on the ASCII-UPPERCASED name, so a lowercase or mixed-case spelling of the
same variable cannot slip through on a platform that treats environment names as
case-sensitive.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

__all__: list[str] = [
    "CREDENTIAL_OVERRIDE_PREFIXES",
    "EXACT_CREDENTIAL_OVERRIDES",
    "MANAGER_SERVICE_ACCOUNT_VARIABLES",
    "is_credential_override",
    "removed_override_names",
    "scrubbed_environment",
]

MANAGER_SERVICE_ACCOUNT_VARIABLES: Final = (
    "LPM_ACQUISITION_READER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_ACQUISITION_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_PROVIDER_OBSERVER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN",
)

CREDENTIAL_OVERRIDE_PREFIXES: Final = ("ANTHROPIC_", "CLAUDE_", "OP_")
EXACT_CREDENTIAL_OVERRIDES: Final = ("CLAUDECODE", *MANAGER_SERVICE_ACCOUNT_VARIABLES)


def is_credential_override(*, name: str) -> bool:
    """Whether `name` is in the closed inherited credential-override set."""
    upper = name.upper()
    if upper in EXACT_CREDENTIAL_OVERRIDES:
        return True
    return upper.startswith(CREDENTIAL_OVERRIDE_PREFIXES)


def scrubbed_environment(*, environ: Mapping[str, str]) -> dict[str, str]:
    """A copy of `environ` carrying only the entries outside the closed set.

    Built by copying survivors, never by reading or deleting an override's value.
    """
    return {name: value for name, value in environ.items() if not is_credential_override(name=name)}


def removed_override_names(*, environ: Mapping[str, str]) -> tuple[str, ...]:
    """The names the scrub removes, sorted — for a secret-free diagnostic.

    NAMES ONLY. A diagnostic that carried the values would defeat the scrub it reports on.
    """
    return tuple(sorted(name for name in environ if is_credential_override(name=name)))
