"""Async handler with search injection.

Async handlers are detected automatically; the blocking provider search runs in
a worker thread via ``asyncio.to_thread()`` so the event loop stays responsive.
"""

from __future__ import annotations

from typing import Any

import azure.functions as func

from azure_functions_knowledge import Document, KnowledgeBindings

app = func.FunctionApp()
kb = KnowledgeBindings()


@app.route(route="async-search", methods=["GET"])
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    top=5,
    connection="%NOTION_TOKEN%",
)
async def async_search(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    import json

    results = [{"title": d.title, "url": d.url} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")


@app.route(route="async-page/{page_id}", methods=["GET"])
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
async def async_page(req: func.HttpRequest, client: Any) -> func.HttpResponse:
    import json

    page_id = req.route_params.get("page_id", "")
    # In an async handler the injected client is an async proxy — await it.
    doc = await client.get_document(page_id)
    return func.HttpResponse(
        json.dumps({"title": doc.title, "content": doc.content}),
        mimetype="application/json",
    )
