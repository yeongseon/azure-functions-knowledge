"""Typed cross-package metadata contract for the ``knowledge`` namespace.

This module defines the shape of the ``_azure_functions_metadata`` convention
attribute that the knowledge decorators attach to Azure Functions handlers.
Sibling toolkit packages (``azure-functions-openapi``, validation, logging)
read this attribute to discover knowledge-backed handlers without importing
this package.

The contract is behavior-preserving: the payload shape (``version``, ``mode``,
``provider``, ``arg_name`` and, for ``input``, ``query``/``top``) is unchanged
from the historical ad-hoc dict. Formalizing it as a ``TypedDict`` with an
explicit version constant lets consumers degrade gracefully as the payload
evolves, matching the ``db`` namespace contract.
"""

from __future__ import annotations

from typing import Any, TypedDict, cast

# Convention attribute name shared across every Azure Functions toolkit package.
METADATA_ATTR = "_azure_functions_metadata"

# Namespace owned by this package inside the convention attribute.
NAMESPACE = "knowledge"

# Version of the ``knowledge`` namespace payload. Consumers should read this and
# degrade gracefully when it exceeds the version they support.
KNOWLEDGE_METADATA_VERSION = 1


class _KnowledgeMetadataRequired(TypedDict):
    """Keys present on every knowledge metadata payload."""

    version: int
    mode: str
    provider: str
    arg_name: str


class KnowledgeMetadata(_KnowledgeMetadataRequired, total=False):
    """The ``knowledge`` namespace payload stored under ``METADATA_ATTR``.

    ``query`` (``"static"``/``"dynamic"``) and ``top`` are only present for the
    ``input`` decorator; ``inject_client`` omits them.
    """

    query: str
    top: int


def set_knowledge_metadata(
    wrapper: Any,
    fn: Any,
    payload: KnowledgeMetadata,
) -> None:
    """Publish a ``knowledge`` payload on ``wrapper`` under the convention attr.

    Reads any existing convention metadata from ``fn`` (populated by inner
    decorators) and writes the combined mapping onto ``wrapper`` so sibling
    tools can discover knowledge-backed handlers. Behavior-preserving
    replacement for the historical ``combined["knowledge"] = meta`` assignment.
    """
    combined: dict[str, Any] = dict(getattr(fn, METADATA_ATTR, None) or {})
    combined[NAMESPACE] = dict(payload)
    setattr(wrapper, METADATA_ATTR, combined)


def read_knowledge_metadata(func: Any) -> KnowledgeMetadata | None:
    """Return the typed ``knowledge`` metadata attached to ``func``, or ``None``."""
    meta = getattr(func, METADATA_ATTR, None)
    if not isinstance(meta, dict):
        return None
    entry = meta.get(NAMESPACE)
    if not isinstance(entry, dict):
        return None
    return cast("KnowledgeMetadata", entry)
