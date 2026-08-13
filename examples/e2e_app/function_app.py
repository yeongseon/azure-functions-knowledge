"""Real-Azure certification app for azure-functions-knowledge.

This app exists **only** for the release gate. The ``e2e-azure`` GitHub workflow
deploys it to a temporary Azure Functions Consumption (Y1) host, runs
``tests/e2e`` against it, records an ``azure-cert`` artifact, then deletes the
resource group.

It is deliberately secret-free and deterministic: the ``StaticProvider`` below
serves two fixed documents from memory, so every e2e assertion is stable and no
external service (Notion, a vector store, etc.) is required.

Two properties are proven by deploying this app to a real host:

1. **Decorator injection + import-time registration.** ``register_provider`` runs
   at import time, so ``/api/health`` can list ``"static"`` before Azure has even
   indexed the app's routes — proving the module imported cleanly on the worker.
2. **``%VAR%`` connection resolution.** The routes are wired with
   ``connection="%STATIC_CONNECTION%"`` and the workflow sets the app setting
   ``STATIC_CONNECTION=static-e2e``. ``StaticProvider.__init__`` raises unless it
   receives the resolved literal ``"static-e2e"``, so a broken substitution (or a
   missing app setting) turns ``/api/search`` and ``/api/doc/{id}`` into 500s that
   the e2e suite catches.
"""

from __future__ import annotations

import json

import azure.functions as func

from azure_functions_knowledge import (
    ConfigurationError,
    Document,
    KnowledgeBindings,
    get_registered_providers,
    register_provider,
)

# The resolved connection value the workflow injects via the STATIC_CONNECTION
# app setting. StaticProvider refuses to start unless '%STATIC_CONNECTION%'
# resolved to exactly this literal, which is how the live e2e proves that
# environment-variable substitution actually ran on the worker.
_EXPECTED_CONNECTION = "static-e2e"


class StaticProvider:
    """A trivial, deterministic in-memory knowledge provider (no external deps).

    Conforms to the ``KnowledgeProvider`` protocol. Unlike the user-facing
    example in ``examples/custom_provider.py``, this one *validates* the resolved
    connection so the certification can assert that ``%VAR%`` substitution ran.
    """

    _DOCS = [
        Document(
            document_id="1",
            content="Azure Functions supports Python v2 programming model.",
            title="Python v2",
            url="https://example.test/1",
            source="static",
        ),
        Document(
            document_id="2",
            content="Knowledge bindings inject search results into handlers.",
            title="Knowledge bindings",
            url="https://example.test/2",
            source="static",
        ),
    ]

    def __init__(self, *, connection: object, **kwargs: object) -> None:
        if connection != _EXPECTED_CONNECTION:
            msg = (
                "StaticProvider expected the resolved connection "
                f"{_EXPECTED_CONNECTION!r} (from %STATIC_CONNECTION%), got "
                f"{connection!r}. The STATIC_CONNECTION app setting is missing "
                "or %VAR% substitution did not run."
            )
            raise ConfigurationError(msg)
        self._docs = list(self._DOCS)

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        matches = [d for d in self._docs if query.lower() in d.content.lower()]
        return matches[:top]

    def get_document(self, document_id: str) -> Document:
        return next(d for d in self._docs if d.document_id == document_id)

    def close(self) -> None:
        pass


register_provider("static", StaticProvider)

app = func.FunctionApp()
kb = KnowledgeBindings()


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness + registration probe.

    Returns the registered provider names so the e2e suite can assert that
    ``register_provider("static", ...)`` ran at import time. This route creates
    no provider, so it stays green even if STATIC_CONNECTION is misconfigured —
    the connection-resolution proof lives in /api/search and /api/doc.
    """
    body = {"ok": True, "providers": get_registered_providers()}
    return func.HttpResponse(json.dumps(body), mimetype="application/json")


@app.route(route="search", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@kb.input(
    "docs",
    provider="static",
    query=lambda req: req.params.get("q", ""),
    top=5,
    connection="%STATIC_CONNECTION%",
)
def search(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    results = [{"id": d.document_id, "title": d.title, "url": d.url} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")


@app.route(route="doc/{id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@kb.inject_client("client", provider="static", connection="%STATIC_CONNECTION%")
def doc(req: func.HttpRequest, client: StaticProvider) -> func.HttpResponse:
    document_id = req.route_params.get("id", "")
    try:
        found = client.get_document(document_id)
    except StopIteration:
        return func.HttpResponse(
            json.dumps({"error": f"document {document_id!r} not found"}),
            status_code=404,
            mimetype="application/json",
        )
    body = {
        "id": found.document_id,
        "title": found.title,
        "content": found.content,
        "url": found.url,
    }
    return func.HttpResponse(json.dumps(body), mimetype="application/json")
