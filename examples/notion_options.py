"""Notion provider options demo.

Shows forwarding provider-specific options (``include_content``,
``content_max_chars``, ``max_depth``, ``max_blocks``) through the decorator.
"""

from __future__ import annotations

import azure.functions as func

from azure_functions_knowledge import Document, KnowledgeBindings

app = func.FunctionApp()
kb = KnowledgeBindings()


# Metadata-only search: skip content extraction for speed / fewer API calls.
@app.route(route="titles", methods=["GET"])
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    connection="%NOTION_TOKEN%",
    include_content=False,
)
def titles_only(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    import json

    return func.HttpResponse(json.dumps([d.title for d in docs]), mimetype="application/json")


# Bounded content extraction: truncate and cap traversal to control cost.
@app.route(route="excerpts", methods=["GET"])
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    connection="%NOTION_TOKEN%",
    include_content=True,
    content_max_chars=2000,
    max_depth=4,
    max_blocks=500,
)
def excerpts(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    import json

    results = [{"title": d.title, "excerpt": d.content} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")
