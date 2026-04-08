from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from ..auth import resolve_connection
from ..errors import AuthError, ProviderError
from ..types import Document
from .base import register_provider

logger = logging.getLogger(__name__)

try:
    from notion_client import Client as NotionClient
    from notion_client.errors import APIResponseError

    _HAS_NOTION = True
except ImportError:
    _HAS_NOTION = False


class NotionProvider:
    """Knowledge provider backed by the Notion API."""

    def __init__(
        self,
        *,
        connection: str | Mapping[str, str],
        **kwargs: Any,
    ) -> None:
        if not _HAS_NOTION:
            msg = (
                "notion-client is required for NotionProvider. "
                "Install it with: pip install azure-functions-knowledge[notion]"
            )
            raise ProviderError(msg)

        if isinstance(connection, str):
            token = resolve_connection(connection)
        else:
            token_value = connection.get("token") or connection.get("api_key")
            if token_value is None:
                msg = "NotionProvider connection mapping must contain 'token' or 'api_key'"
                raise AuthError(msg)
            token = resolve_connection(str(token_value))

        try:
            self._client: Any = NotionClient(auth=token)
        except Exception as exc:
            msg = f"Failed to initialize Notion client: {exc}"
            raise AuthError(msg) from exc

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        try:
            response = self._client.search(
                query=query,
                page_size=top,
                filter={"value": "page", "property": "object"},
            )
        except APIResponseError as exc:
            msg = f"Notion API error during search: {exc}"
            raise ProviderError(msg) from exc

        results: list[Document] = []
        for page in response.get("results", []):
            doc = _page_to_document(page)
            if doc is not None:
                results.append(doc)
        return results

    def get_document(self, document_id: str) -> Document:
        try:
            page = self._client.pages.retrieve(page_id=document_id)
        except APIResponseError as exc:
            msg = f"Notion API error retrieving page {document_id}: {exc}"
            raise ProviderError(msg) from exc

        blocks_response = self._client.blocks.children.list(block_id=document_id)
        blocks = blocks_response.get("results", [])

        title = _extract_title(page)
        content = _blocks_to_text(blocks)
        url = page.get("url", "")

        return Document(
            document_id=document_id,
            content=content,
            title=title,
            url=url,
            source="notion",
            metadata={"blocks": blocks, "properties": page.get("properties", {})},
        )

    def close(self) -> None:
        pass


def _page_to_document(page: dict[str, Any]) -> Document | None:
    page_id = page.get("id", "")
    if not page_id:
        return None

    title = _extract_title(page)
    url = page.get("url", "")

    return Document(
        document_id=page_id,
        content="",
        title=title,
        url=url,
        source="notion",
        metadata={"properties": page.get("properties", {})},
    )


def _extract_title(page: dict[str, Any]) -> str:
    properties = page.get("properties", {})
    for prop in properties.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return "".join(part.get("plain_text", "") for part in title_parts)
    return ""


def _blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for block in blocks:
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        rich_texts = block_data.get("rich_text", [])
        for rt in rich_texts:
            plain = rt.get("plain_text", "")
            if plain:
                texts.append(plain)
    return "\n".join(texts)


if _HAS_NOTION:
    register_provider("notion", NotionProvider)
