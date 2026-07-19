# API Reference

The complete public surface of `azure-functions-knowledge-python`. Every symbol
listed here is exported from the top-level `azure_functions_knowledge` package
(and enforced by `tests/test_public_api.py`), except where noted as internal.

```python
from azure_functions_knowledge import (
    Document,
    KnowledgeBindings,
    KnowledgeProvider,
    create_provider,
    get_registered_providers,
    register_provider,
    AuthError,
    ConfigurationError,
    KnowledgeError,
    ProviderError,
    __version__,
)
```

## `KnowledgeBindings`

Azure Functions-style decorator API for knowledge retrieval. Instantiate once
per app and reuse for every handler:

```python
kb = KnowledgeBindings()
```

### `KnowledgeBindings.input`

```python
def input(
    self,
    arg_name: str,
    *,
    provider: str,
    query: str | Callable[..., str],
    top: int = 5,
    connection: str | Mapping[str, str],
    **kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]
```

Searches a provider and injects the resulting `list[Document]` into the handler
parameter named `arg_name`.

| Parameter | Description |
|-----------|-------------|
| `arg_name` | Handler parameter that receives `list[Document]`. Must exist in the handler signature and must not be a [reserved name](#reserved-parameter-names). |
| `provider` | Registered provider name (e.g. `"notion"`). Resolved via `create_provider`. |
| `query` | Either a static `str` or a callable. A callable receives handler parameters by name (e.g. `lambda req: req.params.get("q", "")`) and must not use `*args`/`**kwargs`. Every parameter the callable references must exist on the handler. |
| `top` | Maximum results to request. Must be `>= 1` (otherwise `ConfigurationError`). |
| `connection` | Connection string or mapping. See [Configuration](configuration.md). |
| `**kwargs` | Forwarded to the provider constructor (e.g. `include_content=False`). |

Behavior:

- The provider is created **per invocation** and closed in a `finally` block.
- Async handlers are detected automatically; the blocking search runs in a
  worker thread via `asyncio.to_thread()`.
- The injected parameter is stripped from the host-facing `__signature__` so the
  Azure Functions host does not attempt to bind it.

### `KnowledgeBindings.inject_client`

```python
def inject_client(
    self,
    arg_name: str,
    *,
    provider: str,
    connection: str | Mapping[str, str],
    **kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]
```

Injects a live provider instance into `arg_name` for imperative control. Use it
when you need to call `search()` / `get_document()` yourself, or issue multiple
calls per invocation.

- For **sync** handlers the raw provider is injected.
- For **async** handlers an `_AsyncProviderProxy` is injected. It exposes
  awaitable `search(...)` / `get_document(...)` methods that offload to a worker
  thread, plus a synchronous `close()`.
- The provider is always closed in a `finally` block after the handler returns.

### Composition rules

- Azure decorators go outermost; knowledge decorators sit closest to the
  function.
- `input` and `inject_client` are **mutually exclusive** on one handler.
- No knowledge decorator may be applied twice to the same handler.

Violating any rule raises `ConfigurationError` at decoration time.

### Reserved parameter names

`arg_name` may not be one of the Azure Functions reserved names:
`context`, `input`, `msg`, `output`, `req`, `timer`. Using one raises
`ConfigurationError`.

## `Document`

```python
@dataclass(kw_only=True)
class Document:
    document_id: str
    content: str
    title: str
    url: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
```

A retrieved knowledge document. `kw_only=True`, so all fields must be passed by
keyword. `metadata` carries provider-specific data (for the Notion provider,
raw `properties` and, for `get_document`, fetched `blocks`). `score` is reserved
for relevance ranking and is currently unset by the built-in provider.

## Provider registry

### `KnowledgeProvider`

```python
@runtime_checkable
class KnowledgeProvider(Protocol):
    def __init__(
        self, *, connection: str | Mapping[str, str], **kwargs: Any
    ) -> None: ...
    def search(self, query: str, *, top: int = 5) -> list[Document]: ...
    def get_document(self, document_id: str) -> Document: ...
    def close(self) -> None: ...
```

The structural protocol every provider must satisfy. Because it is
`runtime_checkable`, `isinstance(obj, KnowledgeProvider)` performs a method-name
check. Note that `isinstance` checks skip dunder methods, so the `__init__`
contract is enforced only by static typing: custom providers must accept a
keyword-only `connection` argument (a string or mapping) plus arbitrary
provider-specific `**kwargs`, matching how `create_provider` instantiates them.
See [Usage → Custom providers](usage.md#custom-provider-registration).

### `register_provider`

```python
def register_provider(name: str, provider_cls: type[KnowledgeProvider]) -> None
```

Registers `provider_cls` under `name` in the process-wide registry. Re-using an
existing name overwrites the previous entry.

### `create_provider`

```python
def create_provider(
    name: str,
    *,
    connection: str | Mapping[str, str],
    **kwargs: Any,
) -> KnowledgeProvider
```

Instantiates a registered provider. Raises `ConfigurationError` with the message
`Unknown provider '<name>'. Available: [...]` when `name` is not registered.
`connection` and `**kwargs` are forwarded to the provider constructor.

### `get_registered_providers`

```python
def get_registered_providers() -> list[str]
```

Returns the sorted list of registered provider names. `"notion"` is always
present because the Notion provider registers itself unconditionally on import.

## Exceptions

All exceptions derive from `KnowledgeError`, so a single `except KnowledgeError`
catches every failure this package raises.

| Exception | Raised when |
|-----------|-------------|
| `KnowledgeError` | Base class for all errors below. |
| `ConfigurationError` | Invalid decorator usage (bad `arg_name`, `top < 1`, illegal composition), unknown provider, or an unset `%VAR%` in a connection string. |
| `ProviderError` | A provider failed at runtime — e.g. `notion-client` is not installed, or the Notion API returned an error. |
| `AuthError` | Authentication/credential problems — e.g. a connection mapping missing `token`/`api_key`, or Notion client initialization failure. |

## `resolve_connection` (internal helper)

```python
from azure_functions_knowledge.auth import resolve_connection

def resolve_connection(value: str) -> str
```

!!! note
    `resolve_connection` is **not** exported from the top-level package — import
    it from `azure_functions_knowledge.auth` if you need it directly. It is
    documented here because providers rely on it and custom providers may reuse
    it.

Substitutes `%VAR%` placeholders in `value` with the matching environment
variables. Raises `ConfigurationError` when a referenced variable is unset. See
[Configuration](configuration.md).

## `__version__`

The installed package version string, kept in sync with the distribution
metadata (`importlib.metadata.version("azure-functions-knowledge-python")`).
