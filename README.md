# Azure Functions Knowledge

> ⚠️ **Experimental** — pattern exploration. APIs and behavior may change. Not recommended as a production dependency yet.

> Part of the **Azure Functions Python DX Toolkit** — dogfood-tested by [azure-functions-cookbook-python](https://github.com/yeongseon/azure-functions-cookbook-python).

[![Test and Coverage](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-knowledge-python/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-knowledge-python)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-yeongseon.dev-blue)](https://yeongseon.dev/azure-functions-python/knowledge/)
[![PyPI version](https://badge.fury.io/py/azure-functions-knowledge.svg)](https://badge.fury.io/py/azure-functions-knowledge)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Read this in: [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

Knowledge retrieval (RAG) decorators for Azure Functions Python v2.

## Why this exists

Retrieval-augmented generation on Azure Functions usually means hand-wiring a provider SDK, credential handling, and result marshalling into every handler. `azure-functions-knowledge` collapses that into a single declarative decorator, so your function just receives the documents it asked for — matching the FastAPI-like developer experience the rest of the toolkit aims for.

## What it does

- **Decorator-based API** — Seamless integration with the Azure Functions Python v2 programming model.
- **Provider abstraction** — Pluggable knowledge providers via a protocol-based interface.
- **Notion support** — Built-in Notion provider for searching and retrieving pages.
- **Async support** — Automatic async offloading for non-blocking execution.
- **Environment variable resolution** — `%VAR%` placeholder substitution for secure credential handling.

## What this package does NOT do

- **Not a vector database** — it does not store, index, or embed your documents; bring your own store (Notion, or a custom provider).
- **Not an embedding or LLM service** — it retrieves documents; generating answers from them is your handler's job.
- **Not a native Azure Functions binding** — the `@kb.*` decorators are Python function wrappers, not host-registered bindings.

## Installation

```bash
pip install azure-functions-knowledge[notion]
```

## Quick Start

```python
import azure.functions as func
from azure_functions_knowledge import Document, KnowledgeBindings

app = func.FunctionApp()
# KnowledgeBindings is the decorator factory — create one per app and reuse it
# to attach @kb.input / @kb.inject_client to your handlers.
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

Full documentation: [https://yeongseon.dev/azure-functions-python/knowledge/](https://yeongseon.dev/azure-functions-python/knowledge/)

## Development

```bash
git clone https://github.com/yeongseon/azure-functions-knowledge-python.git
cd azure-functions-knowledge-python
make install
make check-all
```

## For AI Coding Assistants

This repository includes `llms.txt` and `llms-full.txt` in the root directory.
These files provide comprehensive package and API information optimized for LLM context windows.

- **`llms.txt`** — Quick reference with core API, installation, and quick-start example
- **`llms-full.txt`** — Complete reference with full signatures, patterns, design principles, and ecosystem context

Use these files to get better context when working with this package in AI-assisted coding environments.

## Ecosystem

Part of the **Azure Functions Python DX Toolkit**:

| Package | Role |
|---------|------|
| [azure-functions-openapi-python](https://github.com/yeongseon/azure-functions-openapi-python) | OpenAPI spec generation and Swagger UI |
| [azure-functions-validation-python](https://github.com/yeongseon/azure-functions-validation-python) | Request/response validation and serialization |
| [azure-functions-db-python](https://github.com/yeongseon/azure-functions-db-python) | SQLAlchemy-powered DB integration helpers (poll-based pseudo trigger, input/output/client injection) |
| [azure-functions-langgraph-python](https://github.com/yeongseon/azure-functions-langgraph-python) | LangGraph deployment adapter for Azure Functions |
| [azure-functions-scaffold-python](https://github.com/yeongseon/azure-functions-scaffold-python) | Project scaffolding CLI |
| [azure-functions-logging-python](https://github.com/yeongseon/azure-functions-logging-python) | Structured logging and observability |
| [azure-functions-doctor-python](https://github.com/yeongseon/azure-functions-doctor-python) | Pre-deploy diagnostic CLI |
| [azure-functions-durable-graph-python](https://github.com/yeongseon/azure-functions-durable-graph-python) | Manifest-first graph runtime with Durable Functions *(experimental)* |
| **azure-functions-knowledge-python** | Knowledge retrieval (RAG) decorators |
| [azure-functions-cookbook-python](https://github.com/yeongseon/azure-functions-cookbook-python) | Dogfood examples — runnable recipes that exercise the full toolkit |

## Disclaimer

This project is an independent community project and is not affiliated with,
endorsed by, or maintained by Microsoft.

Azure and Azure Functions are trademarks of Microsoft Corporation.

## License

MIT License. See [LICENSE](LICENSE) for details.
