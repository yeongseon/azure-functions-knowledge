"""Custom provider + registration example.

Implements the ``KnowledgeProvider`` protocol with an in-memory store and
registers it under the name ``"static"`` so it can be used by the decorators.
"""

from __future__ import annotations

import azure.functions as func

from azure_functions_knowledge import Document, KnowledgeBindings, register_provider


class StaticProvider:
    """A trivial in-memory knowledge provider (no external dependencies)."""

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
        # 'connection' is unused here but required by the provider contract.
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


@app.route(route="static-search", methods=["GET"])
@kb.input(
    "docs",
    provider="static",
    query=lambda req: req.params.get("q", ""),
    connection="unused",
)
def static_search(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    import json

    results = [{"title": d.title, "url": d.url} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")
