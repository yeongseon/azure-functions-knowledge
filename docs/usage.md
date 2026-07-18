# Usage

Practical recipes for the two decorators, async handlers, error handling, and
custom providers. Runnable versions of these live in the
[`examples/`](https://github.com/yeongseon/azure-functions-knowledge-python/tree/main/examples)
directory.

## Static vs dynamic queries

A **static** query runs the same search every invocation:

```python
@kb.input("docs", provider="notion", query="project roadmap", connection="%NOTION_TOKEN%")
def handler(timer, docs: list[Document]) -> None:
    for doc in docs:
        print(doc.title, doc.url)
```

A **dynamic** query derives the search string from handler parameters. The
callable receives handler parameters by name and must not use `*args`/`**kwargs`:

```python
@app.route(route="search", methods=["GET"])
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    top=5,
    connection="%NOTION_TOKEN%",
)
def search(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    import json
    results = [{"title": d.title, "url": d.url} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")
```

Referencing a parameter the handler does not have raises `ConfigurationError`
at decoration time.

## Async handlers

Both decorators detect `async def` handlers and offload blocking provider I/O to
a worker thread, so the event loop stays responsive:

```python
@app.route(route="search", methods=["GET"])
@kb.input("docs", provider="notion", query="roadmap", connection="%NOTION_TOKEN%")
async def search(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    ...
```

## Client injection

Use `inject_client` when you need imperative control — multiple calls,
`get_document`, or conditional logic:

```python
@app.route(route="page/{page_id}", methods=["GET"])
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def get_page(req: func.HttpRequest, client) -> func.HttpResponse:
    import json
    page_id = req.route_params.get("page_id", "")
    doc = client.get_document(page_id)
    return func.HttpResponse(
        json.dumps({"title": doc.title, "content": doc.content}),
        mimetype="application/json",
    )
```

In an **async** handler the injected client is an async proxy — `await` its
methods:

```python
@app.route(route="page/{page_id}", methods=["GET"])
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
async def get_page(req: func.HttpRequest, client) -> func.HttpResponse:
    doc = await client.get_document(req.route_params["page_id"])
    results = await client.search("related", top=10)
    ...
```

## Error handling

All errors derive from `KnowledgeError`, so you can catch broadly or narrowly:

```python
from azure_functions_knowledge import (
    AuthError,
    ConfigurationError,
    ProviderError,
)

@app.route(route="search", methods=["GET"])
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def search(req: func.HttpRequest, client) -> func.HttpResponse:
    try:
        docs = client.search(req.params.get("q", ""), top=5)
    except AuthError:
        return func.HttpResponse("Invalid credentials", status_code=401)
    except ConfigurationError:
        return func.HttpResponse("Misconfigured connection", status_code=500)
    except ProviderError:
        return func.HttpResponse("Upstream provider error", status_code=502)
    ...
```

See the [API reference](api.md#exceptions) for which error each situation
raises.

## Custom provider registration

Implement the [`KnowledgeProvider`](api.md#knowledgeprovider) protocol and
register it under a name. Constructors must accept a keyword-only `connection`
argument and may accept extra keyword arguments:

```python
from azure_functions_knowledge import Document, register_provider

class StaticProvider:
    def __init__(self, *, connection, **kwargs):
        self._docs = kwargs.get("docs", [])

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        matches = [d for d in self._docs if query.lower() in d.content.lower()]
        return matches[:top]

    def get_document(self, document_id: str) -> Document:
        return next(d for d in self._docs if d.document_id == document_id)

    def close(self) -> None:
        pass

register_provider("static", StaticProvider)

# Now usable by name:
@kb.input("docs", provider="static", query="hello", connection="unused")
def handler(timer, docs: list[Document]) -> None:
    ...
```

Any keyword arguments you pass to `input` / `inject_client` beyond the reserved
ones are forwarded to your provider constructor.
