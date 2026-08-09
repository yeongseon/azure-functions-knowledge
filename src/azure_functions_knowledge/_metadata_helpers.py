"""Canonical worker-compatibility metadata helpers.

This module houses the primitive shared across the Azure Functions Python DX
Toolkit for copying identity attributes from a user handler onto a decorator
wrapper **without** tripping the Azure Functions worker's function-indexing
heuristics.

The primitive is intentionally kept as a small, dependency-free unit so the
**same shape** can be mirrored verbatim across sibling packages
(``azure-functions-validation``, ``azure-functions-logging``, ...). These
packages are independent PyPI distributions with no shared base dependency, so
"shared" here means a canonical, synced definition rather than a common import.

Ref: https://github.com/yeongseon/azure-functions-knowledge-python/issues/44
"""

from __future__ import annotations

from typing import Any, Callable

# Identity attributes copied from the wrapped function onto the wrapper.
#
# ``functools.wraps`` / ``functools.update_wrapper`` are deliberately NOT used:
#
# * they set ``__wrapped__ = func`` — the Azure Functions library resolves the
#   "user function" by recursively following ``__wrapped__``
#   (``function_app._get_user_function``), so it binds the original
#   (un-wrapped) handler instead of the wrapper, defeating the decorator and
#   re-exposing the injected parameter to the worker's argument indexing;
# * ``typing.get_type_hints`` also follows ``__wrapped__`` on some CPython
#   builds, which can leak the original annotations back to the worker.
SAFE_IDENTITY_ATTRS: tuple[str, ...] = (
    "__name__",
    "__qualname__",
    "__doc__",
    "__module__",
)


def copy_identity_attrs(
    wrapper: Callable[..., Any],
    func: Callable[..., Any],
    attrs: tuple[str, ...] = SAFE_IDENTITY_ATTRS,
) -> None:
    """Copy safe identity attributes from ``func`` onto ``wrapper`` in place.

    Copies only the attributes in ``attrs`` (identity metadata) and neither
    sets ``__wrapped__`` nor copies ``__dict__``. Signature handling is left to
    the caller because it is package-specific (knowledge exposes the handler
    signature with the injected parameter removed).
    """
    for attr in attrs:
        try:
            object.__setattr__(wrapper, attr, getattr(func, attr))
        except (AttributeError, TypeError):  # pragma: no cover
            pass
