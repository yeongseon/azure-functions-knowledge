# azure-functions-knowledge

[![Test and Coverage](https://github.com/yeongseon/azure-functions-knowledge/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-knowledge/actions/workflows/ci-test.yml)
[![PyPI version](https://badge.fury.io/py/azure-functions-knowledge.svg)](https://badge.fury.io/py/azure-functions-knowledge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Knowledge retrieval (RAG) decorators for Azure Functions Python v2.

## Features

- **Decorator-based API** — Seamless integration with Azure Functions Python v2 programming model
- **Provider abstraction** — Pluggable knowledge providers via protocol-based interface
- **Notion support** — Built-in Notion provider for searching and retrieving pages
- **Async support** — Automatic async offloading for non-blocking execution
- **Environment variable resolution** — `%VAR%` placeholder substitution for secure credential handling

## Installation

```bash
pip install azure-functions-knowledge[notion]
```

## Quick Start

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

## Decorators

### `input` — Data Injection

Searches a knowledge provider and injects results into the handler:

```python
@kb.input("docs", provider="notion", query="roadmap", connection="%NOTION_TOKEN%")
def handler(timer, docs: list[Document]) -> None:
    for doc in docs:
        print(doc.title, doc.url)
```

Dynamic queries from handler parameters:

```python
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    connection="%NOTION_TOKEN%",
)
def handler(req, docs: list[Document]) -> func.HttpResponse:
    ...
```

### `inject_client` — Client Injection

Injects a provider instance for imperative control:

```python
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def handler(req, client) -> func.HttpResponse:
    doc = client.get_document(page_id)
    results = client.search("query", top=10)
    ...
```

## Composition Rules

- Azure decorators outermost, knowledge decorators closest to the function
- `input` and `inject_client` are mutually exclusive
- No decorator can be applied twice to the same handler

## Connection Strings

```python
connection="%NOTION_TOKEN%"          # Single env var
connection="Bearer %API_KEY%"        # Partial substitution
connection={"token": "%MY_TOKEN%"}   # Mapping with substitution
```

## Custom Providers

Implement the `KnowledgeProvider` protocol and register:

```python
from azure_functions_knowledge import Document, register_provider

class MyProvider:
    def __init__(self, *, connection, **kwargs):
        ...

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        ...

    def get_document(self, document_id: str) -> Document:
        ...

    def close(self) -> None:
        ...

register_provider("my-provider", MyProvider)
```

## Documentation

Full documentation: [https://yeongseon.github.io/azure-functions-knowledge/](https://yeongseon.github.io/azure-functions-knowledge/)

## Development

```bash
git clone https://github.com/yeongseon/azure-functions-knowledge.git
cd azure-functions-knowledge
make install
make check-all
```

## License

MIT License. See [LICENSE](LICENSE) for details.
