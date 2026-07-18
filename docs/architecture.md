# Architecture

This page explains what happens between a decorated Azure Functions handler and
a knowledge provider. The request flow below is shown as a Markdown sketch
(see [Request flow](#request-flow)).

## Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `KnowledgeBindings` | `decorator.py` | Public decorator API (`input`, `inject_client`). Validates arg names, composition, and query callables; builds the host-facing signature. |
| Provider registry | `providers/base.py` | `register_provider` / `create_provider` / `get_registered_providers` over a process-wide name → class map. |
| `KnowledgeProvider` | `providers/base.py` | Structural `Protocol` (`search`, `get_document`, `close`). |
| `NotionProvider` | `providers/notion.py` | Built-in provider backed by the Notion API. |
| `resolve_connection` | `auth.py` | `%VAR%` environment-variable substitution for connection strings. |
| `Document` | `types.py` | Dataclass returned to handlers (carries a mutable `metadata` dict). |
| Errors | `errors.py` | `KnowledgeError` hierarchy. |

## Request flow

At decoration time the binding validates configuration and replaces the handler
with a wrapper. For `input`, the wrapper resolves the query, creates a provider,
runs the search, injects the results, and always closes the provider. For
`inject_client`, the wrapper creates and injects the provider client (no query
resolution or search) and always closes it when the handler returns:

```
Azure Functions host
        │  invokes wrapper (injected arg hidden from host signature)
        ▼
@kb.input / @kb.inject_client wrapper
        │  resolve query (static or callable)
        ▼
create_provider(name, connection, **kwargs)      ── providers/base.py
        │  registry lookup
        │      └─ unknown name ─▶ ConfigurationError
        ▼
Provider.__init__(connection=...)                 ── e.g. NotionProvider
        │  resolve_connection("%VAR%")            ── auth.py
        │      └─ unset var ─▶ ConfigurationError
        │  missing extra / bad token ─▶ ProviderError / AuthError
        ▼
provider.search(query, top) / get_document(id)
        │  (async handler: run in worker thread via asyncio.to_thread)
        ▼
list[Document] / Document  ─▶ injected into handler ─▶ provider.close()
```

The `input` decorator injects the **results** (`list[Document]`);
`inject_client` injects the **provider** so the handler drives the calls itself.

## Async offloading

Providers are synchronous. When a handler is `async`, the binding keeps the
event loop responsive by offloading blocking I/O to a worker thread:

- `input` wraps the whole search (`create_provider` + `search` + `close`) in
  `asyncio.to_thread(...)`.
- `inject_client` injects an `_AsyncProviderProxy` whose `search` /
  `get_document` methods each call `asyncio.to_thread(...)` on the underlying
  provider, so the handler can `await` them.

## Provider lifecycle

A provider is constructed **per invocation** and closed in a `finally` block —
there is no connection pooling or caching across invocations. Keep constructors
cheap, or cache expensive resources at module scope inside your provider
implementation.

## Notion provider behavior

`NotionProvider` (`providers/notion.py`) implements the protocol against the
Notion API:

- **Registration** — registered unconditionally on import, so
  `create_provider("notion")` reaches an actionable `ProviderError` (instructing
  you to install the `[notion]` extra) rather than a generic "unknown provider"
  error when `notion-client` is missing.
- **Search** — calls Notion `search` filtered to `page` objects, then (unless
  `include_content=False`) fetches and renders page content into
  `Document.content`.
- **Content extraction** — `_fetch_all_blocks` walks child blocks depth-first,
  paginating (`page_size=100`) and recursing into children. It respects
  `max_depth` and `max_blocks` caps and guards against cycles with a `_seen`
  set, producing text in natural reading order.
- **Truncation** — `content_max_chars` truncates rendered content when set.

See [Providers → Notion](providers/notion.md) for the full option list.
