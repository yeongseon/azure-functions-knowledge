from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from azure_functions_knowledge.errors import AuthError, ConfigurationError, ProviderError
from azure_functions_knowledge.providers.base import create_provider
from azure_functions_knowledge.providers.notion import (
    NotionProvider,
    _blocks_to_text,
    _extract_title,
    _fetch_all_blocks,
    _page_to_document,
)


def _make_page(
    page_id: str = "page-1",
    title: str = "Test Page",
    url: str = "https://notion.so/test",
) -> dict[str, Any]:
    return {
        "id": page_id,
        "object": "page",
        "url": url,
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


def _make_block(
    text: str,
    block_type: str = "paragraph",
    *,
    block_id: str | None = None,
    has_children: bool = False,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": block_type,
        block_type: {
            "rich_text": [{"plain_text": text}],
        },
        "has_children": has_children,
    }
    if block_id is not None:
        block["id"] = block_id
    return block


class TestPageToDocument:
    def test_defaults_to_empty_content(self) -> None:
        page = _make_page()
        doc = _page_to_document(page)
        assert doc is not None
        assert doc.document_id == "page-1"
        assert doc.title == "Test Page"
        assert doc.source == "notion"
        assert doc.content == ""

    def test_accepts_content_override(self) -> None:
        page = _make_page()
        doc = _page_to_document(page, content="hello world")
        assert doc is not None
        assert doc.content == "hello world"

    def test_missing_id_returns_none(self) -> None:
        page = _make_page()
        page["id"] = ""
        assert _page_to_document(page) is None


class TestExtractTitle:
    def test_extracts_title(self) -> None:
        page = _make_page(title="Hello")
        assert _extract_title(page) == "Hello"

    def test_no_title_property(self) -> None:
        page: dict[str, Any] = {"properties": {}}
        assert _extract_title(page) == ""

    def test_multi_part_title(self) -> None:
        page: dict[str, Any] = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [
                        {"plain_text": "Hello "},
                        {"plain_text": "World"},
                    ],
                }
            }
        }
        assert _extract_title(page) == "Hello World"


class TestBlocksToText:
    def test_single_block(self) -> None:
        blocks = [_make_block("Hello")]
        assert _blocks_to_text(blocks) == "Hello"

    def test_multiple_blocks(self) -> None:
        blocks = [_make_block("Line 1"), _make_block("Line 2")]
        assert _blocks_to_text(blocks) == "Line 1\nLine 2"

    def test_empty_blocks(self) -> None:
        assert _blocks_to_text([]) == ""

    def test_block_without_rich_text(self) -> None:
        blocks = [{"type": "divider", "divider": {}}]
        assert _blocks_to_text(blocks) == ""

    def test_non_text_blocks_are_skipped(self) -> None:
        blocks = [
            {"type": "image", "image": {"file": {"url": "https://x"}}},
            _make_block("Hello"),
            {"type": "embed", "embed": {"url": "https://y"}},
            {"type": "bookmark", "bookmark": {"url": "https://z"}},
        ]
        assert _blocks_to_text(blocks) == "Hello"

    def test_malformed_rich_text_ignored(self) -> None:
        blocks: list[dict[str, Any]] = [
            {"type": "paragraph", "paragraph": {"rich_text": "not-a-list"}},
            {"type": "paragraph", "paragraph": "not-a-mapping"},
            {"type": "paragraph", "paragraph": {"rich_text": ["not-a-dict"]}},
            _make_block("Kept"),
        ]
        assert _blocks_to_text(blocks) == "Kept"


class TestFetchAllBlocks:
    def test_single_page_no_pagination(self) -> None:
        client = MagicMock()
        client.blocks.children.list.return_value = {
            "results": [_make_block("A"), _make_block("B")],
            "has_more": False,
        }
        blocks = _fetch_all_blocks(client, "root", max_depth=8, max_blocks=1000)
        assert len(blocks) == 2
        client.blocks.children.list.assert_called_once_with(block_id="root", page_size=100)

    def test_paginates_when_has_more(self) -> None:
        client = MagicMock()
        client.blocks.children.list.side_effect = [
            {
                "results": [_make_block("A"), _make_block("B")],
                "has_more": True,
                "next_cursor": "cursor-1",
            },
            {
                "results": [_make_block("C")],
                "has_more": False,
            },
        ]
        blocks = _fetch_all_blocks(client, "root", max_depth=8, max_blocks=1000)
        assert [b["paragraph"]["rich_text"][0]["plain_text"] for b in blocks] == [
            "A",
            "B",
            "C",
        ]
        first_call = client.blocks.children.list.call_args_list[0]
        second_call = client.blocks.children.list.call_args_list[1]
        assert first_call.kwargs == {"block_id": "root", "page_size": 100}
        assert second_call.kwargs == {
            "block_id": "root",
            "page_size": 100,
            "start_cursor": "cursor-1",
        }

    def test_recurses_into_has_children(self) -> None:
        client = MagicMock()

        def list_side_effect(**kwargs: Any) -> dict[str, Any]:
            block_id = kwargs["block_id"]
            if block_id == "root":
                return {
                    "results": [
                        _make_block("Parent", block_id="p1", has_children=True),
                        _make_block("Sibling"),
                    ],
                    "has_more": False,
                }
            if block_id == "p1":
                return {
                    "results": [_make_block("Child A"), _make_block("Child B")],
                    "has_more": False,
                }
            return {"results": [], "has_more": False}

        client.blocks.children.list.side_effect = list_side_effect
        blocks = _fetch_all_blocks(client, "root", max_depth=8, max_blocks=1000)
        assert [b["paragraph"]["rich_text"][0]["plain_text"] for b in blocks] == [
            "Parent",
            "Child A",
            "Child B",
            "Sibling",
        ]

    def test_max_depth_truncates_recursion(self) -> None:
        client = MagicMock()

        def list_side_effect(**kwargs: Any) -> dict[str, Any]:
            block_id = kwargs["block_id"]
            if block_id == "root":
                return {
                    "results": [_make_block("D1", block_id="d1", has_children=True)],
                    "has_more": False,
                }
            if block_id == "d1":
                return {
                    "results": [_make_block("D2", block_id="d2", has_children=True)],
                    "has_more": False,
                }
            if block_id == "d2":
                # Should NEVER be reached because max_depth=1 blocks the recursion.
                return {"results": [_make_block("D3")], "has_more": False}
            return {"results": [], "has_more": False}

        client.blocks.children.list.side_effect = list_side_effect
        blocks = _fetch_all_blocks(client, "root", max_depth=1, max_blocks=1000)
        texts = [b["paragraph"]["rich_text"][0]["plain_text"] for b in blocks]
        assert texts == ["D1", "D2"]  # D3 excluded

    def test_max_blocks_caps_output(self) -> None:
        client = MagicMock()
        client.blocks.children.list.return_value = {
            "results": [_make_block(f"B{i}") for i in range(50)],
            "has_more": False,
        }
        blocks = _fetch_all_blocks(client, "root", max_depth=8, max_blocks=5)
        assert len(blocks) == 5

    def test_cycle_guard(self) -> None:
        client = MagicMock()

        # a → b → a (cycle). The guard prevents re-fetching a.
        call_counts: dict[str, int] = {"a": 0, "b": 0}

        def list_side_effect(**kwargs: Any) -> dict[str, Any]:
            block_id = kwargs["block_id"]
            call_counts[block_id] = call_counts.get(block_id, 0) + 1
            if block_id == "a":
                return {
                    "results": [_make_block("From A", block_id="b", has_children=True)],
                    "has_more": False,
                }
            if block_id == "b":
                return {
                    "results": [_make_block("From B", block_id="a", has_children=True)],
                    "has_more": False,
                }
            return {"results": [], "has_more": False}

        client.blocks.children.list.side_effect = list_side_effect
        blocks = _fetch_all_blocks(client, "a", max_depth=8, max_blocks=100)
        # Each block only fetched once thanks to the _seen guard.
        assert call_counts == {"a": 1, "b": 1}
        assert len(blocks) == 2


class TestNotionProvider:
    def test_missing_notion_client_raises(self) -> None:
        with patch("azure_functions_knowledge.providers.notion._HAS_NOTION", False):
            with pytest.raises(ProviderError, match="notion-client is required"):
                NotionProvider(connection="tok")

    def test_create_provider_actionable_error_when_extra_missing(self) -> None:
        # Registry-level: even without the extra, create_provider("notion")
        # reaches the actionable ProviderError, not "Unknown provider".
        with patch("azure_functions_knowledge.providers.notion._HAS_NOTION", False):
            with pytest.raises(ProviderError, match="notion-client is required"):
                create_provider("notion", connection="tok")

    def test_create_provider_unknown_stays_generic(self) -> None:
        # Regression guard: unrelated unknown names still hit the generic path.
        with pytest.raises(ConfigurationError, match="Unknown provider"):
            create_provider("nonexistent-provider", connection="tok")

    def test_string_connection(self) -> None:
        mock_client = MagicMock()
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="my-token")
            assert provider._client is mock_client

    def test_mapping_connection_with_token(self) -> None:
        mock_client = MagicMock()
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection={"token": "my-token"})
            assert provider._client is mock_client

    def test_mapping_connection_with_api_key(self) -> None:
        mock_client = MagicMock()
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection={"api_key": "my-key"})
            assert provider._client is mock_client

    def test_mapping_connection_missing_key_raises(self) -> None:
        with pytest.raises(AuthError, match="must contain"):
            NotionProvider(connection={"host": "localhost"})

    def test_search_populates_content_by_default(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [_make_page("p1", "Page 1"), _make_page("p2", "Page 2")]
        }

        def list_side_effect(**kwargs: Any) -> dict[str, Any]:
            block_id = kwargs["block_id"]
            if block_id == "p1":
                return {"results": [_make_block("Body of P1")], "has_more": False}
            if block_id == "p2":
                return {"results": [_make_block("Body of P2")], "has_more": False}
            return {"results": [], "has_more": False}

        mock_client.blocks.children.list.side_effect = list_side_effect

        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok")
            results = provider.search("test query", top=2)

        assert len(results) == 2
        assert results[0].content == "Body of P1"
        assert results[1].content == "Body of P2"
        mock_client.search.assert_called_once_with(
            query="test query",
            page_size=2,
            filter={"value": "page", "property": "object"},
        )
        # Two block fetches — one per hit.
        assert mock_client.blocks.children.list.call_count == 2

    def test_search_can_disable_content_fetching(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [_make_page("p1", "Page 1")]}
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok", include_content=False)
            results = provider.search("q")

        assert results[0].content == ""
        # No block fetches when include_content=False.
        mock_client.blocks.children.list.assert_not_called()

    def test_search_content_max_chars_truncates(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [_make_page("p1", "Page 1")]}
        mock_client.blocks.children.list.return_value = {
            "results": [_make_block("A" * 500)],
            "has_more": False,
        }
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok", content_max_chars=50)
            results = provider.search("q")
        assert len(results[0].content) == 50

    def test_search_skips_pages_without_id(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [{"id": "", "properties": {}}, _make_page("p1", "OK")]
        }
        mock_client.blocks.children.list.return_value = {
            "results": [_make_block("Kept")],
            "has_more": False,
        }
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok")
            results = provider.search("q")
        # Skipped the empty-id page; kept the good one.
        assert len(results) == 1
        assert results[0].document_id == "p1"

    def test_get_document(self) -> None:
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = _make_page("p1", "Full Page")
        mock_client.blocks.children.list.return_value = {
            "results": [_make_block("Block text")],
            "has_more": False,
        }
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok")
            doc = provider.get_document("p1")

        assert doc.document_id == "p1"
        assert doc.title == "Full Page"
        assert doc.content == "Block text"
        assert doc.source == "notion"
        assert "blocks" in doc.metadata

    def test_get_document_paginates(self) -> None:
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = _make_page("p1", "Multi")
        mock_client.blocks.children.list.side_effect = [
            {
                "results": [_make_block("page-1-a"), _make_block("page-1-b")],
                "has_more": True,
                "next_cursor": "c1",
            },
            {
                "results": [_make_block("page-2-a")],
                "has_more": False,
            },
        ]
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok")
            doc = provider.get_document("p1")

        assert doc.content == "page-1-a\npage-1-b\npage-2-a"

    def test_get_document_recurses_into_children(self) -> None:
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = _make_page("p1", "Nested")

        def list_side_effect(**kwargs: Any) -> dict[str, Any]:
            block_id = kwargs["block_id"]
            if block_id == "p1":
                return {
                    "results": [
                        _make_block("Toggle", block_id="t1", has_children=True),
                        _make_block("After"),
                    ],
                    "has_more": False,
                }
            if block_id == "t1":
                return {
                    "results": [_make_block("Nested")],
                    "has_more": False,
                }
            return {"results": [], "has_more": False}

        mock_client.blocks.children.list.side_effect = list_side_effect
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok")
            doc = provider.get_document("p1")
        assert doc.content == "Toggle\nNested\nAfter"

    def test_get_document_respects_max_depth(self) -> None:
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = _make_page("p1", "Depth")

        def list_side_effect(**kwargs: Any) -> dict[str, Any]:
            block_id = kwargs["block_id"]
            if block_id == "p1":
                return {
                    "results": [_make_block("L1", block_id="d1", has_children=True)],
                    "has_more": False,
                }
            if block_id == "d1":
                return {
                    "results": [_make_block("L2", block_id="d2", has_children=True)],
                    "has_more": False,
                }
            return {"results": [_make_block("Deeper")], "has_more": False}

        mock_client.blocks.children.list.side_effect = list_side_effect
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok", max_depth=1)
            doc = provider.get_document("p1")
        assert "Deeper" not in doc.content
        assert doc.content == "L1\nL2"

    def test_close_is_noop(self) -> None:
        mock_client = MagicMock()
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok")
            provider.close()

    def test_search_api_error(self) -> None:
        mock_client = MagicMock()

        api_error = type("APIResponseError", (Exception,), {})("API error")
        mock_client.search.side_effect = api_error

        with (
            patch(
                "azure_functions_knowledge.providers.notion.NotionClient",
                return_value=mock_client,
            ),
            patch(
                "azure_functions_knowledge.providers.notion.APIResponseError",
                type(api_error),
            ),
        ):
            provider = NotionProvider(connection="tok")
            with pytest.raises(ProviderError, match="Notion API error"):
                provider.search("test")

    def test_search_block_fetch_api_error_becomes_provider_error(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [_make_page("p1", "X")]}
        api_error = type("APIResponseError", (Exception,), {})("boom")
        mock_client.blocks.children.list.side_effect = api_error
        with (
            patch(
                "azure_functions_knowledge.providers.notion.NotionClient",
                return_value=mock_client,
            ),
            patch(
                "azure_functions_knowledge.providers.notion.APIResponseError",
                type(api_error),
            ),
        ):
            provider = NotionProvider(connection="tok")
            with pytest.raises(ProviderError, match="Notion API error fetching blocks"):
                provider.search("test")

    def test_get_document_api_error(self) -> None:
        mock_client = MagicMock()

        api_error = type("APIResponseError", (Exception,), {})("Not found")
        mock_client.pages.retrieve.side_effect = api_error

        with (
            patch(
                "azure_functions_knowledge.providers.notion.NotionClient",
                return_value=mock_client,
            ),
            patch(
                "azure_functions_knowledge.providers.notion.APIResponseError",
                type(api_error),
            ),
        ):
            provider = NotionProvider(connection="tok")
            with pytest.raises(ProviderError, match="Notion API error"):
                provider.get_document("page-1")


class TestNotionProviderInitFailure:
    def test_client_init_failure_raises_auth_error(self) -> None:
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(AuthError, match="Failed to initialize Notion client"):
                NotionProvider(connection="tok")


class TestFetchAllBlocksEdgeCases:
    def test_zero_max_blocks_returns_empty(self) -> None:
        client = MagicMock()
        blocks = _fetch_all_blocks(client, "root", max_depth=8, max_blocks=0)
        assert blocks == []
        client.blocks.children.list.assert_not_called()

    def test_has_more_without_next_cursor_stops(self) -> None:
        client = MagicMock()
        # has_more is True but next_cursor is absent: the loop must break
        # instead of paginating forever.
        client.blocks.children.list.return_value = {
            "results": [_make_block("only")],
            "has_more": True,
        }
        blocks = _fetch_all_blocks(client, "root", max_depth=8, max_blocks=1000)
        assert len(blocks) == 1
        client.blocks.children.list.assert_called_once()