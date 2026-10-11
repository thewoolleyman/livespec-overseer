"""Inherited credential taints for installed LPM subprocess scenarios."""

__all__: list[str] = [
    "credential_environment",
    "credential_taints",
]

_TAINTS = (
    "sk-ant-inherited-api-key-sentinel",
    "sk-ant-inherited-oauth-sentinel",
    "op-inherited-service-token-sentinel",
)


def credential_environment() -> dict[str, str]:
    """Credential overrides that every child boundary must keep out of results."""
    return {
        "ANTHROPIC_API_KEY": _TAINTS[0],
        "CLAUDE_CODE_OAUTH_TOKEN": _TAINTS[1],
        "OP_SERVICE_ACCOUNT_TOKEN": _TAINTS[2],
    }


def credential_taints() -> tuple[str, ...]:
    """The opaque fixture bytes forbidden from either output stream."""
    return _TAINTS
