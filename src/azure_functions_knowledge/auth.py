from __future__ import annotations

import os
import re

from .errors import ConfigurationError

_ENV_PATTERN = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")


def resolve_connection(value: str) -> str:
    """Resolve ``%VAR%`` placeholders in *value* with environment variables.

    Raises :class:`ConfigurationError` when a referenced variable is not set.
    """

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            msg = f"Environment variable '{var_name}' referenced in connection string is not set"
            raise ConfigurationError(msg)
        return env_value

    return _ENV_PATTERN.sub(_replace, value)
