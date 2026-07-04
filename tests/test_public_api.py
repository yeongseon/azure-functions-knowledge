from __future__ import annotations

from importlib.metadata import version

import azure_functions_knowledge


class TestPublicApi:
    def test_version_matches_distribution_metadata(self) -> None:
        assert azure_functions_knowledge.__version__ == version("azure-functions-knowledge-python")

    def test_all_exports(self) -> None:
        expected = {
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
        }
        assert set(azure_functions_knowledge.__all__) == expected

    def test_imports_are_accessible(self) -> None:
        assert azure_functions_knowledge.Document is not None
        assert azure_functions_knowledge.KnowledgeBindings is not None
        assert azure_functions_knowledge.KnowledgeProvider is not None
        assert azure_functions_knowledge.ConfigurationError is not None
        assert azure_functions_knowledge.ProviderError is not None
        assert azure_functions_knowledge.AuthError is not None
        assert azure_functions_knowledge.KnowledgeError is not None
        assert azure_functions_knowledge.create_provider is not None
        assert azure_functions_knowledge.register_provider is not None
        assert azure_functions_knowledge.get_registered_providers is not None

    def test_notion_auto_registered(self) -> None:
        providers = azure_functions_knowledge.get_registered_providers()
        assert "notion" in providers
