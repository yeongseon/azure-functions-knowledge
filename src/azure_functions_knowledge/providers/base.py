from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ..errors import ConfigurationError
from ..types import Document

_PROVIDER_REGISTRY: dict[str, type[KnowledgeProvider]] = {}


@runtime_checkable
class KnowledgeProvider(Protocol):
    """Protocol that all knowledge providers must satisfy."""

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
    return provider_cls(connection=connection, **kwargs)  # type: ignore[call-arg]


def get_registered_providers() -> list[str]:
    return sorted(_PROVIDER_REGISTRY.keys())
