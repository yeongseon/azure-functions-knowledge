from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from azure_functions_knowledge.errors import AuthError, ProviderError
from azure_functions_knowledge.providers.notion import (
    NotionProvider,
    _blocks_to_text,
    _extract_title,
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


def _make_block(text: str, block_type: str = "paragraph") -> dict[str, Any]:
    return {
        "type": block_type,
        block_type: {
            "rich_text": [{"plain_text": text}],
        },
    }


class TestPageToDocument:
    def test_converts_page(self) -> None:
        page = _make_page()
        doc = _page_to_document(page)
        assert doc is not None
        assert doc.document_id == "page-1"
        assert doc.title == "Test Page"
        assert doc.source == "notion"
        assert doc.content == ""

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


class TestNotionProvider:
    def test_missing_notion_client_raises(self) -> None:
        with patch("azure_functions_knowledge.providers.notion._HAS_NOTION", False):
            with pytest.raises(ProviderError, match="notion-client is required"):
                NotionProvider(connection="tok")

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

    def test_search(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [_make_page("p1", "Page 1"), _make_page("p2", "Page 2")]
        }
        with patch(
            "azure_functions_knowledge.providers.notion.NotionClient",
            return_value=mock_client,
        ):
            provider = NotionProvider(connection="tok")
            results = provider.search("test query", top=2)

        assert len(results) == 2
        assert results[0].document_id == "p1"
        assert results[1].title == "Page 2"
        mock_client.search.assert_called_once_with(
            query="test query",
            page_size=2,
            filter={"value": "page", "property": "object"},
        )

    def test_get_document(self) -> None:
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = _make_page("p1", "Full Page")
        mock_client.blocks.children.list.return_value = {"results": [_make_block("Block text")]}
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
