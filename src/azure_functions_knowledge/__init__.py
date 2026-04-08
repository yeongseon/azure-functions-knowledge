from __future__ import annotations

__version__ = "0.0.1"

import azure_functions_knowledge.providers.notion as _notion_module  # noqa: F401, E402

from .decorator import KnowledgeBindings
from .errors import AuthError, ConfigurationError, KnowledgeError, ProviderError
from .providers.base import (
    KnowledgeProvider,
    create_provider,
    get_registered_providers,
    register_provider,
)
from .types import Document

__all__ = [
    "__version__",
    "AuthError",
    "ConfigurationError",
    "Document",
    "KnowledgeBindings",
    "KnowledgeError",
    "KnowledgeProvider",
    "ProviderError",
    "create_provider",
    "get_registered_providers",
    "register_provider",
]
