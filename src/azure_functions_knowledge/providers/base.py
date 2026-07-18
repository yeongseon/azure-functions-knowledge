from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ..errors import ConfigurationError
from ..types import Document

_PROVIDER_REGISTRY: dict[str, type[KnowledgeProvider]] = {}


@runtime_checkable
class KnowledgeProvider(Protocol):
    """Protocol that all knowledge providers must satisfy."""

    def __init__(
        self, *, connection: str | Mapping[str, str], **kwargs: Any
    ) -> None: ...

    def search(self, query: str, *, top: int = 5) -> list[Document]: ...

    def get_document(self, document_id: str) -> Document: ...

    def close(self) -> None: ...


def register_provider(name: str, provider_cls: type[KnowledgeProvider]) -> None:
    _PROVIDER_REGISTRY[name] = provider_cls


def create_provider(
    name: str,
    *,
    connection: str | Mapping[str, str],
    **kwargs: Any,
) -> KnowledgeProvider:
    """Create a provider instance by registered name."""
    provider_cls = _PROVIDER_REGISTRY.get(name)
    if provider_cls is None:
        available = sorted(_PROVIDER_REGISTRY.keys())
        msg = f"Unknown provider '{name}'. Available: {available}"
        raise ConfigurationError(msg)
    # Provider-specific kwargs are validated by each provider's __init__.
    # A typed config layer (e.g. Unpack[ProviderConfig]) is deferred until the
    # Python floor reaches 3.11+ or typing_extensions is adopted; on 3.10 a
    # TypedDict cannot be connected to **kwargs in a type-safe way. See #32.
    return provider_cls(connection=connection, **kwargs)


def get_registered_providers() -> list[str]:
    return sorted(_PROVIDER_REGISTRY.keys())
