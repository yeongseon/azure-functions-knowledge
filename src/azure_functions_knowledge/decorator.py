from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import functools
import inspect
import logging
from typing import Any

from .errors import ConfigurationError
from .providers.base import create_provider
from .types import Document

logger = logging.getLogger(__name__)

_RESERVED_ARGS = frozenset({"timer", "req", "context", "msg", "input", "output"})
_KNOWLEDGE_DECORATOR_ATTR = "_knowledge_decorators"


def _get_decorators(fn: Callable[..., Any]) -> frozenset[str]:
    existing: object = getattr(fn, _KNOWLEDGE_DECORATOR_ATTR, frozenset())
    if not isinstance(existing, frozenset):
        return frozenset()
    return existing


def _mark_decorator(fn: Callable[..., Any], name: str) -> None:
    setattr(fn, _KNOWLEDGE_DECORATOR_ATTR, _get_decorators(fn) | {name})


def _check_composition(fn: Callable[..., Any], name: str) -> None:
    existing = _get_decorators(fn)

    if name in existing:
        msg = f"Decorator '{name}' cannot be applied twice to the same handler"
        raise ConfigurationError(msg)

    if name == "input" and "inject_client" in existing:
        msg = (
            "Cannot combine 'input' and 'inject_client' on the same handler — use one or the other"
        )
        raise ConfigurationError(msg)
    if name == "inject_client" and "input" in existing:
        msg = (
            "Cannot combine 'inject_client' and 'input' on the same handler — use one or the other"
        )
        raise ConfigurationError(msg)


def _validate_arg_name(arg_name: str, fn: Callable[..., Any], decorator_name: str) -> None:
    sig = inspect.signature(fn, follow_wrapped=False)
    if arg_name not in sig.parameters:
        msg = (
            f"{decorator_name} arg_name='{arg_name}' not found in "
            f"function '{fn.__name__}' parameters"
        )
        raise ConfigurationError(msg)

    if arg_name in _RESERVED_ARGS:
        msg = (
            f"{decorator_name} arg_name='{arg_name}' conflicts with Azure Functions "
            f"reserved parameter name. Avoid: {sorted(_RESERVED_ARGS)}"
        )
        raise ConfigurationError(msg)


def _build_host_signature(
    fn: Callable[..., Any],
    injected: set[str],
) -> inspect.Signature:
    sig = inspect.signature(fn, follow_wrapped=False)
    params = [p for name, p in sig.parameters.items() if name not in injected]
    return sig.replace(parameters=params)


class _AsyncProviderProxy:
    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def search(self, query: str, *, top: int = 5) -> list[Document]:
        return await asyncio.to_thread(self._provider.search, query, top=top)

    async def get_document(self, document_id: str) -> Document:
        return await asyncio.to_thread(self._provider.get_document, document_id)

    def close(self) -> None:
        self._provider.close()


class KnowledgeBindings:
    """Azure Functions-style decorator API for knowledge retrieval integration.

    Provides ``input`` and ``inject_client`` decorator methods that wrap
    knowledge providers in an Azure Functions-native decorator experience.

    ``input`` injects search results into handler parameters.
    ``inject_client`` injects a provider instance for imperative control.

    Decorator composition rules:
        - Azure decorators outermost, knowledge decorators closest to the function
        - ``input`` and ``inject_client`` are mutually exclusive
        - No decorator can be applied twice to the same handler
    """

    def input(
        self,
        arg_name: str,
        *,
        provider: str,
        query: str | Callable[..., str],
        top: int = 5,
        connection: str | Mapping[str, str],
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if top < 1:
            msg = f"input top must be >= 1, got {top}"
            raise ConfigurationError(msg)

        query_callable: Callable[..., str] | None = query if callable(query) else None
        query_static: str | None = None if callable(query) else query

        provider_name = provider
        provider_connection = connection
        provider_kwargs = kwargs

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            _check_composition(fn, "input")
            _validate_arg_name(arg_name, fn, "input")

            query_resolver_params: list[str] = []
            if query_callable is not None:
                resolver_sig = inspect.signature(query_callable)
                for p in resolver_sig.parameters.values():
                    if p.kind in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    ):
                        msg = "input query callable must not use *args or **kwargs"
                        raise ConfigurationError(msg)
                handler_sig = inspect.signature(fn, follow_wrapped=False)
                handler_params = {name for name in handler_sig.parameters if name != arg_name}
                resolver_param_names = list(resolver_sig.parameters.keys())
                unknown = set(resolver_param_names) - handler_params
                if unknown:
                    msg = (
                        f"input query callable references parameters "
                        f"{sorted(unknown)} not found in handler '{fn.__name__}'. "
                        f"Available: {sorted(handler_params)}"
                    )
                    raise ConfigurationError(msg)
                query_resolver_params = resolver_param_names

            is_async = inspect.iscoroutinefunction(fn)

            def _resolve_query(all_kwargs: dict[str, Any]) -> str:
                if query_callable is not None:
                    call_kwargs = {
                        name: all_kwargs[name]
                        for name in query_resolver_params
                        if name in all_kwargs
                    }
                    return query_callable(**call_kwargs)
                if query_static is None:
                    msg = "input: unreachable — neither query callable nor query static"
                    raise ConfigurationError(msg)
                return query_static

            def _execute_search(resolved_query: str) -> list[Document]:
                prov = create_provider(
                    provider_name,
                    connection=provider_connection,
                    **provider_kwargs,
                )
                try:
                    return prov.search(resolved_query, top=top)
                finally:
                    prov.close()

            if is_async:

                @functools.wraps(fn)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    resolved = _resolve_query(kwargs)
                    data = await asyncio.to_thread(_execute_search, resolved)
                    kwargs[arg_name] = data
                    return await fn(*args, **kwargs)

                setattr(
                    async_wrapper,
                    "__signature__",
                    _build_host_signature(fn, {arg_name}),
                )
                _mark_decorator(async_wrapper, "input")
                return async_wrapper

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                resolved = _resolve_query(kwargs)
                data = _execute_search(resolved)
                kwargs[arg_name] = data
                return fn(*args, **kwargs)

            setattr(wrapper, "__signature__", _build_host_signature(fn, {arg_name}))
            _mark_decorator(wrapper, "input")
            return wrapper

        return decorator

    def inject_client(
        self,
        arg_name: str,
        *,
        provider: str,
        connection: str | Mapping[str, str],
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        provider_name = provider
        provider_connection = connection
        provider_kwargs = kwargs

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            _check_composition(fn, "inject_client")
            _validate_arg_name(arg_name, fn, "inject_client")
            is_async = inspect.iscoroutinefunction(fn)

            if is_async:

                @functools.wraps(fn)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    prov = create_provider(
                        provider_name,
                        connection=provider_connection,
                        **provider_kwargs,
                    )
                    proxy = _AsyncProviderProxy(prov)
                    try:
                        kwargs[arg_name] = proxy
                        return await fn(*args, **kwargs)
                    finally:
                        prov.close()

                setattr(
                    async_wrapper,
                    "__signature__",
                    _build_host_signature(fn, {arg_name}),
                )
                _mark_decorator(async_wrapper, "inject_client")
                return async_wrapper

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                prov = create_provider(
                    provider_name,
                    connection=provider_connection,
                    **provider_kwargs,
                )
                try:
                    kwargs[arg_name] = prov
                    return fn(*args, **kwargs)
                finally:
                    prov.close()

            setattr(wrapper, "__signature__", _build_host_signature(fn, {arg_name}))
            _mark_decorator(wrapper, "inject_client")
            return wrapper

        return decorator
