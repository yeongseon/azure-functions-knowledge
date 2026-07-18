# Configuration

Every decorator takes a `connection` argument that tells the provider how to
authenticate. Connections support `%VAR%` environment-variable substitution so
you never have to hard-code secrets.

## Connection forms

`connection` accepts either a string or a mapping:

```python
connection="%NOTION_TOKEN%"          # single env var
connection="Bearer %API_KEY%"        # partial substitution inside a larger string
connection={"token": "%MY_TOKEN%"}   # mapping with substitution
connection={"api_key": "%MY_TOKEN%"} # 'api_key' is accepted as an alias for 'token'
```

## `%VAR%` substitution

Placeholders match the pattern `%NAME%`, where `NAME` starts with a letter or
underscore and continues with letters, digits, or underscores. Each placeholder
is replaced with the corresponding environment variable. Multiple placeholders
in one string are all resolved.

```python
import os
os.environ["NOTION_TOKEN"] = "secret_abc123"

# "%NOTION_TOKEN%"        -> "secret_abc123"
# "Bearer %NOTION_TOKEN%" -> "Bearer secret_abc123"
```

Substitution is performed by `azure_functions_knowledge.auth.resolve_connection`.

### Error semantics

If a referenced variable is **not set**, `resolve_connection` raises
`ConfigurationError`:

```
Environment variable 'NOTION_TOKEN' referenced in connection string is not set
```

Because provider construction happens per invocation, this surfaces at request
time — set the variable in your Function App's application settings (or your
local `local.settings.json`) before deploying.

## Notion token mapping

`NotionProvider` accepts a connection in two shapes:

- **String** — resolved through `%VAR%` substitution, then used directly as the
  Notion integration token.
- **Mapping** — the token is read from the `token` key, falling back to
  `api_key`. The resolved value is then passed through `%VAR%` substitution.
  If neither key is present, an `AuthError` is raised:

  ```
  NotionProvider connection mapping must contain 'token' or 'api_key'
  ```

If the Notion client fails to initialize with the resolved token, an
`AuthError` is raised with the underlying cause attached.

## Passing provider options

Any keyword arguments beyond `connection` are forwarded to the provider
constructor. For Notion, for example:

```python
@kb.input(
    "docs",
    provider="notion",
    query="roadmap",
    connection="%NOTION_TOKEN%",
    include_content=False,   # forwarded to NotionProvider
    content_max_chars=2000,  # forwarded to NotionProvider
)
def handler(req, docs): ...
```

See [Providers → Notion](providers/notion.md) for the full list of options.
