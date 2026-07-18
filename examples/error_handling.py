"""Error handling for knowledge providers.

Every error derives from ``KnowledgeError``; catch narrowly to map failures to
appropriate HTTP responses.
"""

from __future__ import annotations

from typing import Any

import azure.functions as func

from azure_functions_knowledge import (
    AuthError,
    ConfigurationError,
    KnowledgeBindings,
    ProviderError,
)

app = func.FunctionApp()
kb = KnowledgeBindings()


@app.route(route="safe-search", methods=["GET"])
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def safe_search(req: func.HttpRequest, client: Any) -> func.HttpResponse:
    import json

    query = req.params.get("q", "")
    try:
        docs = client.search(query, top=5)
    except AuthError:
        return func.HttpResponse("Invalid credentials", status_code=401)
    except ConfigurationError:
        return func.HttpResponse("Misconfigured connection", status_code=500)
    except ProviderError:
        return func.HttpResponse("Upstream provider error", status_code=502)

    results = [{"title": d.title, "url": d.url} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")
