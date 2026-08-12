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


DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_BLOCKS = 1000
# Notion API `blocks.children.list` default and max page size.
_NOTION_PAGE_SIZE = 100


class NotionProvider:
    """Knowledge provider backed by the Notion API."""

    def __init__(
        self,
        *,
        connection: str | Mapping[str, str],
        include_content: bool = True,
        content_max_chars: int | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_blocks: int = DEFAULT_MAX_BLOCKS,
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

        self._include_content = include_content
        self._content_max_chars = content_max_chars
        self._max_depth = max_depth
        self._max_blocks = max_blocks

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
            page_id = page.get("id", "")
            if not page_id:
                continue

            if self._include_content:
                try:
                    blocks = self._fetch_all_blocks(page_id)
                except APIResponseError as exc:
                    msg = f"Notion API error fetching blocks for page {page_id}: {exc}"
                    raise ProviderError(msg) from exc
                content = self._render_content(blocks)
            else:
                content = ""

            doc = _page_to_document(page, content=content)
            if doc is not None:
                results.append(doc)
        return results

    def get_document(self, document_id: str) -> Document:
        try:
            page = self._client.pages.retrieve(page_id=document_id)
        except APIResponseError as exc:
            msg = f"Notion API error retrieving page {document_id}: {exc}"
            raise ProviderError(msg) from exc

        blocks = self._fetch_all_blocks(document_id)

        title = _extract_title(page)
        content = self._render_content(blocks)
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

    # ---- helpers -------------------------------------------------------

    def _fetch_all_blocks(self, block_id: str) -> list[dict[str, Any]]:
        return _fetch_all_blocks(
            self._client,
            block_id,
            max_depth=self._max_depth,
            max_blocks=self._max_blocks,
        )

    def _render_content(self, blocks: list[dict[str, Any]]) -> str:
        content = _blocks_to_text(blocks)
        if self._content_max_chars is not None and len(content) > self._content_max_chars:
            content = content[: self._content_max_chars]
        return content


def _page_to_document(
    page: dict[str, Any],
    *,
    content: str = "",
) -> Document | None:
    page_id = page.get("id", "")
    if not page_id:
        return None

    title = _extract_title(page)
    url = page.get("url", "")

    return Document(
        document_id=page_id,
        content=content,
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
        if not isinstance(block_data, Mapping):
            continue
        rich_texts = block_data.get("rich_text", [])
        if not isinstance(rich_texts, list):
            continue
        for rt in rich_texts:
            if not isinstance(rt, Mapping):
                continue
            plain = rt.get("plain_text", "")
            if plain:
                texts.append(plain)
    return "\n".join(texts)


def _fetch_all_blocks(
    client: Any,
    block_id: str,
    *,
    max_depth: int,
    max_blocks: int,
    _depth: int = 0,
    _seen: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch child blocks depth-first, paginating and recursing into children.

    Returns blocks in depth-first order so :func:`_blocks_to_text` produces a
    natural reading order. Respects ``max_depth`` and ``max_blocks`` caps and
    guards against cycles via a per-call ``_seen`` set.

    Notion API rate limits apply; callers who need lower cost can lower
    ``max_blocks`` / ``max_depth`` or set ``include_content=False`` on the
    provider.
    """
    if _seen is None:
        _seen = set()
    if block_id in _seen:
        return []
    _seen.add(block_id)
    if _depth > max_depth or max_blocks <= 0:
        return []

    collected: list[dict[str, Any]] = []
    cursor: str | None = None
    while len(collected) < max_blocks:
        kwargs: dict[str, Any] = {
            "block_id": block_id,
            "page_size": _NOTION_PAGE_SIZE,
        }
        if cursor is not None:
            kwargs["start_cursor"] = cursor
        response = client.blocks.children.list(**kwargs)
        for block in response.get("results", []):
            if len(collected) >= max_blocks:
                break
            collected.append(block)
            if block.get("has_children") and _depth + 1 <= max_depth:
                child_id = block.get("id")
                remaining = max_blocks - len(collected)
                if child_id and remaining > 0:
                    children = _fetch_all_blocks(
                        client,
                        child_id,
                        max_depth=max_depth,
                        max_blocks=remaining,
                        _depth=_depth + 1,
                        _seen=_seen,
                    )
                    collected.extend(children)
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
        if not cursor:
            break

    return collected


# Register unconditionally so ``create_provider("notion")`` reaches the
# actionable ``ProviderError`` in ``NotionProvider.__init__`` when the
# optional ``notion-client`` extra is not installed, instead of falling
# through to the generic "Unknown provider" error in the registry.
register_provider("notion", NotionProvider)
