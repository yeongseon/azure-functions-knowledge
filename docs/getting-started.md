# Getting Started

## Setup

1. Install the package with the Notion provider:

```bash
pip install azure-functions-knowledge[notion]
```

2. Set up your Notion API token as an environment variable:

```bash
export NOTION_TOKEN="your-notion-integration-token"
```

## Data Injection with `input`

The `input` decorator searches a knowledge provider and injects results directly into your handler:

```python
import azure.functions as func
from azure_functions_knowledge import Document, KnowledgeBindings

app = func.FunctionApp()
kb = KnowledgeBindings()

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

### Static vs Dynamic Queries

**Static query** — Same search every invocation:

```python
@kb.input("docs", provider="notion", query="project roadmap", connection="%NOTION_TOKEN%")
def handler(timer, docs: list[Document]) -> None:
    ...
```

**Dynamic query** — Derived from handler parameters:

```python
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    connection="%NOTION_TOKEN%",
)
def handler(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    ...
```

## Client Injection with `inject_client`

For imperative control, use `inject_client` to receive a provider instance:

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

## Decorator Composition Rules

- Azure decorators go outermost, knowledge decorators closest to the function
- `input` and `inject_client` are **mutually exclusive** on the same handler
- No decorator can be applied twice to the same handler

## Connection Strings

Connection parameters support `%VAR%` environment variable substitution:

```python
connection="%NOTION_TOKEN%"          # Single env var
connection="Bearer %API_KEY%"        # Partial substitution
connection={"token": "%MY_TOKEN%"}   # Mapping with substitution
```

## Async Support

Both `input` and `inject_client` automatically detect async handlers and offload blocking I/O via `asyncio.to_thread()`:

```python
@app.route(route="search", methods=["GET"])
@kb.input("docs", provider="notion", query="roadmap", connection="%NOTION_TOKEN%")
async def search(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    ...
```
