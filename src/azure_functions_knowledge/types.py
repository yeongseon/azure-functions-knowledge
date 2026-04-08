from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(kw_only=True)
class Document:
    """A retrieved knowledge document."""

    document_id: str
    content: str
    title: str
    url: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
