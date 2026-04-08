from __future__ import annotations

from azure_functions_knowledge.errors import (
    AuthError,
    ConfigurationError,
    KnowledgeError,
    ProviderError,
)


class TestErrorHierarchy:
    def test_configuration_error_is_knowledge_error(self) -> None:
        assert issubclass(ConfigurationError, KnowledgeError)

    def test_provider_error_is_knowledge_error(self) -> None:
        assert issubclass(ProviderError, KnowledgeError)

    def test_auth_error_is_knowledge_error(self) -> None:
        assert issubclass(AuthError, KnowledgeError)

    def test_knowledge_error_is_exception(self) -> None:
        assert issubclass(KnowledgeError, Exception)

    def test_raise_configuration_error(self) -> None:
        try:
            raise ConfigurationError("bad config")
        except KnowledgeError as exc:
            assert str(exc) == "bad config"

    def test_raise_provider_error(self) -> None:
        try:
            raise ProviderError("provider failed")
        except KnowledgeError as exc:
            assert str(exc) == "provider failed"

    def test_raise_auth_error(self) -> None:
        try:
            raise AuthError("auth failed")
        except KnowledgeError as exc:
            assert str(exc) == "auth failed"
