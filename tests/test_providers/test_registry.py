from __future__ import annotations

import pytest

from azure_functions_knowledge.errors import ConfigurationError
from azure_functions_knowledge.providers.base import (
    _PROVIDER_REGISTRY,
    create_provider,
    get_registered_providers,
    register_provider,
)
from azure_functions_knowledge.types import Document


class _DummyProvider:
    def __init__(self, *, connection: str, **kwargs: object) -> None:
        self.connection = connection

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        return []

    def get_document(self, document_id: str) -> Document:
        return Document(
            document_id=document_id,
            content="",
            title="",
            url="",
            source="dummy",
        )

    def close(self) -> None:
        pass


class TestProviderRegistry:
    def test_register_and_create(self) -> None:
        register_provider("dummy", _DummyProvider)
        try:
            prov = create_provider("dummy", connection="test")
            assert prov is not None
        finally:
            _PROVIDER_REGISTRY.pop("dummy", None)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown provider"):
            create_provider("nonexistent_xyz", connection="tok")

    def test_get_registered_providers(self) -> None:
        providers = get_registered_providers()
        assert isinstance(providers, list)
        assert providers == sorted(providers)
