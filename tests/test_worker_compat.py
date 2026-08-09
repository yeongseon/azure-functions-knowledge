"""Worker-indexing compatibility regression tests.

The Azure Functions Python library resolves the "user function" for a
registered handler by recursively following ``__wrapped__``
(``function_app._get_user_function``). If a decorator wrapper exposes
``__wrapped__`` (as ``functools.wraps`` sets it), the library binds the
original handler instead of the wrapper — re-exposing the injected knowledge
parameter to the worker's argument indexing and defeating the decorator.

These tests assert the wrapper stays worker-safe without requiring a live
``func start`` host: no ``__wrapped__``, a cleaned public signature, metadata
on the wrapper (not the original), and preserved identity attributes.

Ref: https://github.com/yeongseon/azure-functions-knowledge-python/issues/44
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock

import pytest

from azure_functions_knowledge.decorator import KnowledgeBindings
from azure_functions_knowledge.providers.base import register_provider
from azure_functions_knowledge.types import Document

_TOOLKIT_META_ATTR = "_azure_functions_metadata"
_KNOWLEDGE_DECORATOR_ATTR = "_knowledge_decorators"


class _FakeProvider:
    def __init__(self, *, connection: str | dict[str, str], **kwargs: Any) -> None:
        self.connection = connection

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        return [
            Document(
                document_id="doc-0",
                content=f"Result for: {query}",
                title="Doc 0",
                url="https://example.com/0",
                source="fake",
            )
        ]

    def get_document(self, document_id: str) -> Document:  # pragma: no cover
        return Document(
            document_id=document_id,
            content="Full content",
            title="Full doc",
            url="https://example.com/full",
            source="fake",
        )

    def close(self) -> None:  # pragma: no cover - trivial
        pass


register_provider("worker-compat-fake", _FakeProvider)


@pytest.fixture()
def kb() -> KnowledgeBindings:
    return KnowledgeBindings()


def _input_decorator(kb: KnowledgeBindings) -> Any:
    return kb.input(
        "docs",
        provider="worker-compat-fake",
        query="hello",
        connection="token",
    )


def _inject_decorator(kb: KnowledgeBindings) -> Any:
    return kb.inject_client(
        "client",
        provider="worker-compat-fake",
        connection="token",
    )


class TestWorkerIndexingCompat:
    def test_input_sync_wrapper_has_no_wrapped(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, docs: list[Document]) -> list[Document]:
            return docs

        original = handler
        wrapped = _input_decorator(kb)(handler)

        # The library follows __wrapped__ to the original handler; it must be absent.
        assert not hasattr(wrapped, "__wrapped__")
        # Original handler must stay clean — inspect.unwrap must not reach it.
        assert inspect.unwrap(wrapped) is wrapped
        assert original is not wrapped

    def test_input_async_wrapper_has_no_wrapped(self, kb: KnowledgeBindings) -> None:
        async def handler(req: Any, docs: list[Document]) -> list[Document]:
            return docs

        wrapped = _input_decorator(kb)(handler)

        assert not hasattr(wrapped, "__wrapped__")
        assert inspect.unwrap(wrapped) is wrapped

    def test_inject_client_wrapper_has_no_wrapped(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, client: Any) -> Any:
            return client

        wrapped = _inject_decorator(kb)(handler)

        assert not hasattr(wrapped, "__wrapped__")
        assert inspect.unwrap(wrapped) is wrapped

    def test_public_signature_hides_injected_param(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, docs: list[Document]) -> list[Document]:
            return docs

        wrapped = _input_decorator(kb)(handler)

        params = inspect.signature(wrapped).parameters
        # The injected 'docs' arg is removed; the trigger 'req' param remains so
        # the worker still indexes the handler.
        assert "docs" not in params
        assert "req" in params

    def test_metadata_lives_on_wrapper_not_original(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, docs: list[Document]) -> list[Document]:
            return docs

        original = handler
        wrapped = _input_decorator(kb)(handler)

        # Toolkit metadata is published on the wrapper for sibling tools...
        assert hasattr(wrapped, _TOOLKIT_META_ATTR)
        # ...and must not leak back onto the original handler.
        assert _TOOLKIT_META_ATTR not in original.__dict__
        assert _KNOWLEDGE_DECORATOR_ATTR not in original.__dict__

    def test_identity_attrs_preserved(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, docs: list[Document]) -> list[Document]:
            """Docstring stays."""
            return docs

        wrapped = _input_decorator(kb)(handler)

        assert wrapped.__name__ == "handler"
        assert wrapped.__doc__ == "Docstring stays."
        assert wrapped.__module__ == handler.__module__

    def test_wrapper_still_invokes_handler(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, docs: list[Document]) -> list[Document]:
            return docs

        wrapped = _input_decorator(kb)(handler)
        result = wrapped(req=MagicMock())

        assert len(result) == 1
        assert result[0].content == "Result for: hello"
