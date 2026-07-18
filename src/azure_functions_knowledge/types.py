from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(kw_only=True)
class Document:
    """A retrieved knowledge document.

    ``score`` is an optional-future field reserved for relevance ranking.
    It defaults to ``None``; providers MAY populate it (the built-in Notion
    provider currently does not).
    """

    document_id: str
    content: str
    title: str
    url: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
