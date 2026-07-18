from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
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
_TOOLKIT_META_ATTR = "_azure_functions_metadata"


def _get_decorators(fn: Callable[..., Any]) -> frozenset[str]:
    existing: object = getattr(fn, _KNOWLEDGE_DECORATOR_ATTR, frozenset())
    if not isinstance(existing, frozenset):
        return frozenset()
    return existing


def _mark_decorator(fn: Callable[..., Any], name: str) -> None:
    setattr(fn, _KNOWLEDGE_DECORATOR_ATTR, _get_decorators(fn) | {name})


def _write_toolkit_metadata(
    wrapper: Callable[..., Any],
    fn: Callable[..., Any],
    meta: dict[str, Any],
) -> None:
    """Publish knowledge metadata on the ecosystem-wide convention attribute.

    Sibling toolkit packages (``azure-functions-openapi``, validation, logging)
    introspect ``_azure_functions_metadata`` to compose behavior. Writing the
    ``knowledge`` namespace here lets those tools discover knowledge-backed
    handlers instead of the package being an island. Consumers never need to
    import this package.
    """
    combined = dict(getattr(fn, _TOOLKIT_META_ATTR, None) or {})
    combined["knowledge"] = meta
    setattr(wrapper, _TOOLKIT_META_ATTR, combined)


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


@contextmanager
def _provider_context(
    provider_name: str,
    connection: str | Mapping[str, str],
    provider_kwargs: dict[str, Any],
) -> Iterator[Any]:
    """Create a provider, yield it, and always close it.

    Centralizes the provider lifecycle so every wrapper shares one create →
    use → close path. This is also the natural seam for future provider
    pooling.
    """
    provider = create_provider(
        provider_name,
        connection=connection,
        **provider_kwargs,
    )
    try:
        yield provider
    finally:
        provider.close()


class AsyncProxy:
    """Wrap a synchronous provider so async handlers can ``await`` its methods.

    Any attribute access that resolves to a callable is offloaded to a worker
    thread via :func:`asyncio.to_thread`, so the proxy does not need editing
    when the provider protocol grows new methods. Non-callable attributes are
    returned as-is. ``close`` is intentionally kept synchronous.
    """

    def __init__(self, target: Any) -> None:
        self._target = target

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        async def _async_call(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.to_thread(attr, *args, **kwargs)

        return _async_call

    def close(self) -> None:
        self._target.close()


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

    def _wrap_handler(
        self,
        fn: Callable[..., Any],
        arg_name: str,
        make_injection: Callable[[dict[str, Any], bool], Any],
        mark_name: str,
        meta: dict[str, Any],
    ) -> Callable[..., Any]:
        """Build the sync/async handler wrapper shared by both decorators.

        ``make_injection(kwargs, is_async)`` returns a context manager that
        yields the value to inject into ``arg_name``. The provider stays alive
        for the duration of the ``with`` block (i.e. while the handler runs).
        """
        is_async = inspect.iscoroutinefunction(fn)

        if is_async:

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                cm = make_injection(kwargs, True)
                # Entering may create a provider and/or run a blocking search,
                # so offload it to keep the event loop responsive.
                value = await asyncio.to_thread(cm.__enter__)
                try:
                    kwargs[arg_name] = value
                    return await fn(*args, **kwargs)
                finally:
                    await asyncio.to_thread(cm.__exit__, None, None, None)

            wrapper: Callable[..., Any] = async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with make_injection(kwargs, False) as value:
                    kwargs[arg_name] = value
                    return fn(*args, **kwargs)

            wrapper = sync_wrapper

        setattr(wrapper, "__signature__", _build_host_signature(fn, {arg_name}))
        _mark_decorator(wrapper, mark_name)
        _write_toolkit_metadata(wrapper, fn, meta)
        return wrapper

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

            @contextmanager
            def _make_injection(
                all_kwargs: dict[str, Any], _is_async: bool
            ) -> Iterator[list[Document]]:
                resolved = _resolve_query(all_kwargs)
                with _provider_context(provider_name, provider_connection, provider_kwargs) as prov:
                    yield prov.search(resolved, top=top)

            meta = {
                "version": 1,
                "mode": "input",
                "provider": provider_name,
                "arg_name": arg_name,
                "query": "dynamic" if query_callable is not None else "static",
                "top": top,
            }
            return self._wrap_handler(fn, arg_name, _make_injection, "input", meta)

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

            @contextmanager
            def _make_injection(_all_kwargs: dict[str, Any], is_async: bool) -> Iterator[Any]:
                with _provider_context(provider_name, provider_connection, provider_kwargs) as prov:
                    yield AsyncProxy(prov) if is_async else prov

            meta = {
                "version": 1,
                "mode": "inject_client",
                "provider": provider_name,
                "arg_name": arg_name,
            }
            return self._wrap_handler(fn, arg_name, _make_injection, "inject_client", meta)

        return decorator
