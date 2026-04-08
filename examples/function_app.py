from __future__ import annotations

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
def search_knowledge(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    import json

    results = [{"title": d.title, "url": d.url, "id": d.document_id} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")


@app.route(route="page/{page_id}", methods=["GET"])
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def get_page(req: func.HttpRequest, client: object) -> func.HttpResponse:
    import json

    page_id = req.route_params.get("page_id", "")
    doc = client.get_document(page_id)  # type: ignore[union-attr]
    return func.HttpResponse(
        json.dumps({"title": doc.title, "content": doc.content, "url": doc.url}),
        mimetype="application/json",
    )
