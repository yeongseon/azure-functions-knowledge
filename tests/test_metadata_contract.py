"""Tests for the formalized ``knowledge`` metadata contract."""

from __future__ import annotations

from typing import Any

import pytest

from azure_functions_knowledge._metadata import (
    KNOWLEDGE_METADATA_VERSION,
    METADATA_ATTR,
    NAMESPACE,
    KnowledgeMetadata,
    read_knowledge_metadata,
    set_knowledge_metadata,
)
from azure_functions_knowledge.decorator import KnowledgeBindings
from azure_functions_knowledge.providers.base import register_provider
from azure_functions_knowledge.types import Document


class _FakeProvider:
    def __init__(self, *, connection: str | dict[str, str], **kwargs: Any) -> None:
        self.connection = connection

    def search(self, query: str, *, top: int = 5) -> list[Document]:  # pragma: no cover
        return []

    def get_document(self, document_id: str) -> Document:  # pragma: no cover
        return Document(
            document_id=document_id,
            content="c",
            title="t",
            url="u",
            source="fake",
        )

    def close(self) -> None:  # pragma: no cover - trivial
        pass


register_provider("contract-fake", _FakeProvider)


@pytest.fixture()
def kb() -> KnowledgeBindings:
    return KnowledgeBindings()


class TestMetadataContract:
    def test_constants(self) -> None:
        assert NAMESPACE == "knowledge"
        assert KNOWLEDGE_METADATA_VERSION == 1
        assert METADATA_ATTR == "_azure_functions_metadata"

    def test_set_and_read_roundtrip(self) -> None:
        def fn() -> None:  # pragma: no cover - never invoked
            ...

        def wrapper() -> None:  # pragma: no cover - never invoked
            ...

        payload: KnowledgeMetadata = {
            "version": KNOWLEDGE_METADATA_VERSION,
            "mode": "input",
            "provider": "contract-fake",
            "arg_name": "docs",
            "query": "static",
            "top": 3,
        }
        set_knowledge_metadata(wrapper, fn, payload)

        got = read_knowledge_metadata(wrapper)
        assert got == payload
        # Writing publishes on the wrapper, not the original function.
        assert read_knowledge_metadata(fn) is None

    def test_set_preserves_other_namespaces(self) -> None:
        def fn() -> None:  # pragma: no cover - never invoked
            ...

        def wrapper() -> None:  # pragma: no cover - never invoked
            ...

        setattr(fn, METADATA_ATTR, {"db": {"version": 1}})
        payload: KnowledgeMetadata = {
            "version": KNOWLEDGE_METADATA_VERSION,
            "mode": "inject_client",
            "provider": "contract-fake",
            "arg_name": "client",
        }
        set_knowledge_metadata(wrapper, fn, payload)

        combined = getattr(wrapper, METADATA_ATTR)
        assert combined["db"] == {"version": 1}
        assert combined[NAMESPACE] == payload

    def test_read_returns_none_for_missing_attr(self) -> None:
        def fn() -> None:  # pragma: no cover - never invoked
            ...

        assert read_knowledge_metadata(fn) is None

    def test_read_returns_none_for_non_dict_attr(self) -> None:
        def fn() -> None:  # pragma: no cover - never invoked
            ...

        setattr(fn, METADATA_ATTR, "not-a-dict")
        assert read_knowledge_metadata(fn) is None

    def test_read_returns_none_for_missing_namespace(self) -> None:
        def fn() -> None:  # pragma: no cover - never invoked
            ...

        setattr(fn, METADATA_ATTR, {"db": {"version": 1}})
        assert read_knowledge_metadata(fn) is None

    def test_read_returns_none_for_non_dict_namespace(self) -> None:
        def fn() -> None:  # pragma: no cover - never invoked
            ...

        setattr(fn, METADATA_ATTR, {NAMESPACE: "not-a-dict"})
        assert read_knowledge_metadata(fn) is None

    def test_decorator_publishes_typed_input_metadata(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, docs: list[Document]) -> list[Document]:  # pragma: no cover
            return docs

        wrapped = kb.input(
            "docs",
            provider="contract-fake",
            query="hello",
            connection="token",
        )(handler)

        meta = read_knowledge_metadata(wrapped)
        assert meta is not None
        assert meta["version"] == KNOWLEDGE_METADATA_VERSION
        assert meta["mode"] == "input"
        assert meta["provider"] == "contract-fake"
        assert meta["arg_name"] == "docs"
        assert meta["query"] == "static"
        assert meta["top"] == 5

    def test_decorator_publishes_typed_inject_client_metadata(self, kb: KnowledgeBindings) -> None:
        def handler(req: Any, client: Any) -> Any:  # pragma: no cover
            return client

        wrapped = kb.inject_client(
            "client",
            provider="contract-fake",
            connection="token",
        )(handler)

        meta = read_knowledge_metadata(wrapped)
        assert meta is not None
        assert meta["mode"] == "inject_client"
        assert meta["arg_name"] == "client"
        assert "query" not in meta
        assert "top" not in meta
