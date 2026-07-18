# Notion Provider

`NotionProvider` is the built-in [`KnowledgeProvider`](../api.md#knowledgeprovider)
backed by the [Notion API](https://developers.notion.com/). It is registered
under the name `"notion"`.

## Installation

The provider depends on the optional `notion-client` package, installed via the
`notion` extra:

```bash
pip install azure-functions-knowledge-python[notion]
```

The provider is **registered unconditionally**, even when `notion-client` is not
installed. Attempting to create it without the extra raises a `ProviderError`
with an actionable install hint rather than a generic "unknown provider" error.

## Authentication

Pass a Notion integration token via `connection`. See
[Configuration](../configuration.md) for the accepted forms:

```python
connection="%NOTION_TOKEN%"           # string, resolved from env
connection={"token": "%NOTION_TOKEN%"} # mapping ('api_key' also accepted)
```

## Options

All options are keyword arguments forwarded through the decorator:

| Option | Default | Description |
|--------|---------|-------------|
| `include_content` | `True` | When `True`, `search` fetches and renders page content into `Document.content`. Set `False` to return metadata only (faster, fewer API calls). |
| `content_max_chars` | `None` | Truncates rendered content to this many characters. `None` means no limit. |
| `max_depth` | `8` | Maximum block-tree recursion depth when extracting content. |
| `max_blocks` | `1000` | Maximum number of blocks fetched per page. |

Example:

```python
@app.route(route="search", methods=["GET"])
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    connection="%NOTION_TOKEN%",
    include_content=True,
    content_max_chars=4000,
    max_depth=4,
    max_blocks=500,
)
def search(req, docs): ...
```

## Behavior

- **`search`** — queries Notion filtered to `page` objects, honoring `top` as
  the page size. Each result page is converted to a `Document`; when
  `include_content=True`, page blocks are fetched and rendered to text.
- **`get_document`** — retrieves a single page by id and always renders its full
  block content. `metadata` includes the raw `blocks` and `properties`.
- **Content extraction** — child blocks are walked depth-first with pagination
  and recursion into children, bounded by `max_depth` / `max_blocks` and
  protected against cycles. Text is emitted in natural reading order.

## Returned `Document`

| Field | Notion source |
|-------|---------------|
| `document_id` | Page id |
| `title` | First `title`-typed property |
| `url` | Page `url` |
| `content` | Rendered block text (empty when `include_content=False`) |
| `source` | `"notion"` |
| `metadata` | `{"properties": ...}` for search; also `{"blocks": ...}` for `get_document` |

## Errors

| Situation | Exception |
|-----------|-----------|
| `notion-client` not installed | `ProviderError` |
| Connection mapping missing `token`/`api_key` | `AuthError` |
| Client initialization failure | `AuthError` |
| Notion API error during search/retrieve/block fetch | `ProviderError` |
| Unset `%VAR%` in the connection string | `ConfigurationError` |

## Rate limits

The Notion API is rate-limited. To reduce request volume, lower `max_blocks` /
`max_depth`, or set `include_content=False` when you only need titles and URLs.
