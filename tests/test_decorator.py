from __future__ import annotations

import inspect
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import pytest

from azure_functions_knowledge.decorator import KnowledgeBindings
from azure_functions_knowledge.errors import ConfigurationError
from azure_functions_knowledge.providers.base import register_provider
from azure_functions_knowledge.types import Document


class FakeProvider:
    def __init__(self, *, connection: str | dict[str, str], **kwargs: Any) -> None:
        self.connection = connection
        self.kwargs = kwargs
        self.closed = False

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        return [
            Document(
                document_id=f"doc-{i}",
                content=f"Result for: {query}",
                title=f"Doc {i}",
                url=f"https://example.com/{i}",
                source="fake",
            )
            for i in range(top)
        ]

    def get_document(self, document_id: str) -> Document:
        return Document(
            document_id=document_id,
            content="Full content",
            title="Full doc",
            url="https://example.com/full",
            source="fake",
        )

    def close(self) -> None:
        self.closed = True


register_provider("fake", FakeProvider)


@pytest.fixture()
def kb() -> KnowledgeBindings:
    return KnowledgeBindings()


class TestInputDecorator:
    def test_static_query(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="fake", query="hello", connection="token")
        def handler(timer: Any, docs: list[Document]) -> list[Document]:
            return docs

        result = handler(timer=MagicMock())
        assert len(result) == 5
        assert result[0].content == "Result for: hello"

    def test_callable_query(self, kb: KnowledgeBindings) -> None:
        @kb.input(
            "docs",
            provider="fake",
            query=lambda req: f"search for {req}",
            connection="token",
        )
        def handler(req: str, docs: list[Document]) -> list[Document]:
            return docs

        result = handler(req="test")
        assert result[0].content == "Result for: search for test"

    def test_custom_top(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="fake", query="q", top=3, connection="tok")
        def handler(timer: Any, docs: list[Document]) -> int:
            return len(docs)

        assert handler(timer=MagicMock()) == 3

    def test_top_less_than_1_raises(self, kb: KnowledgeBindings) -> None:
        with pytest.raises(ConfigurationError, match="top must be >= 1"):
            kb.input("docs", provider="fake", query="q", top=0, connection="tok")

    def test_signature_hides_injected_param(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="fake", query="q", connection="tok")
        def handler(timer: Any, docs: list[Document]) -> None:
            pass

        sig = inspect.signature(handler)
        assert "docs" not in sig.parameters
        assert "timer" in sig.parameters

    def test_duplicate_input_raises(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="fake", query="q", connection="tok")
        def handler(timer: Any, docs: list[Document]) -> None:
            pass

        with pytest.raises(ConfigurationError, match="cannot be applied twice"):
            kb.input("docs", provider="fake", query="q", connection="tok")(handler)

    def test_input_then_inject_client_raises(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="fake", query="q", connection="tok")
        def handler(timer: Any, docs: list[Document]) -> None:
            pass

        with pytest.raises(ConfigurationError, match="Cannot combine"):
            kb.inject_client("docs", provider="fake", connection="tok")(handler)

    def test_bad_arg_name_raises(self, kb: KnowledgeBindings) -> None:
        with pytest.raises(ConfigurationError, match="not found"):

            @kb.input("nonexistent", provider="fake", query="q", connection="tok")
            def handler(timer: Any) -> None:
                pass

    def test_reserved_arg_name_raises(self, kb: KnowledgeBindings) -> None:
        with pytest.raises(ConfigurationError, match="reserved"):

            @kb.input("req", provider="fake", query="q", connection="tok")
            def handler(req: Any) -> None:
                pass

    def test_unknown_provider_raises(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="nonexistent", query="q", connection="tok")
        def handler(timer: Any, docs: list[Document]) -> None:
            pass

        with pytest.raises(ConfigurationError, match="Unknown provider"):
            handler(timer=MagicMock())

    def test_callable_query_bad_params_raises(self, kb: KnowledgeBindings) -> None:
        with pytest.raises(ConfigurationError, match="not found in handler"):

            @kb.input(
                "docs",
                provider="fake",
                query=lambda unknown_param: "q",
                connection="tok",
            )
            def handler(timer: Any, docs: list[Document]) -> None:
                pass

    def test_callable_query_varargs_raises(self, kb: KnowledgeBindings) -> None:
        def bad_resolver(*args: Any) -> str:
            return "q"

        with pytest.raises(ConfigurationError, match="must not use"):

            @kb.input("docs", provider="fake", query=bad_resolver, connection="tok")
            def handler(timer: Any, docs: list[Document]) -> None:
                pass


class TestInjectClientDecorator:
    def test_injects_provider(self, kb: KnowledgeBindings) -> None:
        captured: list[Any] = []

        @kb.inject_client("client", provider="fake", connection="my-token")
        def handler(timer: Any, client: Any) -> None:
            captured.append(client)

        handler(timer=MagicMock())
        assert len(captured) == 1
        assert hasattr(captured[0], "search")
        assert hasattr(captured[0], "get_document")

    def test_provider_closed_after_handler(self, kb: KnowledgeBindings) -> None:
        captured: list[Any] = []

        @kb.inject_client("client", provider="fake", connection="tok")
        def handler(timer: Any, client: Any) -> None:
            captured.append(client)

        handler(timer=MagicMock())
        assert captured[0].closed

    def test_provider_closed_on_error(self, kb: KnowledgeBindings) -> None:
        captured: list[Any] = []

        @kb.inject_client("client", provider="fake", connection="tok")
        def handler(timer: Any, client: Any) -> None:
            captured.append(client)
            msg = "boom"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="boom"):
            handler(timer=MagicMock())
        assert captured[0].closed

    def test_signature_hides_injected_param(self, kb: KnowledgeBindings) -> None:
        @kb.inject_client("client", provider="fake", connection="tok")
        def handler(timer: Any, client: Any) -> None:
            pass

        sig = inspect.signature(handler)
        assert "client" not in sig.parameters
        assert "timer" in sig.parameters

    def test_inject_client_then_input_raises(self, kb: KnowledgeBindings) -> None:
        @kb.inject_client("client", provider="fake", connection="tok")
        def handler(timer: Any, client: Any) -> None:
            pass

        with pytest.raises(ConfigurationError, match="Cannot combine"):
            kb.input("client", provider="fake", query="q", connection="tok")(handler)

    def test_duplicate_inject_client_raises(self, kb: KnowledgeBindings) -> None:
        @kb.inject_client("client", provider="fake", connection="tok")
        def handler(timer: Any, client: Any) -> None:
            pass

        with pytest.raises(ConfigurationError, match="cannot be applied twice"):
            kb.inject_client("client", provider="fake", connection="tok")(handler)


class TestAsyncHandlers:
    @pytest.mark.asyncio()
    async def test_async_input(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="fake", query="async-q", connection="tok")
        async def handler(timer: Any, docs: list[Document]) -> list[Document]:
            return docs

        result = await handler(timer=MagicMock())
        assert len(result) == 5
        assert result[0].content == "Result for: async-q"

    @pytest.mark.asyncio()
    async def test_async_inject_client(self, kb: KnowledgeBindings) -> None:
        captured: list[Any] = []

        @kb.inject_client("client", provider="fake", connection="tok")
        async def handler(timer: Any, client: Any) -> None:
            captured.append(client)
            results = await client.search("test")
            captured.append(results)

        await handler(timer=MagicMock())
        assert len(captured) == 2
        assert len(captured[1]) == 5

    @pytest.mark.asyncio()
    async def test_async_input_propagates_error_and_closes(
        self, kb: KnowledgeBindings
    ) -> None:
        created: list[FakeProvider] = []

        class TrackingProvider(FakeProvider):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                created.append(self)

        register_provider("tracking", TrackingProvider)

        @kb.input("docs", provider="tracking", query="boom", connection="tok")
        async def handler(timer: Any, docs: list[Document]) -> None:
            raise RuntimeError("handler failed")

        with pytest.raises(RuntimeError, match="handler failed"):
            await handler(timer=MagicMock())

        # The exception must propagate AND the provider must be closed,
        # mirroring synchronous ``with`` semantics.
        assert len(created) == 1
        assert created[0].closed is True


class TestToolkitMetadata:
    def test_input_publishes_metadata(self, kb: KnowledgeBindings) -> None:
        @kb.input("docs", provider="fake", query="hello", connection="token")
        def handler(timer: Any, docs: list[Document]) -> list[Document]:
            return docs

        meta = getattr(handler, "_azure_functions_metadata")["knowledge"]
        assert meta == {
            "version": 1,
            "mode": "input",
            "provider": "fake",
            "arg_name": "docs",
            "query": "static",
            "top": 5,
        }

    def test_input_dynamic_query_metadata(self, kb: KnowledgeBindings) -> None:
        @kb.input(
            "docs",
            provider="fake",
            query=lambda req: str(req),
            connection="token",
            top=3,
        )
        def handler(req: Any, docs: list[Document]) -> list[Document]:
            return docs

        meta = getattr(handler, "_azure_functions_metadata")["knowledge"]
        assert meta["query"] == "dynamic"
        assert meta["top"] == 3

    def test_inject_client_publishes_metadata(self, kb: KnowledgeBindings) -> None:
        @kb.inject_client("client", provider="fake", connection="tok")
        def handler(timer: Any, client: Any) -> None:
            return None

        meta = getattr(handler, "_azure_functions_metadata")["knowledge"]
        assert meta == {
            "version": 1,
            "mode": "inject_client",
            "provider": "fake",
            "arg_name": "client",
        }


class TestAsyncProxy:
    @pytest.mark.asyncio()
    async def test_callable_offloaded_and_attrs_and_close(self) -> None:
        import asyncio

        from azure_functions_knowledge.decorator import AsyncProxy

        class Target:
            name = "target"

            def __init__(self) -> None:
                self.closed = False

            def echo(self, value: str) -> str:
                return value

            def close(self) -> None:
                self.closed = True

        target = Target()
        proxy = AsyncProxy(target)
        # Non-callable attribute is returned as-is.
        assert proxy.name == "target"
        # Callable attribute is offloaded via asyncio.to_thread and awaitable.
        with mock.patch(
            "azure_functions_knowledge.decorator.asyncio.to_thread",
            wraps=asyncio.to_thread,
        ) as to_thread:
            assert await proxy.echo("hi") == "hi"
        # Enforce the offload so a regression to a blocking call is caught.
        to_thread.assert_called_once()
        assert to_thread.call_args.args[0] == target.echo
        # close is intentionally synchronous.
        proxy.close()
        assert target.closed is True


class TestGetDecoratorsDefensive:
    def test_non_frozenset_marker_is_ignored(self) -> None:
        from azure_functions_knowledge.decorator import _get_decorators

        def fn() -> None:
            pass

        # A corrupted / unexpected marker value must degrade to an empty set
        # rather than raise, so composition checks stay robust.
        setattr(fn, "_knowledge_decorators", "not-a-frozenset")
        assert _get_decorators(fn) == frozenset()
