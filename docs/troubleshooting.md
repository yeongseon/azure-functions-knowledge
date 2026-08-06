# Troubleshooting

Common problems and how to resolve them.

## `ProviderError: notion-client is required for NotionProvider`

The optional Notion dependency is not installed. Install the extra:

```bash
pip install azure-functions-knowledge[notion]
```

## `ConfigurationError: Environment variable '...' referenced in connection string is not set`

A `%VAR%` placeholder in your `connection` has no matching environment variable.
Set it in your Function App application settings (or `local.settings.json` for
local runs) before invoking the function. See [Configuration](configuration.md).

## `ConfigurationError: Unknown provider '...'`

The `provider` name is not registered. Check spelling, confirm the provider was
imported/registered before the handler runs, and use
`get_registered_providers()` to list what is available.

## `AuthError: NotionProvider connection mapping must contain 'token' or 'api_key'`

When passing a mapping connection, include a `token` (or `api_key`) key:

```python
connection={"token": "%NOTION_TOKEN%"}
```

## `ConfigurationError: ... arg_name='...' conflicts with Azure Functions reserved parameter name`

The injected parameter name collides with a host-reserved name
(`context`, `input`, `msg`, `output`, `req`, `timer`). Rename the injected
parameter — for example use `docs` instead of `input`.

## `ConfigurationError: Cannot combine 'input' and 'inject_client' ...`

The two decorators are mutually exclusive on one handler. Pick one.

## Notion returns fewer/empty results than expected

- Ensure your Notion integration has access to the pages/databases you expect
  (share them with the integration in Notion).
- If content is missing, confirm `include_content=True` (the default).
- Very large pages may hit `max_blocks` / `max_depth` caps — raise them if you
  need deeper extraction, but mind Notion rate limits.

## Notion API rate limiting

Reduce request volume by lowering `max_blocks` / `max_depth`, or set
`include_content=False` when you only need titles and URLs. See
[Providers → Notion](providers/notion.md#rate-limits).
