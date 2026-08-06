# FAQ

## Which Python versions are supported?

Python 3.10 through 3.14 (`>=3.10, <3.15`).

## Do I always need the Notion extra?

Only if you use the built-in Notion provider. Custom providers have no such
dependency. Install with `pip install azure-functions-knowledge[notion]`
when you need Notion.

## Can I use this with async handlers?

Yes. Both `input` and `inject_client` detect `async def` handlers and offload
blocking provider I/O to a worker thread. With `inject_client`, the async
handler receives a proxy whose methods you `await`. See
[Usage → Async handlers](usage.md#async-handlers).

## Is the provider reused across invocations?

No. A provider is created per invocation and closed afterward in a `finally`
block. There is no built-in pooling — cache expensive resources inside your
provider implementation if needed.

## How do I add my own knowledge source?

Implement the [`KnowledgeProvider`](api.md#knowledgeprovider) protocol and call
`register_provider("my-name", MyProvider)`. See
[Usage → Custom provider registration](usage.md#custom-provider-registration).

## Where does the injected parameter come from?

The decorators hide the injected parameter from the host-facing signature and
supply it themselves at invocation time, so the Azure Functions host never tries
to bind it.

## What is `Document.score`?

A reserved field for relevance ranking. It is part of the public dataclass but
is not populated by the built-in Notion provider today.

## How do I keep secrets out of my code?

Use `%VAR%` placeholders in `connection` and store the real values in your
Function App application settings or `local.settings.json`. See
[Configuration](configuration.md).
